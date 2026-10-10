"""Mechanical Counter — генератор STL и аниматор для 3D-печати."""
__version__ = "1.0.0"
__author__ = "Your Name"
__license__ = "MIT"

from .geometry import Config
from .scene import build_scene, Part

__all__ = ["Config", "build_scene", "Part", "__version__"]
