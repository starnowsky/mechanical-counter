#!/usr/bin/env python3
"""matplotlib fallback-бэкенд (работает без GPU)."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

from counter.scene import Part

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    HAS_MPL = True
except Exception:  # noqa: BLE001
    HAS_MPL = False

log = logging.getLogger("backend_mpl")


class MPLBackend:
    """Медленный, но везде работающий рендер на matplotlib."""

    def __init__(self, resolution: Tuple[int, int] = (1280, 720), fast: bool = False):
        if not HAS_MPL:
            raise RuntimeError("matplotlib не установлен")
        self.resolution = resolution
        self._meshes: Dict[str, np.ndarray] = {}
        self._transparent: set[str] = set()
        self._highlight: Optional[str] = None
        self._title = ""
        self.fig = plt.figure(
            figsize=(resolution[0] / 100, resolution[1] / 100), dpi=100
        )
        self.ax = self.fig.add_subplot(111, projection="3d")

    def add_parts(self, parts: List[Part]) -> None:
        for p in parts:
            self._meshes[p.name] = np.asarray(p.mesh.array()) + p.final_offset
            if p.is_transparent:
                self._transparent.add(p.name)
        self.reset_camera(200.0)

    def update_parts(
        self,
        transforms: Dict[str, np.ndarray],
        highlight: Optional[str] = None,
        transparency_override: Optional[Dict[str, float]] = None,
    ) -> None:
        for name, v in transforms.items():
            if name in self._meshes:
                self._meshes[name] = np.asarray(v, dtype=float)
        self._highlight = highlight

    def reset_camera(self, distance: float = 200.0) -> None:
        pass

    def set_camera(
        self,
        position,
        viewup,
        focal_point: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> None:
        self.ax.view_init(elev=30, azim=-60)

    def add_title(self, text: str) -> None:
        self._title = text

    def screenshot(self) -> np.ndarray:
        self.ax.clear()
        for name, tris in self._meshes.items():
            alpha = 0.3 if name in self._transparent else 0.9
            pc = Poly3DCollection(tris, alpha=alpha, edgecolor="k", linewidths=0.05)
            if self._highlight == name:
                pc.set_facecolor("#ff8c00")
            else:
                pc.set_facecolor("#7fb3d5")
            self.ax.add_collection3d(pc)

        if self._meshes:
            all_pts = np.concatenate(
                [t.reshape(-1, 3) for t in self._meshes.values()], axis=0
            )
        else:
            all_pts = np.zeros((1, 3))
        mn = all_pts.min(axis=0)
        mx = all_pts.max(axis=0)
        center = (mn + mx) / 2
        radius = max(float((mx - mn).max()) / 2, 1.0) * 1.1
        for axis, getter in (
            ("x", self.ax.set_xlim),
            ("y", self.ax.set_ylim),
            ("z", self.ax.set_zlim),
        ):
            getter(
                center[["x", "y", "z"].index(axis)] - radius,
                center[["x", "y", "z"].index(axis)] + radius,
            )
        self.ax.set_box_aspect((1, 1, 1))
        if self._title:
            self.ax.set_title(self._title)
        self.fig.canvas.draw()
        buf = np.asarray(self.fig.canvas.buffer_rgba(), dtype=np.uint8)
        return buf[:, :, :3].copy()

    def close(self) -> None:
        plt.close(self.fig)
