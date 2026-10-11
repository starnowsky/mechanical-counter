"""Mechanical Counter — STL generator and animator for 3D printing."""

__version__ = "1.0.0"
__author__ = "Your Name"
__license__ = "MIT"

from .geometry import Config, drum_role
from .scene import Part, build_scene

__all__ = ["Config", "drum_role", "build_scene", "Part", "__version__"]
