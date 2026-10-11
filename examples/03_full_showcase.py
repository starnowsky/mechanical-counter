"""
Example: full render with split-screen and sound.

Run:
    python examples/03_full_showcase.py
"""

from counter import Config
from counter.cli import run_animation
from counter.cli_animate import AnimConfig

cfg = Config(digits=3)
ac = AnimConfig(
    fps=24,
    resolution=(1280, 720),
    layout="lshape",
    transparent_housing=True,
    with_audio=True,
    slow_step=True,
)

run_animation(cfg, ac, out="out/showcase.mp4")
print("✔ out/showcase.mp4")
