# Changelog

All notable changes. Format: [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [1.0.0] — 2026-10-10

### Added
- STL generation for all counter parts (1–4 digits)
- Mesh manifold validation
- STEP export (optional, via cadquery)
- Assembly / disassembly animation
- Mechanism operation animation with 36° stepwise rotation
- PyVista backend (fast) + matplotlib backend (fallback)
- Split-screen with 3 cameras (iso / front / top)
- Sound synthesis (clicks, hum, overflow chime)
- CLI with `stl` and `animate` subcommands
- Transparent housing in operation mode
- PBR materials, SSAO, shadows
- PNG preview for each part
- Docker image for headless rendering

### Fixed
- VTK warnings `Framebuffer Object not bound` (multi_samples=0)
- `vtk.util` was not imported
- `multi_samples` removed in PyVista 0.44+
- `add_text(name=...)` removed in newer PyVista

## [0.1.0] — 2026-09-01

### Added
- STL generator prototype
