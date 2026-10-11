#!/usr/bin/env python3
"""Синтез звуков для анимации (щёлчки, гул, сигнал переполнения)."""

from __future__ import annotations

import wave
from typing import List, Tuple

import numpy as np

SAMPLE_RATE = 44100


def _envelope(n: int, decay: float = 8.0) -> np.ndarray:
    t = np.linspace(0.0, 1.0, n, endpoint=False)
    return np.exp(-decay * t)


def click(freq: float = 2400.0, dur: float = 0.03, vol: float = 0.35) -> np.ndarray:
    """Короткий щелчок."""
    n = max(int(SAMPLE_RATE * dur), 1)
    t = np.arange(n) / SAMPLE_RATE
    wave = np.sin(2 * np.pi * freq * t)
    return (vol * wave * _envelope(n)).astype(np.float32)


def motor_hum(dur: float = 0.15, vol: float = 0.03) -> np.ndarray:
    """Низкочастотный гул мотора."""
    n = max(int(SAMPLE_RATE * dur), 1)
    t = np.arange(n) / SAMPLE_RATE
    wave = np.sin(2 * np.pi * 110.0 * t) + 0.5 * np.sin(2 * np.pi * 220.0 * t)
    return (vol * wave * _envelope(n, decay=3.0)).astype(np.float32)


def overflow_chime(dur: float = 0.18, vol: float = 0.28) -> np.ndarray:
    """Сигнал переполнения разряда (двухтоновый)."""
    n = max(int(SAMPLE_RATE * dur), 1)
    t = np.arange(n) / SAMPLE_RATE
    wave = np.sin(2 * np.pi * 880.0 * t) + np.sin(2 * np.pi * 1320.0 * t)
    return (vol * wave * _envelope(n, decay=6.0)).astype(np.float32)


def silence(dur: float = 0.1) -> np.ndarray:
    """Тишина заданной длительности."""
    return np.zeros(max(int(SAMPLE_RATE * dur), 1), dtype=np.float32)


def build_track(
    fps: int, n_frames: int, events: List[Tuple[int, np.ndarray]]
) -> np.ndarray:
    """Раскладывает события (номер_кадра, сэмплы) на общую дорожку."""
    total = max(int(SAMPLE_RATE * n_frames / fps), 1)
    track: np.ndarray = np.zeros(total, dtype=np.float32)
    for frame, samples in events:
        samples = np.asarray(samples, dtype=np.float32)
        start = int(frame / fps * SAMPLE_RATE)
        if start >= total or len(samples) == 0:
            continue
        end = min(start + len(samples), total)
        if end > start:
            track[start:end] += samples[: end - start]
    peak = float(np.abs(track).max()) if len(track) else 0.0
    if peak > 1.0:
        track = track * np.float32(1.0 / peak)
    return track


def save_wav(path: str, track: np.ndarray) -> None:
    """Сохраняет дорожку в WAV (16 бит, моно)."""
    data = np.clip(np.asarray(track, dtype=np.float32), -1.0, 1.0)
    pcm = (data * 32767.0).astype(np.int16)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.tobytes())
