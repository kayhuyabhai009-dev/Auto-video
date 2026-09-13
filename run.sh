#!/usr/bin/env bash
# Start the Auto Video Producer studio (http://0.0.0.0:7860)
cd "$(dirname "$0")"

# self-heal environment if site-packages were reset
python3 -c "import fastapi, PIL, numpy, httpx, espeakng_loader, imageio_ffmpeg" 2>/dev/null || ./setup.sh

echo "==> Auto Video Producer  ·  http://0.0.0.0:7860"
exec python3 -m uvicorn app.server:app --host 0.0.0.0 --port 7860 --log-level warning
