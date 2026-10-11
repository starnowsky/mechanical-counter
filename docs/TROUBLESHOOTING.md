# Troubleshooting

## PyVista / VTK

### `Attempt to set draw buffers from a Framebuffer Object that is not bound`

**Cause:** VTK 9.3 on Linux + MSAA.

**Solution:**
```python
pv.Plotter(multi_samples=0)   # ← disable MSAA
# or
plotter.renderer.SetMultiSamples(0)
```

### `module 'vtk' has no attribute 'util'`

**Cause:** newer VTK does not import `vtk.util` automatically.

**Solution:**
```python
import vtk
from vtk.util import numpy_support   # ← explicitly
```

### `Plotter.__init__() got an unexpected keyword argument 'multi_samples'`

**Cause:** PyVista 0.44+ removed the parameter.

**Solution:**
```python
self.plotter = pv.Plotter(off_screen=True, window_size=resolution)
self.plotter.renderer.SetMultiSamples(0)
```

### Black image

**Solution:**
```bash
export VTK_DEFAULT_OPENGL_WINDOW=vtkEGLRenderWindow
export LIBGL_ALWAYS_SOFTWARE=1
```

Or via `xvfb`:
```bash
xvfb-run -a -s "-screen 0 1280x720x24" mc animate --fast
```

### Rendering is very slow (>100 ms/frame)

**Cause:** CPU rendering (Mesa llvmpipe) instead of GPU.

**Solution:**
```bash
# check
python -c "import pyvista as pv; pv.OFF_SCREEN=True; p=pv.Plotter(); print(p.ren_win.GetClassName())"

# should be vtkEGLRenderWindow or vtkXOpenGLRenderWindow
```

If `vtkOSOpenGLRenderWindow` — install:
```bash
apt install libegl1-mesa libgl1-mesa-dri
export VTK_DEFAULT_OPENGL_WINDOW=vtkEGLRenderWindow
```

## FFmpeg

### `ffmpeg: command not found`

```bash
apt install ffmpeg        # Linux
brew install ffmpeg       # macOS
```

### MP4 is not created

Check:
```bash
ffmpeg -codecs | grep libx264
```

If empty — reinstall with the `--enable-libx264` flag.

## Python

### `NameError: name 'Config' is not defined`

Check the imports at the top of the file:
```python
from counter import Config
```

### `ModuleNotFoundError: No module named 'counter'`

```bash
pip install -e .
# or
cd counter_project
python -m counter --help
```

## Printing

### Drums do not rotate

- Check the drum-axle clearance: should be 0.15–0.2 mm
- Grease the axle with PTFE
- Ream the hole with a drill bit 0.1 mm larger

### Digits are hard to read

- Print the drums in **white** PETG
- Fill the recessed digits with black paint
- Or vice versa — print black, paint white
