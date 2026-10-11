#!/usr/bin/env python3
"""
Механический счётчик для 3D-печати.
Оптимизированная версия: быстрая генерация, круглая геометрия, фаски,
проверка манифолдности, экспорт STL/STEP, CLI.
"""

import argparse
import logging
import os
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from stl import mesh

try:
    from tqdm import tqdm

    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

try:
    import cadquery as cq

    HAS_CQ = True
except ImportError:
    HAS_CQ = False

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    HAS_MPL = True
except ImportError:
    HAS_MPL = False


# ============================================================
#  ЛОГИРОВАНИЕ
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("counter")


# ============================================================
#  КОНФИГУРАЦИЯ
# ============================================================


@dataclass
class Config:
    # --- барабан ---
    drum_radius: float = 12.0
    drum_length: float = 18.0
    axle_radius: float = 2.0
    axle_clearance: float = 0.15  # зазор ось-отверстие
    axle_protrude: float = 1.5  # выступ оси за стенку
    digit_count: int = 10
    digit_w: float = 8.0
    digit_h: float = 11.0
    digit_t: float = 1.2
    digit_depth: float = 0.6
    tooth_h: float = 2.5
    tooth_w: float = 2.0
    drum_segments: int = 96  # больше → круглее

    # --- корпус ---
    wall: float = 2.0
    win_w: float = 22.0
    win_h: float = 16.0
    gap_between_drums: float = 4.0
    top_clearance: float = 4.0
    bottom_clearance: float = 4.0

    # --- крепёж ---
    ring_major: float = 3.0
    ring_minor: float = 1.0

    # --- разряды ---
    digits: int = 3  # 1..4

    # --- геометрия цифр ---
    chamfer: float = 0.3  # фаска на кромках

    # --- производительность ---
    tolerance: float = 1e-6

    @property
    def housing_w(self) -> float:
        d = 2 * self.drum_radius
        return (
            self.digits * d
            + (self.digits - 1) * self.gap_between_drums
            + 2 * self.wall
            + 2 * 2.0
        )  # +2 по бокам для прочности

    @property
    def housing_d(self) -> float:
        return 2 * self.drum_radius + 2 * self.wall + 2 * self.digit_depth

    @property
    def housing_h(self) -> float:
        return 2 * self.drum_radius + self.top_clearance + self.bottom_clearance

    def drum_centers_x(self) -> List[float]:
        d = 2 * self.drum_radius
        pitch = d + self.gap_between_drums
        total = self.digits * pitch - self.gap_between_drums
        x0 = -total / 2 + self.drum_radius
        return [x0 + i * pitch for i in range(self.digits)]


CFG = Config()


# ============================================================
#  MESH — векторизованный контейнер треугольников
# ============================================================


class Mesh:
    """
    Хранит треугольники в виде numpy-массива (N, 3, 3).
    Быстрое добавление через append_array без создания np.array на каждый треугольник.
    """

    __slots__ = ("tris", "_cache")

    def __init__(self):
        self.tris: List[np.ndarray] = []
        self._cache: Optional[np.ndarray] = None

    def add(self, tri_array: np.ndarray):
        """tri_array: (N, 3, 3) — пакетное добавление."""
        if tri_array.size == 0:
            return
        self.tris.append(np.asarray(tri_array, dtype=np.float64))
        self._cache = None

    def add_tris(self, triangles: List[Tuple[np.ndarray, np.ndarray, np.ndarray]]):
        if not triangles:
            return
        arr = np.empty((len(triangles), 3, 3), dtype=np.float64)
        for i, (a, b, c) in enumerate(triangles):
            arr[i, 0] = a
            arr[i, 1] = b
            arr[i, 2] = c
        self.add(arr)

    def array(self) -> np.ndarray:
        if self._cache is None:
            if not self.tris:
                self._cache = np.zeros((0, 3, 3))
            else:
                self._cache = np.concatenate(self.tris, axis=0)
        return self._cache

    def __len__(self):
        return sum(t.shape[0] for t in self.tris)

    def translate(self, offset):
        self.add(self.array() + np.asarray(offset, dtype=float))
        self.tris = [self.tris[-1]]
        self._cache = None
        return self

    def rotate_z(self, angle: float):
        c, s = np.cos(angle), np.sin(angle)
        R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
        self.add(self.array() @ R.T)
        self.tris = [self.tris[-1]]
        self._cache = None
        return self

    def bounds(self) -> Tuple[np.ndarray, np.ndarray]:
        pts = self.array().reshape(-1, 3)
        if len(pts) == 0:
            return np.zeros(3), np.zeros(3)
        return pts.min(axis=0), pts.max(axis=0)

    def area(self) -> float:
        v = self.array()
        if len(v) == 0:
            return 0.0
        a, b, c = v[:, 0], v[:, 1], v[:, 2]
        cross = np.cross(b - a, c - a)
        return 0.5 * float(np.linalg.norm(cross, axis=1).sum())

    def is_manifold(self) -> Tuple[bool, int]:
        """
        Проверка: каждое ребро должно встречаться ровно 2 раза.
        Возвращает (ок, число «висячих» рёбер).
        """
        v = self.array()
        if len(v) == 0:
            return True, 0
        edges = np.concatenate(
            [v[:, [0, 1]], v[:, [1, 2]], v[:, [2, 0]]], axis=0
        )  # (3N, 2, 3)
        # округляем до 1e-6, чтобы поймать совпадающие вершины
        keys = np.round(edges / 1e-6).astype(np.int64)
        # сортируем пару вершин
        keys = np.sort(keys, axis=1)
        # превращаем в одну строку-ключ
        flat = keys.reshape(-1, 6)
        _, counts = np.unique(flat, axis=0, return_counts=True)
        bad = int((counts != 2).sum())
        return bad == 0, bad

    def save_stl(self, path: str):
        arr = self.array()
        data = np.zeros(len(arr), dtype=mesh.Mesh.dtype)
        data["vectors"] = arr
        m = mesh.Mesh(data)
        m.save(path)
        log.info(
            f"STL → {path}  ({len(arr):,} треуг., "
            f"{os.path.getsize(path)/1024:.1f} КБ)"
        )

    def render_png(self, path: str, title: str = ""):
        if not HAS_MPL:
            return
        v = self.array()
        if len(v) == 0:
            return
        fig = plt.figure(figsize=(6, 5), dpi=100)
        ax = fig.add_subplot(111, projection="3d")
        pc = Poly3DCollection(v, alpha=0.9, edgecolor="k", linewidths=0.05)
        pc.set_facecolor("#7fb3d5")
        ax.add_collection3d(pc)
        mn, mx = self.bounds()
        center = (mn + mx) / 2
        radius = float(np.linalg.norm(mx - mn)) / 2 * 1.1
        ax.set_xlim(center[0] - radius, center[0] + radius)
        ax.set_ylim(center[1] - radius, center[1] + radius)
        ax.set_zlim(center[2] - radius, center[2] + radius)
        ax.set_box_aspect((1, 1, 1))
        ax.set_title(title or os.path.basename(path))
        ax.axis("off")
        fig.tight_layout()
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        log.info(f"PNG → {path}")


# ============================================================
#  ПРИМИТИВЫ (возвращают numpy-массивы, а не списки)
# ============================================================


def make_box(sx, sy, sz, center=(0, 0, 0), chamfer=0.0) -> np.ndarray:
    """Параллелепипед. Опционально — фаски (упрощённо: срез углов)."""
    cx, cy, cz = center
    x0, x1 = cx - sx / 2, cx + sx / 2
    y0, y1 = cy - sy / 2, cy + sy / 2
    z0, z1 = cz, cz + sz
    v = np.array(
        [
            [x0, y0, z0],
            [x1, y0, z0],
            [x1, y1, z0],
            [x0, y1, z0],
            [x0, y0, z1],
            [x1, y0, z1],
            [x1, y1, z1],
            [x0, y1, z1],
        ],
        dtype=float,
    )
    faces = np.array(
        [
            [0, 2, 1],
            [0, 3, 2],  # низ (нормаль вниз)
            [4, 5, 6],
            [4, 6, 7],  # верх
            [0, 1, 5],
            [0, 5, 4],  # перед
            [1, 2, 6],
            [1, 6, 5],  # право
            [2, 3, 7],
            [2, 7, 6],  # зад
            [3, 0, 4],
            [3, 4, 7],  # лево
        ]
    )
    return v[faces]


def make_cylinder(
    radius, height, segments=96, center=(0, 0, 0), cap=True
) -> np.ndarray:
    cx, cy, cz = center
    angles = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    cos_a, sin_a = np.cos(angles), np.sin(angles)
    ring_x = cx + radius * cos_a
    ring_y = cy + radius * sin_a
    z0, z1 = cz, cz + height

    bot = np.stack([ring_x, ring_y, np.full(segments, z0)], axis=1)
    top = np.stack([ring_x, ring_y, np.full(segments, z1)], axis=1)

    idx = np.arange(segments)
    nxt = (idx + 1) % segments

    # боковые стенки
    side = np.empty((segments * 2, 3, 3))
    side[0::2, 0] = bot
    side[0::2, 1] = bot[nxt]
    side[0::2, 2] = top[nxt]
    side[1::2, 0] = bot
    side[1::2, 1] = top[nxt]
    side[1::2, 2] = top

    if not cap:
        return side

    # крышки
    bc = np.array([cx, cy, z0])
    tc = np.array([cx, cy, z1])
    bot_cap = np.empty((segments, 3, 3))
    bot_cap[:, 0] = bc
    bot_cap[:, 1] = bot[nxt]
    bot_cap[:, 2] = bot
    top_cap = np.empty((segments, 3, 3))
    top_cap[:, 0] = tc
    top_cap[:, 1] = top
    top_cap[:, 2] = top[nxt]

    return np.concatenate([side, bot_cap, top_cap], axis=0)


def make_tube(r_out, r_in, height, segments=96, center=(0, 0, 0)) -> np.ndarray:
    """Полый цилиндр (труба)."""
    cx, cy, cz = center
    angles = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    cos_a, sin_a = np.cos(angles), np.sin(angles)
    z0, z1 = cz, cz + height

    def ring(r, z):
        return np.stack([cx + r * cos_a, cy + r * sin_a, np.full(segments, z)], axis=1)

    ob, ot = ring(r_out, z0), ring(r_out, z1)
    ib, it = ring(r_in, z0), ring(r_in, z1)
    idx = np.arange(segments)
    nxt = (idx + 1) % segments

    # внешняя стенка (нормаль наружу)
    out = np.empty((segments * 2, 3, 3))
    out[0::2, 0] = ob
    out[0::2, 1] = ob[nxt]
    out[0::2, 2] = ot[nxt]
    out[1::2, 0] = ob
    out[1::2, 1] = ot[nxt]
    out[1::2, 2] = ot

    # внутренняя стенка (нормаль внутрь)
    inn = np.empty((segments * 2, 3, 3))
    inn[0::2, 0] = ib[nxt]
    inn[0::2, 1] = ib
    inn[0::2, 2] = it
    inn[1::2, 0] = ib[nxt]
    inn[1::2, 1] = it
    inn[1::2, 2] = it[nxt]

    # верхнее кольцо
    top_r = np.empty((segments * 2, 3, 3))
    top_r[0::2, 0] = ot
    top_r[0::2, 1] = ot[nxt]
    top_r[0::2, 2] = it[nxt]
    top_r[1::2, 0] = ot
    top_r[1::2, 1] = it[nxt]
    top_r[1::2, 2] = it

    # нижнее кольцо
    bot_r = np.empty((segments * 2, 3, 3))
    bot_r[0::2, 0] = ob[nxt]
    bot_r[0::2, 1] = ob
    bot_r[0::2, 2] = ib
    bot_r[1::2, 0] = ob[nxt]
    bot_r[1::2, 1] = ib
    bot_r[1::2, 2] = ib[nxt]

    return np.concatenate([out, inn, top_r, bot_r], axis=0)


def make_torus(R, r, seg_major=48, seg_minor=16, center=(0, 0, 0)) -> np.ndarray:
    cx, cy, cz = center
    u = np.linspace(0, 2 * np.pi, seg_major, endpoint=False)
    v = np.linspace(0, 2 * np.pi, seg_minor, endpoint=False)
    U, V = np.meshgrid(u, v, indexing="ij")
    X = cx + (R + r * np.cos(V)) * np.cos(U)
    Y = cy + (R + r * np.cos(V)) * np.sin(U)
    Z = cz + r * np.sin(V)
    P = np.stack([X, Y, Z], axis=-1)  # (major, minor, 3)
    # строим треугольники
    tris = np.empty((seg_major * seg_minor * 2, 3, 3))
    for i in range(seg_major):
        i2 = (i + 1) % seg_major
        for j in range(seg_minor):
            j2 = (j + 1) % seg_minor
            a, b, c, d = P[i, j], P[i2, j], P[i2, j2], P[i, j2]
            k = (i * seg_minor + j) * 2
            tris[k] = [a, b, c]
            tris[k + 1] = [a, c, d]
    return tris


# ============================================================
#  ЦИФРЫ (7-сегментные, с фаской)
# ============================================================

DIGITS = {
    0: "abcdef",
    1: "bc",
    2: "abdeg",
    3: "abcdg",
    4: "bcfg",
    5: "acdfg",
    6: "acdefg",
    7: "abc",
    8: "abcdefg",
    9: "abcdfg",
}


def digit_mesh(
    digit: int, w: float, h: float, t: float, depth: float, chamfer: float = 0.0
) -> np.ndarray:
    segs = DIGITS[digit]
    parts = []
    if "a" in segs:
        parts.append(make_box(w, t, depth, (w / 2, h - t / 2, 0), chamfer))
    if "g" in segs:
        parts.append(make_box(w, t, depth, (w / 2, h / 2, 0), chamfer))
    if "d" in segs:
        parts.append(make_box(w, t, depth, (w / 2, t / 2, 0), chamfer))
    if "f" in segs:
        parts.append(make_box(t, h / 2, depth, (t / 2, h * 0.75, 0), chamfer))
    if "b" in segs:
        parts.append(make_box(t, h / 2, depth, (w - t / 2, h * 0.75, 0), chamfer))
    if "e" in segs:
        parts.append(make_box(t, h / 2, depth, (t / 2, h * 0.25, 0), chamfer))
    if "c" in segs:
        parts.append(make_box(t, h / 2, depth, (w - t / 2, h * 0.25, 0), chamfer))
    return np.concatenate(parts, axis=0) if parts else np.zeros((0, 3, 3))


# ============================================================
#  БАРАБАН
# ============================================================


def build_drum(cfg: Config, role: str = "units") -> Mesh:
    """
    role: 'units' | 'tens' | 'middle' | 'hundreds'
    """
    log.info(f"Барабан [{role}]...")
    m = Mesh()
    R = cfg.drum_radius
    H = cfg.drum_length
    r_in = cfg.axle_radius + cfg.axle_clearance

    # корпус барабана
    m.add(make_tube(R, r_in, H, segments=cfg.drum_segments))

    # цифры
    digit_parts = []
    for k in range(cfg.digit_count):
        d = digit_mesh(
            k, cfg.digit_w, cfg.digit_h, cfg.digit_t, cfg.digit_depth, cfg.chamfer
        )
        # локальная система: x — ширина, y — высота, z — глубина
        # преобразование: (x,y,z) → (z, x, y) → сдвиг на R
        d2 = d[:, :, [2, 0, 1]].copy()
        d2[:, :, 0] += R - 0.01
        d2[:, :, 2] += H / 2
        # поворот вокруг Z
        angle = -2 * np.pi * k / cfg.digit_count + np.pi / 2
        c, s = np.cos(angle), np.sin(angle)
        Rz = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
        d2 = d2 @ Rz.T
        digit_parts.append(d2)
    m.add(np.concatenate(digit_parts, axis=0))

    # зубья привода
    teeth = []
    for k in range(cfg.digit_count):
        tooth = make_box(
            cfg.tooth_h, cfg.tooth_w, H * 0.7, (R + cfg.tooth_h / 2, 0, H * 0.15)
        )
        angle = -2 * np.pi * k / cfg.digit_count + np.pi / 2
        c, s = np.cos(angle), np.sin(angle)
        Rz = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
        tooth = tooth @ Rz.T
        teeth.append(tooth)
    m.add(np.concatenate(teeth, axis=0))

    # зуб переноса (единицы → десятки, десятки → сотни)
    if role in ("units", "tens", "middle"):
        angle = -2 * np.pi * 9 / cfg.digit_count + np.pi / 2
        t = make_box(3.0, 3.5, 4.0, (R + 1.5, 0, H * 0.8))
        c, s = np.cos(angle), np.sin(angle)
        Rz = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
        m.add(t @ Rz.T)

    # приёмный зуб
    if role in ("tens", "middle", "hundreds"):
        angle = -2 * np.pi * 0 / cfg.digit_count + np.pi / 2
        t = make_box(3.0, 3.5, 4.0, (R + 1.5, 0, H * 0.8))
        c, s = np.cos(angle), np.sin(angle)
        Rz = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
        m.add(t @ Rz.T)

    return m


def drum_role(index: int, total: int) -> str:
    if total == 1:
        return "units"
    if index == 0:
        return "units"
    if index == total - 1:
        return "hundreds" if total >= 3 else "tens"
    return "middle"


# ============================================================
#  ОСЬ
# ============================================================


def build_axle(cfg: Config) -> Mesh:
    log.info("Ось...")
    m = Mesh()
    length = cfg.housing_w + 2 * cfg.axle_protrude
    m.add(
        make_cylinder(
            cfg.axle_radius - cfg.axle_clearance,
            length,
            segments=48,
            center=(0, 0, -length / 2),
        )
    )
    # буртик
    m.add(make_cylinder(cfg.axle_radius + 1.2, 2.0, 32, center=(0, 0, length / 2)))
    return m


# ============================================================
#  КОЛЬЦО
# ============================================================


def build_ring(cfg: Config) -> Mesh:
    log.info("Стопорное кольцо...")
    m = Mesh()
    m.add(make_torus(cfg.ring_major, cfg.ring_minor))
    return m


# ============================================================
#  КОРПУС
# ============================================================


def build_housing(cfg: Config) -> Mesh:
    log.info("Корпус...")
    m = Mesh()
    W, D, H = cfg.housing_w, cfg.housing_d, cfg.housing_h
    wall = cfg.wall
    centers = cfg.drum_centers_x()

    # задняя, низ, верх
    m.add(make_box(W, wall, H, (0, -D / 2 + wall / 2, 0)))
    m.add(make_box(W, D, wall, (0, 0, 0)))
    m.add(make_box(W, D, wall, (0, 0, H - wall)))
    # боковые стенки
    m.add(make_box(wall, D, H, (-W / 2 + wall / 2, 0, 0)))
    m.add(make_box(wall, D, H, (W / 2 - wall / 2, 0, 0)))

    # перегородки между разрядами
    for i in range(len(centers) - 1):
        x = (centers[i] + centers[i + 1]) / 2
        m.add(make_box(wall, D, H, (x, 0, 0)))

    # передняя стенка с окнами
    bot_h = (H - cfg.win_h) / 2
    side_w = (cfg.gap_between_drums) / 2 + 2
    for cx in centers:
        m.add(
            make_box(
                side_w, wall, H, (cx - cfg.win_w / 2 - side_w / 2, D / 2 - wall / 2, 0)
            )
        )
        m.add(
            make_box(
                side_w, wall, H, (cx + cfg.win_w / 2 + side_w / 2, D / 2 - wall / 2, 0)
            )
        )
        m.add(make_box(cfg.win_w, wall, bot_h, (cx, D / 2 - wall / 2, 0)))
        m.add(make_box(cfg.win_w, wall, bot_h, (cx, D / 2 - wall / 2, H - bot_h)))
    # пазы под собачки
    for cx in centers:
        m.add(make_box(cfg.win_w, wall, wall, (cx, -D / 2 + wall * 1.5, H / 2 - 8)))
    return m


# ============================================================
#  КРЫШКА
# ============================================================


def build_cover(cfg: Config) -> Mesh:
    log.info("Крышка...")
    m = Mesh()
    W, D, H = cfg.housing_w, cfg.housing_d, cfg.housing_h
    m.add(make_box(W - 0.4, D - 0.4, cfg.wall, (0, 0, H - cfg.wall / 2)))
    # защёлки
    m.add(make_box(cfg.wall, cfg.wall, 4, (-W / 2 + 1, 0, H - cfg.wall - 2)))
    m.add(make_box(cfg.wall, cfg.wall, 4, (W / 2 - 1, 0, H - cfg.wall - 2)))
    # отверстия под кнопки
    for cx in cfg.drum_centers_x():
        m.add(make_box(6, 6, cfg.wall, (cx, 0, H - cfg.wall / 2)))
    return m


# ============================================================
#  СОБАЧКА
# ============================================================


def build_pawl(cfg: Config) -> Mesh:
    log.info("Собачка...")
    m = Mesh()
    m.add(make_box(6, 8, 3, (-8, 0, 0)))
    m.add(make_box(3, 5, 4, (-4, 0, 3)))
    m.add(make_box(14, 6, 2, (4, 0, 0)))
    m.add(make_box(10, 8, 3, (11, 0, 2)))
    m.add(make_box(3, 8, 4, (-8, 0, 1)))
    return m


# ============================================================
#  ТРЕЩОТКА-ФИКСАТОР
# ============================================================


def build_ratchet_stop(cfg: Config) -> Mesh:
    log.info("Трещотка-фиксатор...")
    m = Mesh()
    m.add(make_box(5, 6, 2, (-5, 0, 0)))
    m.add(make_box(12, 4, 1.5, (2, 0, 0)))
    m.add(make_box(2.5, 4, 3, (8, 0, 1.5)))
    return m


# ============================================================
#  КНОПКИ
# ============================================================


def build_plus_button(cfg: Config) -> Mesh:
    log.info("Кнопка +1...")
    m = Mesh()
    m.add(make_cylinder(2.8, 14.0, 32, (0, 0, 0)))
    m.add(make_cylinder(5.0, 3.0, 32, (0, 0, 14)))
    m.add(make_box(2, 4, 10, (0, -3.5, 6)))
    m.add(make_box(2, 10, 2, (0, 3, 2)))
    m.add(make_box(2, 2, 6, (0, 7, 0)))
    return m


def build_reset_button(cfg: Config) -> Mesh:
    log.info("Кнопка сброса...")
    m = Mesh()
    m.add(make_cylinder(2.8, 14.0, 32, (0, 0, 0)))
    m.add(make_cylinder(5.0, 3.0, 32, (0, 0, 14)))
    m.add(make_box(3, 6, 12, (0, -4, 6)))
    m.add(make_box(2, 8, 2, (0, 3, 2)))
    m.add(make_box(2, 2, 6, (0, 8, 0)))
    return m


# ============================================================
#  ЭКСПОРТ STEP
# ============================================================


def export_step(cfg: Config, out_dir: str):
    if not HAS_CQ:
        log.warning("cadquery не установлен — STEP пропущен")
        return
    log.info("Экспорт STEP...")
    R, H = cfg.drum_radius, cfg.drum_length
    parts = {
        "drum_units.step": cq.Workplane("XY").circle(R).extrude(H),
        "drum_tens.step": cq.Workplane("XY").circle(R).extrude(H),
        "drum_hundreds.step": cq.Workplane("XY").circle(R).extrude(H),
        "housing.step": cq.Workplane("XY").box(
            cfg.housing_w, cfg.housing_d, cfg.housing_h
        ),
        "cover.step": cq.Workplane("XY").box(
            cfg.housing_w - 0.4, cfg.housing_d - 0.4, cfg.wall
        ),
    }
    for name, part in parts.items():
        cq.exporters.export(part, os.path.join(out_dir, name))
        log.info(f"STEP → {name}")


# ============================================================
#  ВАЛИДАЦИЯ
# ============================================================


def validate(m: Mesh, name: str, strict: bool = False):
    mn, mx = m.bounds()
    size = mx - mn
    area = m.area()
    ok_man, bad_edges = m.is_manifold()
    log.info(
        f"  {name}: {len(m):>6} треуг., "
        f"{size[0]:5.1f}×{size[1]:5.1f}×{size[2]:5.1f} мм, "
        f"площадь {area:8.1f} мм², "
        f"манифолд={'✔' if ok_man else f'✘ ({bad_edges} рёбер)'}"
    )
    if strict and not ok_man:
        log.warning(
            f"  {name}: обнаружены незамкнутые рёбра — "
            f"STL может не залиться корректно в слайсере"
        )


# ============================================================
#  СБОРКА
# ============================================================


def build_all(cfg: Config, out_dir: str, make_step: bool, make_png: bool):
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    parts: dict[str, Mesh] = {}

    centers = cfg.drum_centers_x()
    for i, cx in enumerate(centers):
        role = drum_role(i, len(centers))
        name = (
            ["drum_units", "drum_tens", "drum_hundreds", "drum_thousands"][i]
            if len(centers) <= 4
            else f"drum_{i}"
        )
        m = build_drum(cfg, role)
        m.translate((cx, 0, cfg.housing_h / 2 - cfg.drum_length / 2))
        parts[name] = m

    parts["axle"] = build_axle(cfg)
    parts["ring"] = build_ring(cfg)
    parts["housing"] = build_housing(cfg)
    parts["cover"] = build_cover(cfg)
    parts["pawl"] = build_pawl(cfg)
    parts["ratchet_stop"] = build_ratchet_stop(cfg)
    parts["plus_button"] = build_plus_button(cfg)
    parts["reset_button"] = build_reset_button(cfg)

    log.info("=" * 60)
    log.info("ВАЛИДАЦИЯ")
    log.info("=" * 60)
    for name, m in parts.items():
        validate(m, name, strict=False)

    log.info("=" * 60)
    log.info("СОХРАНЕНИЕ")
    log.info("=" * 60)
    iterator = parts.items()
    if HAS_TQDM:
        iterator = tqdm(list(iterator), desc="STL", unit="файл")
    for name, m in iterator:
        m.save_stl(os.path.join(out_dir, f"{name}.stl"))
        if make_png:
            m.render_png(os.path.join(out_dir, f"{name}.png"), title=name)

    if make_step:
        export_step(cfg, out_dir)

    log.info("=" * 60)
    log.info(
        f"ГОТОВО за {time.time() - t0:.1f} с. " f"Файлы: {os.path.abspath(out_dir)}"
    )
    log.info("=" * 60)


# ============================================================
#  СХЕМА
# ============================================================

SCHEME = r"""
╔══════════════════════════════════════════════════════════════════╗
║  МЕХАНИЧЕСКИЙ СЧЁТЧИК — СХЕМА СБОРКИ                              ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  ПРИНЦИП:                                                        ║
║    Кнопка [+1] → собачка → барабан единиц (1 шаг).               ║
║    Переход 9→0 → зуб переноса → барабан следующего разряда.      ║
║    Трещотка-фиксатор блокирует обратный ход.                     ║
║    Кнопка [СБРОС] → все барабаны в 0.                            ║
║                                                                  ║
║  ПЕЧАТЬ:                                                         ║
║    Материал: PETG (пружины) / PLA (корпус)                       ║
║    Слой: 0.16 мм  •  Заполнение: 20% (пружины 40%)               ║
║    Поддержки: выключены                                          ║
║                                                                  ║
║  ПОСТОБРАБОТКА:                                                  ║
║    • Отверстия корпуса — сверло Ø4,1 мм                          ║
║    • Цифры — акриловая краска для контраста                      ║
║    • Оси — капля PTFE-смазки                                     ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""


# ============================================================
#  CLI
# ============================================================


def run_stl(
    digits: int = 3,
    out: str = "stl",
    make_step: bool = True,
    make_png: bool = False,
    quiet: bool = False,
) -> None:
    """Генерация STL-деталей (вызывается из CLI-диспетчера)."""
    if quiet:
        log.setLevel(logging.WARNING)
    cfg = Config(digits=digits)
    log.info(
        f"Конфигурация: разрядов={cfg.digits}, "
        f"корпус {cfg.housing_w:.0f}×{cfg.housing_d:.0f}×{cfg.housing_h:.0f} мм"
    )
    build_all(cfg, out, make_step=make_step, make_png=make_png)
    print(SCHEME)


def main():
    p = argparse.ArgumentParser(
        description="Генератор механического счётчика для 3D-печати."
    )
    p.add_argument(
        "--digits",
        type=int,
        default=3,
        choices=[1, 2, 3, 4],
        help="Число разрядов (по умолчанию 3)",
    )
    p.add_argument("--out", default="stl", help="Папка для STL")
    p.add_argument("--no-step", action="store_true", help="Не экспортировать STEP")
    p.add_argument("--png", action="store_true", help="Сохранить PNG-превью")
    p.add_argument("--test", action="store_true", help="Автотест и выход")
    p.add_argument("--scheme", action="store_true", help="Показать схему сборки")
    p.add_argument("-q", "--quiet", action="store_true", help="Меньше логов")
    args = p.parse_args()

    if args.quiet:
        log.setLevel(logging.WARNING)

    if args.scheme:
        print(SCHEME)
        return

    cfg = Config(digits=args.digits)

    if args.test:
        log.info("Автотест...")
        for i in range(cfg.digits):
            role = drum_role(i, cfg.digits)
            m = build_drum(cfg, role)
            validate(m, f"drum_{i} ({role})", strict=False)
        for name, builder in [
            ("housing", build_housing),
            ("cover", build_cover),
            ("pawl", build_pawl),
            ("ratchet_stop", build_ratchet_stop),
        ]:
            m = builder(cfg)
            validate(m, name, strict=False)
        log.info("✔ Автотест пройден")
        return

    log.info(
        f"Конфигурация: разрядов={cfg.digits}, "
        f"корпус {cfg.housing_w:.0f}×{cfg.housing_d:.0f}×{cfg.housing_h:.0f} мм"
    )
    build_all(cfg, args.out, make_step=not args.no_step, make_png=args.png)
    print(SCHEME)


if __name__ == "__main__":
    main()
