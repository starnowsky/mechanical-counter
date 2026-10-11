#!/usr/bin/env python3
"""Сцена для анимации: детали счётчика с двумя позициями."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from counter.geometry import (
    Config,
    Mesh,
    build_axle,
    build_cover,
    build_drum,
    build_housing,
    build_pawl,
    build_plus_button,
    build_ratchet_stop,
    build_reset_button,
    build_ring,
    drum_role,
)


@dataclass
class Part:
    """Деталь с собранной и «разлетевшейся» позициями."""

    name: str
    mesh: Mesh
    final_offset: np.ndarray
    explode_offset: np.ndarray
    order: int = 0
    is_transparent: bool = False

    def transformed(self, t: float, mode: str = "explode") -> np.ndarray:
        """Позиция детали во время t (N, 3, 3).

        mode="explode":   t=0 → разлёт, t=1 → сборка.
        mode="disassemble": t=0 → сборка, t=1 → разлёт.
        """
        if mode == "disassemble":
            k = float(t)
        else:
            k = 1.0 - float(t)
        return self.mesh.array() + self.final_offset + self.explode_offset * k


def _drum_explode_offsets(n: int) -> List[np.ndarray]:
    """Векторы разлёта для N барабанов (веером вверх по Z)."""
    return [np.array([0.0, 0.0, 24.0 + 8.0 * i]) for i in range(n)]


def build_scene(cfg: Config) -> List[Part]:
    """Собирает список деталей для анимации (11 деталей для 3 разрядов)."""
    centers = cfg.drum_centers_x()
    pivot_z = cfg.housing_h / 2.0
    drum_names = ["drum_units", "drum_tens", "drum_hundreds", "drum_thousands"]
    parts: List[Part] = []

    parts.append(
        Part(
            name="housing",
            mesh=build_housing(cfg),
            final_offset=np.zeros(3),
            explode_offset=np.zeros(3),
            order=0,
            is_transparent=True,
        )
    )

    parts.append(
        Part(
            name="axle",
            mesh=build_axle(cfg),
            final_offset=np.zeros(3),
            explode_offset=np.array([0.0, -40.0, 0.0]),
            order=1,
        )
    )

    offsets = _drum_explode_offsets(len(centers))
    for i, (cx, off) in enumerate(zip(centers, offsets)):
        role = drum_role(i, len(centers))
        name = drum_names[i] if i < len(drum_names) else f"drum_{i}"
        final = np.array([cx, 0.0, pivot_z - cfg.drum_length / 2.0])
        parts.append(
            Part(
                name=name,
                mesh=build_drum(cfg, role),
                final_offset=final,
                explode_offset=off,
                order=2 + i,
            )
        )

    parts.append(
        Part(
            name="pawl",
            mesh=build_pawl(cfg),
            final_offset=np.zeros(3),
            explode_offset=np.array([0.0, 36.0, 0.0]),
            order=3,
        )
    )
    parts.append(
        Part(
            name="ratchet_stop",
            mesh=build_ratchet_stop(cfg),
            final_offset=np.zeros(3),
            explode_offset=np.array([0.0, 46.0, 0.0]),
            order=3,
        )
    )
    parts.append(
        Part(
            name="ring",
            mesh=build_ring(cfg),
            final_offset=np.zeros(3),
            explode_offset=np.array([40.0, 0.0, 0.0]),
            order=4,
        )
    )
    parts.append(
        Part(
            name="cover",
            mesh=build_cover(cfg),
            final_offset=np.zeros(3),
            explode_offset=np.array([0.0, 0.0, 60.0]),
            order=5,
            is_transparent=True,
        )
    )
    parts.append(
        Part(
            name="plus_button",
            mesh=build_plus_button(cfg),
            final_offset=np.zeros(3),
            explode_offset=np.array([0.0, 0.0, 70.0]),
            order=6,
        )
    )
    parts.append(
        Part(
            name="reset_button",
            mesh=build_reset_button(cfg),
            final_offset=np.zeros(3),
            explode_offset=np.array([0.0, 0.0, 80.0]),
            order=6,
        )
    )

    return parts
