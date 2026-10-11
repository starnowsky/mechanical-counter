# Architecture

## Overview

```
┌─────────────────┐
│   CLI (mc)      │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌────────┐
│  stl  │ │animate │
└───┬───┘ └───┬────┘
    │         │
    ▼         ▼
┌───────┐ ┌──────────────┐
│geometry│ │   scene      │
└───────┘ └──────┬───────┘
                 │
            ┌────┴────┬────────┬────────┐
            ▼         ▼        ▼        ▼
       ┌────────┐┌────────┐┌───────┐┌───────┐
       │backend ││backend ││camera ││audio  │
       │  _pv   ││  _mpl  ││       ││       │
       └────────┘└────────┘└───────┘└───────┘
```

## Modules

### `geometry.py`
- `Config` — dataclass with all dimensions
- `Mesh` — triangle container with cache
- `make_box`, `make_cylinder`, `make_tube`, `make_torus` — primitives
- `build_drum`, `build_housing`, `build_cover`, ... — part assembly

### `scene.py`
- `Part` — a part with two positions (assembled / exploded)
- `build_scene(cfg)` — builds the animation scene

### `backend_pv.py` (fast)
- PyVista + VTK, PBR materials, SSAO, shadows
- Three fallback levels in `screenshot()`

### `backend_mpl.py` (fallback)
- matplotlib 3D, works everywhere
- 15× slower, but no GPU required

### `cameras.py`
- Presets: iso / front / top / side
- `split_screen_multi` — L-shape, hstack, vstack, grid

### `audio.py`
- Synthesizes `click`, `motor_hum`, `overflow_chime`
- `build_track` — assembles a WAV track

## Data flow

1. `Config` → `build_scene` → `List[Part]`
2. `Part` + `t` → `transformed(t, mode)` → `np.ndarray(N,3,3)`
3. `backend.update_parts(transforms)` → updates VTK actors
4. `backend.screenshot()` → RGB frame
5. List of frames → `imageio.mimsave` → MP4/GIF
6. `audio.build_track(events)` → WAV
7. `ffmpeg` → mux video + sound
