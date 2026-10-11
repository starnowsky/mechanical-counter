"""Тесты сцены."""

from counter import Config
from counter.scene import build_scene


def test_scene_has_all_parts():
    cfg = Config(digits=3)
    parts = build_scene(cfg)
    names = {p.name for p in parts}
    assert "housing" in names
    assert "cover" in names
    assert "axle" in names
    assert "drum_units" in names
    assert "drum_tens" in names
    assert "drum_hundreds" in names


def test_scene_part_count():
    cfg = Config(digits=3)
    parts = build_scene(cfg)
    assert len(parts) == 11  # 3 барабана + 8 деталей
