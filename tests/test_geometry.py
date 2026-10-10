"""Тесты геометрии."""
import numpy as np
import pytest
from counter import Config
from counter.geometry import make_box, make_cylinder, make_tube, build_drum


def test_make_box_vertex_count():
    tri = make_box(10, 20, 30)
    assert tri.shape == (12, 3, 3)


def test_make_box_area():
    # коробка 10×10×10, площадь = 6 * 100 = 600
    tri = make_box(10, 10, 10)
    v = tri
    a, b, c = v[:, 0], v[:, 1], v[:, 2]
    cross = np.cross(b - a, c - a)
    area = 0.5 * np.linalg.norm(cross, axis=1).sum()
    assert abs(area - 600) < 1e-6


def test_make_cylinder_area():
    r, h = 5.0, 10.0
    tri = make_cylinder(r, h, segments=128)
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    cross = np.cross(b - a, c - a)
    area = 0.5 * np.linalg.norm(cross, axis=1).sum()
    # площадь цилиндра: 2πrh + 2πr²
    expected = 2 * np.pi * r * h + 2 * np.pi * r ** 2
    assert abs(area - expected) / expected < 0.01


def test_tube_manifold():
    from counter.geometry import Mesh
    m = Mesh()
    m.add(make_tube(10, 6, 20, segments=64))
    ok, bad = m.is_manifold()
    assert ok, f"{bad} висячих рёбер"


@pytest.mark.parametrize("digits", [1, 2, 3, 4])
def test_drum_all_digit_counts(digits):
    cfg = Config(digits=digits)
    for i in range(digits):
        from counter.geometry import drum_role
        role = drum_role(i, digits)
        m = build_drum(cfg, role)
        assert len(m) > 0
