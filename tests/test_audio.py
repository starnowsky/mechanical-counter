"""Audio tests."""

import numpy as np

from counter.audio import build_track, click


def test_click_nonzero():
    s = click()
    assert s.shape[0] > 0
    assert np.abs(s).max() > 0.1


def test_build_track():
    events = [(0, click()), (30, click()), (60, click())]
    track = build_track(fps=30, n_frames=90, events=events)
    assert track.shape[0] > 0
    assert np.abs(track).max() <= 1.0
