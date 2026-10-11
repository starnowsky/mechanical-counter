#!/usr/bin/env python3
"""Camera presets and split-screen frame compositing."""

from __future__ import annotations

from typing import List, Sequence, Tuple

import numpy as np

from counter.geometry import Config

PRESETS = {
    "iso": ((1.0, 1.0, 1.0), (0.0, 0.0, 1.0)),
    "front": ((0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
    "top": ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
    "side": ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
}


def apply_preset(backend, preset: str = "iso") -> None:
    """Point the camera at a preset (iso/front/top/side)."""
    position, viewup = PRESETS.get(preset, PRESETS["iso"])
    backend.set_camera(position=position, viewup=viewup, focal_point=(0.0, 0.0, 0.0))


def auto_distance(cfg: Config) -> float:
    """Pick a camera distance based on the scene bounds."""
    size = max(cfg.housing_w, cfg.housing_d, cfg.housing_h)
    return size * 1.8 + 60.0


def _as_rgb(img: np.ndarray) -> np.ndarray:
    img = np.asarray(img)
    if img.ndim == 2:
        return np.stack([img, img, img], axis=-1)
    if img.shape[2] == 4:
        return img[:, :, :3]
    return img


def _resize(img: np.ndarray, tw: int, th: int) -> np.ndarray:
    """Fast nearest-neighbor resize."""
    img = _as_rgb(img)
    ih, iw = img.shape[:2]
    if ih == 0 or iw == 0 or tw <= 0 or th <= 0:
        return np.zeros((th, tw, 3), dtype=np.uint8)
    ys = np.linspace(0, ih - 1, th).round().astype(int)
    xs = np.linspace(0, iw - 1, tw).round().astype(int)
    return img[np.ix_(ys, xs)].astype(np.uint8)


def split_screen_multi(
    frames_per_cam: Sequence[Sequence[np.ndarray]],
    layout: str = "lshape",
    size: Tuple[int, int] = (1280, 720),
) -> List[np.ndarray]:
    """Composite frames from several cameras (lshape/hstack/vstack/grid)."""
    n_cams = len(frames_per_cam)
    if n_cams == 0:
        return []
    n_frames = len(frames_per_cam[0])
    w, h = int(size[0]), int(size[1])
    out: List[np.ndarray] = []

    for i in range(n_frames):
        imgs = [_as_rgb(frames_per_cam[c][i]) for c in range(n_cams)]
        canvas = np.zeros((h, w, 3), dtype=np.uint8)

        if layout == "hstack":
            cw = w // n_cams
            for c, im in enumerate(imgs):
                canvas[:, c * cw : (c + 1) * cw] = _resize(im, cw, h)
        elif layout == "vstack":
            ch = h // n_cams
            for c, im in enumerate(imgs):
                canvas[c * ch : (c + 1) * ch, :] = _resize(im, w, ch)
        elif layout == "grid":
            cols = 2
            cw, ch = w // cols, h // cols
            for c, im in enumerate(imgs[:4]):
                row, col = divmod(c, cols)
                canvas[row * ch : (row + 1) * ch, col * cw : (col + 1) * cw] = _resize(
                    im, cw, ch
                )
        else:  # lshape
            if n_cams >= 3:
                left_w = w // 2
                canvas[:, :left_w] = _resize(imgs[0], left_w, h)
                right_w = w - left_w
                rh = h // 2
                canvas[:rh, left_w:] = _resize(imgs[1], right_w, rh)
                canvas[rh:, left_w:] = _resize(imgs[2], right_w, h - rh)
            elif n_cams == 2:
                left_w = w // 2
                canvas[:, :left_w] = _resize(imgs[0], left_w, h)
                canvas[:, left_w:] = _resize(imgs[1], w - left_w, h)
            else:
                canvas = _resize(imgs[0], w, h)

        out.append(canvas)
    return out
