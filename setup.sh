#!/usr/bin/env bash
# Auto Video Producer — environment bootstrap.
# Installs Python dependencies (PyPI), ensures an ffmpeg binary is resolvable.
set -e
cd "$(dirname "$0")"

echo "==> installing python dependencies"
pip3 install --break-system-packages -q \
  fastapi "uvicorn[standard]" pillow numpy python-multipart aiofiles httpx \
  espeakng-loader imageio-ffmpeg

echo "==> ffmpeg check"
python3 - <<'PY'
from app.util import ffmpeg_path
print("    ffmpeg:", ffmpeg_path())
PY

python3 - <<'EOF'
import importlib
for m in ["fastapi", "uvicorn", "PIL", "numpy", "httpx", "espeakng_loader", "imageio_ffmpeg"]:
    importlib.import_module(m)
print("==> all dependencies ok")
