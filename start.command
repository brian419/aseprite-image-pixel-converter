#!/bin/zsh
set -e

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Setting up Aseprite Image Pixel Converter for first use..."
  python3 -m venv .venv
fi

source .venv/bin/activate

if ! python3 -c 'import flask, PIL, waitress' >/dev/null 2>&1; then
  echo "Installing required local packages..."
  python3 -m pip install --upgrade pip --quiet
  python3 -m pip install -r requirements.txt --quiet
fi

NATIVE_SOURCE="native/apple_subject_lift.swift"
NATIVE_BUILD_DIR=".build"
NATIVE_HELPER="$NATIVE_BUILD_DIR/apple_subject_lift"

if [ -f "$NATIVE_SOURCE" ] && { [ ! -x "$NATIVE_HELPER" ] || [ "$NATIVE_SOURCE" -nt "$NATIVE_HELPER" ]; }; then
  mkdir -p "$NATIVE_BUILD_DIR"
  if xcrun --find swiftc >/dev/null 2>&1; then
    echo "Building local Apple Vision subject helper..."
    if ! xcrun swiftc -O "$NATIVE_SOURCE" -o "$NATIVE_HELPER"; then
      rm -f "$NATIVE_HELPER"
      echo "Warning: the Apple Vision helper could not be built. Whole-image conversion will still work."
      echo "Smart Click and Smart Lasso require current Xcode Command Line Tools on macOS 14 or newer."
    fi
  else
    echo "Warning: Swift compiler not found. Whole-image conversion will still work."
    echo "Smart Click and Smart Lasso require Xcode Command Line Tools on macOS 14 or newer."
  fi
fi

echo "Starting Aseprite Image Pixel Converter..."
exec python3 web_app.py
