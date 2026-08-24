#!/bin/zsh
set -e

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Setting up Aseprite Image Pixel Converter for first use..."
  python3 -m venv .venv
fi

source .venv/bin/activate

if ! python3 -c 'import cv2, flask, numpy, PIL, waitress' >/dev/null 2>&1; then
  echo "Installing required local packages..."
  python3 -m pip install --upgrade pip --quiet
  python3 -m pip install -r requirements.txt --quiet
fi

echo "Starting Aseprite Image Pixel Converter..."
exec python3 web_app.py
