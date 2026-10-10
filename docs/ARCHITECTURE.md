# Архитектура

## Обзор

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

## Модули

### `geometry.py`
- `Config` — dataclass со всеми размерами
- `Mesh` — контейнер треугольников с кэшем
- `make_box`, `make_cylinder`, `make_tube`, `make_torus` — примитивы
- `build_drum`, `build_housing`, `build_cover`, ... — сборка деталей

### `scene.py`
- `Part` — деталь с двумя позициями (собранная / разлетевшаяся)
- `build_scene(cfg)` — собирает сцену для анимации

### `backend_pv.py` (быстрый)
- PyVista + VTK, PBR-материалы, SSAO, тени
- Три уровня fallback в `screenshot()`

### `backend_mpl.py` (fallback)
- matplotlib 3D, работает везде
- Медленнее в 15×, но не требует GPU

### `cameras.py`
- Пресеты: iso / front / top / side
- `split_screen_multi` — L-shape, hstack, vstack, grid

### `audio.py`
- Синтез `click`, `motor_hum`, `overflow_chime`
- `build_track` — собирает WAV-дорожку

## Поток данных

1. `Config` → `build_scene` → `List[Part]`
2. `Part` + `t` → `transformed(t, mode)` → `np.ndarray(N,3,3)`
3. `backend.update_parts(transforms)` → обновляет VTK-актёры
4. `backend.screenshot()` → RGB-кадр
5. Список кадров → `imageio.mimsave` → MP4/GIF
6. `audio.build_track(events)` → WAV
7. `ffmpeg` → склейка видео + звук
