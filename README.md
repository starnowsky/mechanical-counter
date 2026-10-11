<div align="center">

# ⚙️ Mechanical Counter

**A mechanical counter for 3D printing — with STL generation, assembly animation, and sound**

[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/starnowsky/mechanical-counter/actions/workflows/ci.yml/badge.svg)](https://github.com/starnowsky/mechanical-counter/actions)
[![PyPI](https://img.shields.io/pypi/v/mechanical-counter.svg)](https://pypi.org/project/mechanical-counter/)

<img src="docs/images/preview.gif" alt="preview" width="720"/>

</div>

---

## ✨ What is it

A complete pipeline for creating a **3D-printable mechanical counter** with three digits (0–999):

| Feature | Command |
|---|---|
| 🖨 **STL generation** of all parts | `mc stl --digits 3` |
| 🎬 **Assembly animation** (PyVista / matplotlib) | `mc animate --layout lshape` |
| 🔊 **Synchronized click sounds** | built into `animate` |
| 📊 **Progress bar, logs, mesh validation** | everywhere |
| 🎥 **Split-screen with 3 cameras** (iso/front/top) | `--layout lshape` |
| 🪟 **Transparent housing** during operation | `--no-transparent` disables |
| 📄 **STEP export** for CAD | `--step` |

## 🎥 Preview

<table>
<tr>
<td><img src="docs/images/assembly.gif" width="320"/></td>
<td><img src="docs/images/operate.gif" width="320"/></td>
</tr>
<tr>
<td align="center">Assembly</td>
<td align="center">Mechanism operation</td>
</tr>
</table>

## 🚀 Installation

### Quick (pip)

```bash
pip install mechanical-counter
```

### From source

```bash
git clone https://github.com/starnowsky/mechanical-counter.git
cd mechanical-counter
pip install -e ".[full]"
```

### Optional components

```bash
pip install mechanical-counter[step]    # +cadquery for STEP
pip install mechanical-counter[audio]   # +sound
pip install mechanical-counter[fast]    # +pyvista for fast rendering
pip install mechanical-counter[all]     # everything
```

## ▶️ Usage

### STL generation

```bash
mc stl --digits 3 --out ./stl
```

Creates `drum_units.stl`, `drum_tens.stl`, `housing.stl`, `cover.stl`,
`axle.stl`, `pawl.stl`, `ratchet_stop.stl`, `plus_button.stl`,
`reset_button.stl` — ready for slicing.

### Animation

```bash
# Full showreel: assembly → operation → disassembly
mc animate --digits 3 --layout lshape --out out/showreel.mp4

# Fast preview render
mc animate --fast

# No sound, no split-screen
mc animate --no-audio --layout none

# Only mechanism operation up to value 137
mc animate --mode operate --value 137
```

### Programmatic use

```python
from counter import Config
from counter.scene import build_scene
from counter.backend_pv import PVBackend

cfg = Config(digits=3)
parts = build_scene(cfg)

backend = PVBackend(resolution=(1280, 720), fast=False)
backend.add_parts(parts)
backend.reset_camera(distance=200)

img = backend.screenshot()
backend.close()
```

## 🧰 Requirements

| Component | Required | Purpose |
|---|---|---|
| Python 3.9+ | ✔ | |
| numpy | ✔ | math |
| numpy-stl | ✔ | STL export |
| tqdm | ✔ | progress bar |
| matplotlib | ○ | fallback rendering, PNG preview |
| pyvista + vtk | ○ | **fast** 3D rendering |
| imageio + ffmpeg | ○ | GIF/MP4 |
| cadquery | ○ | STEP export |
| pillow | ○ | split-screen |

## 🎯 Project structure

```
counter/
├── geometry.py    # counter mesh generation
├── scene.py       # animation scene
├── cameras.py     # cameras + split-screen
├── audio.py       # sound synthesis
├── backend_pv.py  # PyVista renderer (fast)
├── backend_mpl.py # matplotlib renderer (fallback)
└── cli.py         # CLI: stl + animate
```

## 🧪 Tests

```bash
make test           # pytest
make lint           # flake8 + mypy
make format         # black + isort
make ci             # all together
```

## 🖨 Printing and assembly

See [`docs/ASSEMBLY.md`](docs/ASSEMBLY.md) — a step-by-step guide
with photos, a bill of materials, and post-processing.

**In short:**
- Material: **PETG** (springs, buttons) + **PLA** (housing)
- Layer: **0.16 mm**
- Infill: **20%** (springs 40%)
- Supports: **disabled**
- Post-processing: Ø4.1 drill bit for axles, paint for digits

## 📖 Documentation

- [Architecture](docs/ARCHITECTURE.md) — how the code is structured
- [Assembly](docs/ASSEMBLY.md) — printing and mounting
- [Bill of materials](docs/BOM.md) — parts list
- [Troubleshooting](docs/TROUBLESHOOTING.md) — VTK, EGL, ffmpeg

## 🤝 Contributing

PRs welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).
Bugs and ideas — in [Issues](https://github.com/starnowsky/mechanical-counter/issues).

## 📜 License

MIT — do whatever you want. See [LICENSE](LICENSE).

## 🙏 Acknowledgements

- [PyVista](https://pyvista.org) for fast 3D
- [numpy-stl](https://github.com/wolph/numpy-stl) for STL
- Everyone who printed and shared assembly photos

<div align="center">

**[⬆ back to top](#-mechanical-counter)**

</div>
