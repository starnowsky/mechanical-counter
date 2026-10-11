"""
Example: simple animation without sound and split-screen.

Run:
    python examples/02_simple_animation.py
"""

import imageio.v2 as imageio

from counter import Config
from counter.backend_pv import PVBackend
from counter.scene import build_scene

cfg = Config(digits=3)
parts = build_scene(cfg)

backend = PVBackend(resolution=(640, 480), fast=True)
backend.add_parts(parts)

frames = []
for i in range(60):
    t = i / 59
    # simple exploded-position interpolation
    for p in parts:
        v = p.transformed(t, "explode")
        # update the points
        m = backend._meshes.get(p.name)
        if m is not None:
            m.points = v.reshape(-1, 3)
            m.Modified()
    backend.reset_camera(distance=150)
    frames.append(backend.screenshot())

backend.close()
imageio.mimsave("out/simple.gif", frames, fps=20, loop=0)
print("✔ out/simple.gif")
