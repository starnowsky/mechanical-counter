# Changelog

Все значимые изменения. Формат: [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [1.0.0] — 2026-10-10

### Added
- Генерация STL всех деталей счётчика (1–4 разряда)
- Проверка манифолдности меша
- Экспорт STEP (опционально, через cadquery)
- Анимация сборки / разборки
- Анимация работы механизма со шаговым вращением 36°
- PyVista-бэкенд (быстрый) + matplotlib-бэкенд (fallback)
- Split-screen из 3 камер (iso / front / top)
- Синтез звуков (щелчки, гул, сигнал переполнения)
- CLI с подкомандами `stl` и `animate`
- Прозрачный корпус в режиме работы
- PBR-материалы, SSAO, тени
- PNG-превью каждой детали
- Docker-образ для headless рендера

### Fixed
- VTK warnings `Framebuffer Object not bound` (multi_samples=0)
- `vtk.util` не импортировался
- `multi_samples` убран в PyVista 0.44+
- `add_text(name=...)` убран в новых PyVista

## [0.1.0] — 2026-09-01

### Added
- Прототип генератора STL
