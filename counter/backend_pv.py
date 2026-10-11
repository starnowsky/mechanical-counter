#!/usr/bin/env python3
"""PyVista backend (fast off-screen 3D rendering)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from counter.scene import Part

try:
    import pyvista as pv

    HAS_PV = True
except Exception:  # noqa: BLE001
    pv = None  # type: ignore
    HAS_PV = False

log = logging.getLogger("backend_pv")


class PVBackend:
    """Renderer backed by PyVista/VTK."""

    def __init__(self, resolution: Tuple[int, int] = (1280, 720), fast: bool = False):
        if not HAS_PV:
            raise RuntimeError("PyVista is not installed: pip install pyvista vtk")
        self.resolution = resolution
        self.fast = fast
        self._meshes: Dict[str, "pv.PolyData"] = {}
        self._actors: Dict[str, Any] = {}
        self._colors: Dict[str, Tuple[float, float, float]] = {}
        self._opacity: Dict[str, float] = {}
        self._title = None

        pv.OFF_SCREEN = True
        self.plotter = pv.Plotter(off_screen=True, window_size=resolution)
        try:
            self.plotter.renderer.SetMultiSamples(0)
        except Exception:
            pass
        self.plotter.set_background("white")

    def add_parts(self, parts: List[Part]) -> None:
        palette = [
            (0.75, 0.75, 0.78),
            (0.35, 0.55, 0.85),
            (0.85, 0.35, 0.35),
            (0.35, 0.75, 0.45),
            (0.85, 0.65, 0.25),
            (0.55, 0.35, 0.75),
            (0.25, 0.65, 0.75),
        ]
        for i, p in enumerate(parts):
            tris = np.asarray(p.mesh.array(), dtype=float) + p.final_offset
            n = tris.shape[0]
            verts = tris.reshape(-1, 3)
            faces = np.empty((n, 4), dtype=np.int64)
            faces[:, 0] = 3
            faces[:, 1:] = np.arange(n * 3).reshape(n, 3)
            poly = pv.PolyData(verts, faces.ravel())
            color = palette[i % len(palette)]
            opacity = 0.35 if p.is_transparent else 1.0
            actor = self.plotter.add_mesh(
                poly, color=color, opacity=opacity, smooth_shading=True
            )
            self._meshes[p.name] = poly
            self._actors[p.name] = actor
            self._colors[p.name] = color
            self._opacity[p.name] = opacity
        self.reset_camera(distance=200.0)

    def update_parts(
        self,
        transforms: Dict[str, np.ndarray],
        highlight: Optional[str] = None,
        transparency_override: Optional[Dict[str, float]] = None,
    ) -> None:
        transparency_override = transparency_override or {}
        for name, v in transforms.items():
            poly = self._meshes.get(name)
            if poly is None:
                continue
            poly.points = np.asarray(v, dtype=float).reshape(-1, 3)
            poly.Modified()
            actor = self._actors.get(name)
            if actor is None:
                continue
            prop = actor.GetProperty()
            prop.SetOpacity(
                transparency_override.get(name, self._opacity.get(name, 1.0))
            )
            if highlight == name:
                prop.SetColor(1.0, 0.55, 0.0)
            else:
                prop.SetColor(*self._colors.get(name, (0.6, 0.6, 0.6)))

    def reset_camera(self, distance: float = 200.0) -> None:
        self.plotter.reset_camera()
        self.plotter.camera.distance = distance
        self.plotter.camera.focal_point = (0.0, 0.0, 0.0)

    def set_camera(
        self,
        position,
        viewup,
        focal_point: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> None:
        pos = np.asarray(position, dtype=float).tolist()
        self.plotter.camera_position = [pos, list(focal_point), list(viewup)]

    def add_title(self, text: str) -> None:
        if self._title is not None:
            try:
                self.plotter.remove_actor(self._title)
            except Exception:
                pass
        try:
            self._title = self.plotter.add_text(
                text, position="upper_left", font_size=12, color="black"
            )
        except Exception:
            self._title = None

    def screenshot(self) -> np.ndarray:
        return np.asarray(self.plotter.screenshot(transparent_background=False))

    def close(self) -> None:
        try:
            self.plotter.close()
        except Exception:
            pass
