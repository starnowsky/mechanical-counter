#!/usr/bin/env python3
from __future__ import annotations

"""
Полный рендер-пайплайн: PyVista + прозрачность + split-screen + звук.
"""

import argparse
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

import numpy as np
from tqdm import tqdm

# ---------- ОБЯЗАТЕЛЬНЫЕ ИМПОРТЫ ПРОЕКТА ----------
from counter import Config, drum_role
from scene import build_scene, Part

try:
    from backend_pv import PVBackend, HAS_PV
except Exception as _e:
    print("PyVista backend не загружен:", _e)
    HAS_PV = False

from cameras import apply_preset, auto_distance, split_screen_multi
from audio import (click, motor_hum, overflow_chime, silence,
                   build_track, save_wav)

try:
    import imageio.v2 as imageio
    HAS_IMAGEIO = True
except ImportError:
    HAS_IMAGEIO = False

log = logging.getLogger("anim")


# ============================================================
#  КОНФИГ АНИМАЦИИ
# ============================================================

@dataclass
class AnimConfig:
    fps: int = 30
    resolution: Tuple[int, int] = (1280, 720)
    duration_explode: float = 2.5
    duration_hold: float = 0.8
    duration_operate: float = 6.0
    duration_disassemble: float = 2.5
    layout: str = "lshape"
    transparent_housing: bool = True
    with_audio: bool = True
    slow_step: bool = True


# ============================================================
#  ПОШАГОВОЕ ВРАЩЕНИЕ БАРАБАНА (36° + overshoot)
# ============================================================

def drum_step_angle(t: float, digit: int, cfg: Config,
                    slow_step: bool) -> float:
    step = 2 * np.pi / cfg.digit_count
    if not slow_step:
        return -step * digit
    total_steps = digit
    local = (t * 10) % 1.0
    done = int(t * 10)
    if done >= total_steps:
        return -step * total_steps
    s = 1 - (1 - local) ** 3
    overshoot = np.exp(-8 * local) * np.sin(20 * local) * 0.08
    return -step * (done + s) + overshoot


# ============================================================
#  ГЕНЕРАЦИЯ ВСЕХ КАДРОВ (батч-склейка, VTK-тихий)
# ============================================================

def render_all(parts, cfg: Config, ac: AnimConfig,
               cameras: List[str], final_value: int):
    backend = PVBackend(resolution=ac.resolution)
    backend.add_parts(parts)

    frames_per_cam: List[List[np.ndarray]] = [[] for _ in cameras] \
        if cameras else [[]]
    audio_events: List[Tuple[int, np.ndarray]] = []
    frame_idx = 0
    n_drums = len(cfg.drum_centers_x())

    # ---------- фаза 1: сборка ----------
    n_explode = int(ac.duration_explode * ac.fps)
    log.info(f"Фаза 1: сборка ({n_explode} кадров, {len(cameras) or 1} камер)")
    for i in tqdm(range(n_explode), desc="сборка"):
        t = i / max(n_explode - 1, 1)
        imgs = _render_one(backend, parts, cfg, ac, "explode", t,
                           cameras=cameras)
        for k, img in enumerate(imgs):
            frames_per_cam[k].append(img)
        if i % 15 == 0:
            audio_events.append((frame_idx, click(1800, 0.04, 0.35)))
        frame_idx += 1

    # ---------- фаза 2: пауза ----------
    n_hold = int(ac.duration_hold * ac.fps)
    for k in range(len(frames_per_cam)):
        last = frames_per_cam[k][-1]
        frames_per_cam[k].extend([last] * n_hold)
    frame_idx += n_hold

    # ---------- фаза 3: работа ----------
    n_oper = int(ac.duration_operate * ac.fps)
    log.info(f"Фаза 3: работа ({n_oper} кадров)")
    prev_total = 0
    for i in tqdm(range(n_oper), desc="работа"):
        t = i / max(n_oper - 1, 1)
        total = int(round(t * final_value))
        values = {"total": total}
        for k in range(n_drums):
            values[f"digit_{k}"] = (total // (10 ** k)) % 10
            prev_d = (prev_total // (10 ** k)) % 10
            values[f"active_{k}"] = (prev_d != values[f"digit_{k}"])

        imgs = _render_one(backend, parts, cfg, ac, "operate", t,
                           values=values, cameras=cameras)
        for k, img in enumerate(imgs):
            frames_per_cam[k].append(img)

        if total != prev_total:
            if ((total // 1) % 10) != ((prev_total // 1) % 10):
                audio_events.append((frame_idx, click(2400, 0.025, 0.3)))
            for k in range(1, n_drums):
                if (prev_total // (10 ** k)) % 10 != (total // (10 ** k)) % 10:
                    audio_events.append((frame_idx, overflow_chime(0.18, 0.28)))
            prev_total = total
        if i % 8 == 0:
            audio_events.append((frame_idx, motor_hum(0.15, 0.03)))
        frame_idx += 1

    # ---------- фаза 4: разборка ----------
    n_dis = int(ac.duration_disassemble * ac.fps)
    log.info(f"Фаза 4: разборка ({n_dis} кадров)")
    for i in tqdm(range(n_dis), desc="разборка"):
        t = i / max(n_dis - 1, 1)
        imgs = _render_one(backend, parts, cfg, ac, "disassemble", t,
                           cameras=cameras)
        for k, img in enumerate(imgs):
            frames_per_cam[k].append(img)
        frame_idx += 1

    backend.close()

    # ---------- склейка ОДИН РАЗ ----------
    if len(cameras) > 1 and ac.layout != "none":
        log.info(f"Split-screen: {ac.layout} ({frame_idx} кадров)")
        frames = split_screen_multi(frames_per_cam,
                                    layout=ac.layout, size=ac.resolution)
    else:
        frames = frames_per_cam[0]

    return frames, audio_events


def _render_one(backend, parts, cfg, ac, mode, t, values=None,
                cameras=None) -> List[np.ndarray]:
    values = values or {}
    transforms = {}
    highlight = None
    transparency = {}

    if mode in ("explode", "disassemble"):
        orders = sorted(set(p.order for p in parts))
        max_order = max(orders) if orders else 1
        tt = t if mode == "explode" else 1 - t
        for p in parts:
            start = p.order / (max_order + 1)
            end = min(start + 0.5, 1.0)
            local = np.clip((tt - start) / max(end - start, 1e-6), 0, 1)
            local = 0.5 - 0.5 * np.cos(np.pi * local)
            transforms[p.name] = p.transformed(local, "explode")
            if 0.05 < local < 0.95:
                highlight = p.name
            if ac.transparent_housing and p.is_transparent and tt > 0.5:
                transparency[p.name] = 0.22

    elif mode == "operate":
        centers = cfg.drum_centers_x()
        drum_names = ["drum_units", "drum_tens", "drum_hundreds", "drum_thousands"]
        pivot_z = cfg.housing_h / 2
        for p in parts:
            if not p.name.startswith("drum_"):
                transforms[p.name] = p.mesh.array() + p.final_offset
                if ac.transparent_housing and p.is_transparent:
                    transparency[p.name] = 0.22
        for i, cx in enumerate(centers):
            name = drum_names[i]
            p = next((x for x in parts if x.name == name), None)
            if p is None:
                continue
            digit = values.get(f"digit_{i}", 0)
            angle = drum_step_angle(t, digit, cfg, ac.slow_step)
            v = p.mesh.array() + p.final_offset - np.array([cx, 0, pivot_z])
            c, s = np.cos(angle), np.sin(angle)
            R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
            v = (v.reshape(-1, 3) @ R.T).reshape(-1, 3, 3) \
                + np.array([cx, 0, pivot_z])
            transforms[name] = v
            if values.get(f"active_{i}", False):
                highlight = name

    backend.update_parts(transforms, highlight=highlight,
                         transparency_override=transparency)

    if mode == "operate":
        backend.add_title(f"РАБОТА   •   значение = {values.get('total', 0):03d}")
    elif mode == "explode":
        backend.add_title("СБОРКА")
    else:
        backend.add_title("РАЗБОРКА")

    imgs = []
    dist = auto_distance(cfg) * 1.6
    if cameras:
        for cam in cameras:
            apply_preset(backend, cam)
            backend.plotter.camera.distance = dist
            backend.plotter.render()
            imgs.append(backend.screenshot())
    else:
        backend.reset_camera(distance=dist)
        imgs.append(backend.screenshot())
    return imgs


# ============================================================
#  СОХРАНЕНИЕ ВИДЕО + ЗВУК
# ============================================================

def save_video(frames, path, fps):
    if not HAS_IMAGEIO:
        log.warning("imageio не установлен — сохраняю PNG-кадры")
        os.makedirs(path + "_frames", exist_ok=True)
        for i, f in enumerate(frames[::max(1, len(frames)//30)]):
            imageio.imsave(f"{path}_frames/f{i:04d}.png", f) \
                if HAS_IMAGEIO else None
        return
    ext = os.path.splitext(path)[1].lower()
    if ext == ".gif":
        imageio.mimsave(path, frames, fps=fps, loop=0)
    elif ext == ".mp4":
        imageio.mimsave(path, frames, fps=fps, codec="libx264",
                        quality=8, macro_block_size=None)
    else:
        imageio.mimsave(path + ".gif", frames, fps=fps, loop=0)
    log.info(f"Видео: {path} ({os.path.getsize(path)/1024/1024:.2f} МБ)")


def mux_audio(video_path, wav_path, out_path):
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-i", wav_path,
             "-c:v", "copy", "-c:a", "aac", "-shortest", out_path],
            check=True, capture_output=True,
        )
        log.info(f"✔ Видео со звуком: {out_path}")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        log.warning(f"ffmpeg недоступен: {e}. Видео без звука.")


# ============================================================
#  CLI
# ============================================================

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )
    p = argparse.ArgumentParser(description="Полный рендер счётчика.")
    p.add_argument("--digits", type=int, default=3, choices=[1, 2, 3, 4])
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--out", default="out/assembly.mp4")
    p.add_argument("--value", type=int, default=None)
    p.add_argument("--layout",
                   choices=["none", "hstack", "vstack", "lshape", "grid"],
                   default="lshape")
    p.add_argument("--no-transparent", action="store_true")
    p.add_argument("--no-audio", action="store_true")
    p.add_argument("--no-step", action="store_true")
    p.add_argument("--fast", action="store_true")
    args = p.parse_args()

    cfg = Config(digits=args.digits)
    ac = AnimConfig(fps=args.fps, layout=args.layout)
    ac.transparent_housing = not args.no_transparent
    ac.with_audio = not args.no_audio
    ac.slow_step = not args.no_step
    if args.fast:
        ac.resolution = (854, 480)
        ac.fps = 20
        ac.duration_operate = 4.0

    final_value = args.value if args.value is not None else 10 ** args.digits - 1

    if not HAS_PV:
        log.error("PyVista не установлен. pip install pyvista vtk")
        return

    cameras = ["iso", "front", "top"] if ac.layout != "none" else []

    log.info(f"Конфиг: {args.digits} разряда, {ac.fps} fps, "
             f"layout={ac.layout}, прозрачность={ac.transparent_housing}, "
             f"звук={ac.with_audio}, финал={final_value}")

    parts = build_scene(cfg)
    t0 = time.time()
    frames, audio_events = render_all(parts, cfg, ac, cameras, final_value)
    log.info(f"Рендер: {len(frames)} кадров за {time.time()-t0:.1f} с "
             f"({(time.time()-t0)/len(frames)*1000:.0f} мс/кадр)")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    save_video(frames, args.out, ac.fps)

    if ac.with_audio and audio_events:
        log.info(f"Звук: {len(audio_events)} событий")
        track = build_track(ac.fps, len(frames), audio_events)
        wav_path = os.path.splitext(args.out)[0] + ".wav"
        save_wav(wav_path, track)
        if args.out.endswith(".mp4"):
            out_with_audio = os.path.splitext(args.out)[0] + "_audio.mp4"
            mux_audio(args.out, wav_path, out_with_audio)

    log.info(f"✔ Готово за {time.time()-t0:.1f} с")


if __name__ == "__main__":
    main()
