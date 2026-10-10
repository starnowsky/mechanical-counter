FROM python:3.11-slim

# Системные зависимости для VTK / EGL / ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1-mesa-dri libglx-mesa0 libegl1-mesa libosmesa6 \
        xvfb ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY counter/ ./counter/

RUN pip install --no-cache-dir -e ".[all]"

# off-screen рендер
ENV VTK_DEFAULT_OPENGL_WINDOW=vtkEGLRenderWindow \
    PYVISTA_OFF_SCREEN=true \
    PYTHONUNBUFFERED=1

ENTRYPOINT ["mc"]
CMD ["--help"]
