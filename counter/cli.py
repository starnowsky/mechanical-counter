#!/usr/bin/env python3
from __future__ import annotations

"""
Full render pipeline: PyVista + transparency + split-screen + sound.
"""

import argparse
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from tqdm import tqdm

# ---------- PROJECT IMPORTS ----------
from counter import Config, __version__
from counter.scene import build_scene

try:
    from counter.backend_pv import HAS_PV, PVBackend
except Exception as _e:
    print("PyVista backend failed to load:", _e)
    HAS_PV = False

from counter.audio import build_track, click, motor_hum, overflow_chime, save_wav
from counter.cameras import apply_preset, auto_distance, split_screen_multi

try:
    import imageio.v2 as imageio

    HAS_IMAGEIO = True
except ImportError:
    HAS_IMAGEIO = False

log = logging.getLogger("anim")


# ============================================================
#  ANIMATION CONFIG
# ============================================================


@dataclass
class AnimConfig:
    fps: int = 30
    resolution: Tuple[int, int] = (1280, 720)
    duration_explode: float = 2.5
    duration_hold: float = 0.8
    duration_operate: float = 6.0
    duration_disassemble: float = 2.5
    layout: str = "lshape"
    transparent_housing: bool = True
    with_audio: bool = True
    slow_step: bool = True


# ============================================================
#  STEPWISE DRUM ROTATION (36° + overshoot)
# ============================================================


def drum_step_angle(t: float, digit: int, cfg: Config, slow_step: bool) -> float:
    step = 2 * np.pi / cfg.digit_count
    if not slow_step:
        return -step * digit
    total_steps = digit
    local = (t * 10) % 1.0
    done = int(t * 10)
    if done >= total_steps:
        return -step * total_steps
    s = 1 - (1 - local) ** 3
    overshoot = np.exp(-8 * local) * np.sin(20 * local) * 0.08
    return -step * (done + s) + overshoot


# ============================================================
#  FRAME GENERATION (batched compositing, quiet VTK)
# ============================================================


def render_all(
    parts, cfg: Config, ac: AnimConfig, cameras: List[str], final_value: int
):
    backend = PVBackend(resolution=ac.resolution)
    backend.add_parts(parts)

    frames_per_cam: List[List[np.ndarray]] = [[] for _ in cameras] if cameras else [[]]
    audio_events: List[Tuple[int, np.ndarray]] = []
    frame_idx = 0
    n_drums = len(cfg.drum_centers_x())

    # ---------- phase 1: assembly ----------
    n_explode = int(ac.duration_explode * ac.fps)
    log.info(f"Phase 1: assembly ({n_explode} frames, {len(cameras) or 1} camera(s))")
    for i in tqdm(range(n_explode), desc="assembly"):
        t = i / max(n_explode - 1, 1)
        imgs = _render_one(backend, parts, cfg, ac, "explode", t, cameras=cameras)
        for k, img in enumerate(imgs):
            frames_per_cam[k].append(img)
        if i % 15 == 0:
            audio_events.append((frame_idx, click(1800, 0.04, 0.35)))
        frame_idx += 1

    # ---------- phase 2: hold ----------
    n_hold = int(ac.duration_hold * ac.fps)
    for k in range(len(frames_per_cam)):
        last = frames_per_cam[k][-1]
        frames_per_cam[k].extend([last] * n_hold)
    frame_idx += n_hold

    # ---------- phase 3: operation ----------
    n_oper = int(ac.duration_operate * ac.fps)
    log.info(f"Phase 3: operation ({n_oper} frames)")
    prev_total = 0
    for i in tqdm(range(n_oper), desc="operation"):
        t = i / max(n_oper - 1, 1)
        total = int(round(t * final_value))
        values = {"total": total}
        for k in range(n_drums):
            values[f"digit_{k}"] = (total // (10**k)) % 10
            prev_d = (prev_total // (10**k)) % 10
            values[f"active_{k}"] = prev_d != values[f"digit_{k}"]

        imgs = _render_one(
            backend, parts, cfg, ac, "operate", t, values=values, cameras=cameras
        )
        for k, img in enumerate(imgs):
            frames_per_cam[k].append(img)

        if total != prev_total:
            if ((total // 1) % 10) != ((prev_total // 1) % 10):
                audio_events.append((frame_idx, click(2400, 0.025, 0.3)))
            for k in range(1, n_drums):
                if (prev_total // (10**k)) % 10 != (total // (10**k)) % 10:
                    audio_events.append((frame_idx, overflow_chime(0.18, 0.28)))
            prev_total = total
        if i % 8 == 0:
            audio_events.append((frame_idx, motor_hum(0.15, 0.03)))
        frame_idx += 1

    # ---------- phase 4: disassembly ----------
    n_dis = int(ac.duration_disassemble * ac.fps)
    log.info(f"Phase 4: disassembly ({n_dis} frames)")
    for i in tqdm(range(n_dis), desc="disassembly"):
        t = i / max(n_dis - 1, 1)
        imgs = _render_one(backend, parts, cfg, ac, "disassemble", t, cameras=cameras)
        for k, img in enumerate(imgs):
            frames_per_cam[k].append(img)
        frame_idx += 1

    backend.close()

    # ---------- composite ONCE ----------
    if len(cameras) > 1 and ac.layout != "none":
        log.info(f"Split-screen: {ac.layout} ({frame_idx} frames)")
        frames = split_screen_multi(
            frames_per_cam, layout=ac.layout, size=ac.resolution
        )
    else:
        frames = frames_per_cam[0]

    return frames, audio_events


def _render_one(
    backend, parts, cfg, ac, mode, t, values=None, cameras=None
) -> List[np.ndarray]:
    values = values or {}
    transforms = {}
    highlight = None
    transparency = {}

    if mode in ("explode", "disassemble"):
        orders = sorted(set(p.order for p in parts))
        max_order = max(orders) if orders else 1
        tt = t if mode == "explode" else 1 - t
        for p in parts:
            start = p.order / (max_order + 1)
            end = min(start + 0.5, 1.0)
            local = np.clip((tt - start) / max(end - start, 1e-6), 0, 1)
            local = 0.5 - 0.5 * np.cos(np.pi * local)
            transforms[p.name] = p.transformed(local, "explode")
            if 0.05 < local < 0.95:
                highlight = p.name
            if ac.transparent_housing and p.is_transparent and tt > 0.5:
                transparency[p.name] = 0.22

    elif mode == "operate":
        centers = cfg.drum_centers_x()
        drum_names = ["drum_units", "drum_tens", "drum_hundreds", "drum_thousands"]
        pivot_z = cfg.housing_h / 2
        for p in parts:
            if not p.name.startswith("drum_"):
                transforms[p.name] = p.mesh.array() + p.final_offset
                if ac.transparent_housing and p.is_transparent:
                    transparency[p.name] = 0.22
        for i, cx in enumerate(centers):
            name = drum_names[i]
            p = next((x for x in parts if x.name == name), None)
            if p is None:
                continue
            digit = values.get(f"digit_{i}", 0)
            angle = drum_step_angle(t, digit, cfg, ac.slow_step)
            v = p.mesh.array() + p.final_offset - np.array([cx, 0, pivot_z])
            c, s = np.cos(angle), np.sin(angle)
            R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
            v = (v.reshape(-1, 3) @ R.T).reshape(-1, 3, 3) + np.array([cx, 0, pivot_z])
            transforms[name] = v
            if values.get(f"active_{i}", False):
                highlight = name

    backend.update_parts(
        transforms, highlight=highlight, transparency_override=transparency
    )

    if mode == "operate":
        backend.add_title(f"OPERATION   •   value = {values.get('total', 0):03d}")
    elif mode == "explode":
        backend.add_title("ASSEMBLY")
    else:
        backend.add_title("DISASSEMBLY")

    imgs = []
    dist = auto_distance(cfg) * 1.6
    if cameras:
        for cam in cameras:
            apply_preset(backend, cam)
            backend.plotter.camera.distance = dist
            backend.plotter.render()
            imgs.append(backend.screenshot())
    else:
        backend.reset_camera(distance=dist)
        imgs.append(backend.screenshot())
    return imgs


# ============================================================
#  VIDEO + AUDIO SAVING
# ============================================================


def save_video(frames, path, fps):
    if not HAS_IMAGEIO:
        log.warning("imageio is not installed — saving PNG frames")
        os.makedirs(path + "_frames", exist_ok=True)
        for i, f in enumerate(frames[:: max(1, len(frames) // 30)]):
            imageio.imsave(f"{path}_frames/f{i:04d}.png", f) if HAS_IMAGEIO else None
        return
    ext = os.path.splitext(path)[1].lower()
    if ext == ".gif":
        imageio.mimsave(path, frames, fps=fps, loop=0)
    elif ext == ".mp4":
        imageio.mimsave(
            path, frames, fps=fps, codec="libx264", quality=8, macro_block_size=None
        )
    else:
        imageio.mimsave(path + ".gif", frames, fps=fps, loop=0)
    log.info(f"Video: {path} ({os.path.getsize(path)/1024/1024:.2f} MB)")


def mux_audio(video_path, wav_path, out_path):
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                video_path,
                "-i",
                wav_path,
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                out_path,
            ],
            check=True,
            capture_output=True,
        )
        log.info(f"✔ Video with audio: {out_path}")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        log.warning(f"ffmpeg unavailable: {e}. Video will have no audio.")


# ============================================================
#  CLI
# ============================================================


def run_animation(
    cfg: Config,
    ac: AnimConfig,
    out: str = "out/showcase.mp4",
    final_value: Optional[int] = None,
) -> str:
    """Full pipeline: scene → frames → video (+ audio)."""
    if not HAS_PV:
        raise RuntimeError("PyVista is not installed. pip install pyvista vtk")

    if final_value is None:
        final_value = 10**cfg.digits - 1

    cameras = ["iso", "front", "top"] if ac.layout != "none" else []
    parts = build_scene(cfg)

    t0 = time.time()
    frames, audio_events = render_all(parts, cfg, ac, cameras, final_value)
    log.info(
        f"Render: {len(frames)} frames in {time.time()-t0:.1f} s "
        f"({(time.time()-t0)/len(frames)*1000:.0f} ms/frame)"
    )

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    save_video(frames, out, ac.fps)

    if ac.with_audio and audio_events:
        log.info(f"Audio: {len(audio_events)} events")
        track = build_track(ac.fps, len(frames), audio_events)
        wav_path = os.path.splitext(out)[0] + ".wav"
        save_wav(wav_path, track)
        if out.endswith(".mp4"):
            out_with_audio = os.path.splitext(out)[0] + "_audio.mp4"
            mux_audio(out, wav_path, out_with_audio)

    log.info(f"✔ Done in {time.time()-t0:.1f} s")
    return out


def cmd_stl(args: argparse.Namespace) -> None:
    from counter.geometry import SCHEME, run_stl

    if args.scheme:
        print(SCHEME)
        return
    run_stl(
        digits=args.digits,
        out=args.out,
        make_step=not args.no_step,
        make_png=args.png,
        quiet=args.quiet,
    )


def cmd_animate(args: argparse.Namespace) -> None:
    cfg = Config(digits=args.digits)
    ac = AnimConfig(fps=args.fps, layout=args.layout)
    ac.transparent_housing = not args.no_transparent
    ac.with_audio = not args.no_audio
    ac.slow_step = not args.no_step
    if args.fast:
        ac.resolution = (854, 480)
        ac.fps = 20
        ac.duration_operate = 4.0

    final_value = args.value if args.value is not None else 10**args.digits - 1

    log.info(
        f"Config: {args.digits} digits, {ac.fps} fps, "
        f"layout={ac.layout}, transparency={ac.transparent_housing}, "
        f"audio={ac.with_audio}, final={final_value}"
    )

    run_animation(cfg, ac, out=args.out, final_value=final_value)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mc",
        description="Mechanical counter: STL generation and assembly animation.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = p.add_subparsers(dest="command", required=True)

    ps = sub.add_parser("stl", help="Generate STL for all parts")
    ps.add_argument("--digits", type=int, default=3, choices=[1, 2, 3, 4])
    ps.add_argument("--out", default="stl", help="Output folder for STL files")
    ps.add_argument("--no-step", action="store_true", help="Do not export STEP")
    ps.add_argument("--png", action="store_true", help="Save PNG preview")
    ps.add_argument("--scheme", action="store_true", help="Show assembly diagram")
    ps.add_argument("-q", "--quiet", action="store_true", help="Less logging")
    ps.set_defaults(func=cmd_stl)

    pa = sub.add_parser("animate", help="Assembly / mechanism operation animation")
    pa.add_argument("--digits", type=int, default=3, choices=[1, 2, 3, 4])
    pa.add_argument("--fps", type=int, default=30)
    pa.add_argument("--out", default="out/assembly.mp4")
    pa.add_argument("--value", type=int, default=None)
    pa.add_argument(
        "--layout",
        choices=["none", "hstack", "vstack", "lshape", "grid"],
        default="lshape",
    )
    pa.add_argument("--no-transparent", action="store_true")
    pa.add_argument("--no-audio", action="store_true")
    pa.add_argument("--no-step", action="store_true")
    pa.add_argument("--fast", action="store_true")
    pa.set_defaults(func=cmd_animate)

    return p


def main(argv: Optional[List[str]] = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
