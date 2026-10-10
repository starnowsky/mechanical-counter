# Troubleshooting

## PyVista / VTK

### `Attempt to set draw buffers from a Framebuffer Object that is not bound`

**Причина:** VTK 9.3 на Linux + MSAA.

**Решение:**
```python
pv.Plotter(multi_samples=0)   # ← отключить MSAA
# или
plotter.renderer.SetMultiSamples(0)
```

### `module 'vtk' has no attribute 'util'`

**Причина:** новые VTK не подгружают `vtk.util` автоматически.

**Решение:**
```python
import vtk
from vtk.util import numpy_support   # ← явно
```

### `Plotter.__init__() got an unexpected keyword argument 'multi_samples'`

**Причина:** PyVista 0.44+ убрал параметр.

**Решение:**
```python
self.plotter = pv.Plotter(off_screen=True, window_size=resolution)
self.plotter.renderer.SetMultiSamples(0)
```

### Картинка чёрная

**Решение:**
```bash
export VTK_DEFAULT_OPENGL_WINDOW=vtkEGLRenderWindow
export LIBGL_ALWAYS_SOFTWARE=1
```

Или через `xvfb`:
```bash
xvfb-run -a -s "-screen 0 1280x720x24" mc animate --fast
```

### Рендер очень медленный (>100 мс/кадр)

**Причина:** CPU-рендер (Mesa llvmpipe) вместо GPU.

**Решение:**
```bash
# проверить
python -c "import pyvista as pv; pv.OFF_SCREEN=True; p=pv.Plotter(); print(p.ren_win.GetClassName())"

# должно быть vtkEGLRenderWindow или vtkXOpenGLRenderWindow
```

Если `vtkOSOpenGLRenderWindow` — установи:
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

### MP4 не создаётся

Проверь:
```bash
ffmpeg -codecs | grep libx264
```

Если пусто — переустанови с флагом `--enable-libx264`.

## Python

### `NameError: name 'Config' is not defined`

Проверь импорты в верхней части файла:
```python
from counter import Config
```

### `ModuleNotFoundError: No module named 'counter'`

```bash
pip install -e .
# или
cd counter_project
python -m counter --help
```

## Печать

### Барабаны не вращаются

- Проверь зазор барабан-ось: должен быть 0.15–0.2 мм
- Смажь ось PTFE
- Рассверлить отверстие сверлом на 0.1 мм больше

### Цифры плохо видны

- Печатай барабаны в **белом** PETG
- Заполни вдавленные цифры чёрной краской
- Или наоборот — печатай чёрным, крась белым
