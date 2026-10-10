"""
Пример: генерация STL всех деталей счётчика.

Запуск:
    python examples/01_generate_stl.py
"""
from counter import Config
from counter.geometry import build_all

cfg = Config(digits=3)
build_all(cfg, out_dir="./stl", make_step=False, make_png=False)
print("✔ STL готовы в ./stl")
