#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 -m pip install pyinstaller pillow
python3 resources/build_swimrocket_assets.py
mkdir -p resources/SwimRocket.iconset
for size in 16 32 64 128 256 512; do
  sips -z "$size" "$size" resources/swimrocket-icon.png --out "resources/SwimRocket.iconset/icon_${size}x${size}.png" >/dev/null
  if [ "$size" -le 256 ]; then
    double=$((size * 2))
    sips -z "$double" "$double" resources/swimrocket-icon.png --out "resources/SwimRocket.iconset/icon_${size}x${size}@2x.png" >/dev/null
  fi
done
iconutil -c icns resources/SwimRocket.iconset -o resources/swimrocket.icns
python3 -m PyInstaller \
  --noconfirm --clean --windowed \
  --name "SwimRocket Встречи" \
  --icon resources/swimrocket.icns \
  --add-data "resources:resources" \
  --exclude-module torch \
  --exclude-module faster_whisper \
  --exclude-module pyannote \
  --exclude-module transformers \
  main.py
mkdir -p release
hdiutil create -volname "SwimRocket Встречи" \
  -srcfolder "dist/SwimRocket Встречи.app" \
  -ov -format UDZO "release/SwimRocketMeetings.dmg"
