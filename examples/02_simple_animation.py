"""
Пример: простая анимация без звука и split-screen.

Запуск:
    python examples/02_simple_animation.py
"""
from counter import Config
from counter.scene import build_scene
from counter.backend_pv import PVBackend
import imageio.v2 as imageio
import numpy as np

cfg = Config(digits=3)
parts = build_scene(cfg)

backend = PVBackend(resolution=(640, 480), fast=True)
backend.add_parts(parts)

frames = []
for i in range(60):
    t = i / 59
    # простая интерполяция разлёта
    for p in parts:
        v = p.transformed(t, "explode")
        # обновляем точки
        m = backend._meshes.get(p.name)
        if m is not None:
            m.points = v.reshape(-1, 3)
            m.Modified()
    backend.reset_camera(distance=150)
    frames.append(backend.screenshot())

backend.close()
imageio.mimsave("out/simple.gif", frames, fps=20, loop=0)
print("✔ out/simple.gif")
