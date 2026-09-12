#!/usr/bin/env bash
# Auto Video Producer — environment bootstrap.
# Installs Python dependencies (PyPI) and verifies an ffmpeg binary resolves.
set -e
cd "$(dirname "$0")"

echo "==> installing python dependencies"
pip3 install --break-system-packages -q \
  fastapi "uvicorn[standard]" pillow numpy python-multipart aiofiles httpx \
  espeakng-loader imageio-ffmpeg

echo "==> ffmpeg check"
python3 -c "from app.util import ffmpeg_path; print('    ffmpeg:', ffmpeg_path())"

python3 -c "
import importlib
for m in ['fastapi', 'uvicorn', 'PIL', 'numpy', 'httpx', 'espeakng_loader', 'imageio_ffmpeg']:
    importlib.import_module(m)
print('==> all dependencies ok')"
echo "==> bootstrap complete. Start with: ./run.sh"
