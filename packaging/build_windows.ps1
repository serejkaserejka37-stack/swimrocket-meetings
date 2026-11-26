$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root
& .\.venv\Scripts\python.exe -m pip install pyinstaller pillow | Out-Host
& .\.venv\Scripts\python.exe resources\build_swimrocket_assets.py | Out-Host
& .\.venv\Scripts\python.exe -m PyInstaller `
  --noconfirm --clean --windowed `
  --name SwimRocketMeetings `
  --icon resources\swimrocket.ico `
  --add-data "resources;resources" `
  --exclude-module torch `
  --exclude-module faster_whisper `
  --exclude-module pyannote `
  --exclude-module transformers `
  main.py | Out-Host
& iscc packaging\windows_installer.iss | Out-Host
