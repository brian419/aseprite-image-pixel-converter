# Aseprite Image Pixel Converter

A local macOS-friendly utility for converting large reference images into smaller, palette-limited PNGs that are easier to refine manually in Aseprite.

The primary workflow is now a local browser app:

```text
launch app
  ↓
drag in an image
  ↓
choose size and palette
  ↓
choose a macOS save folder (optional)
  ↓
convert
  ↓
open the result in Aseprite
```

The tool runs locally. It does **not** attempt to create finished pixel art automatically; it prepares a constrained starting image for manual cleanup and art decisions in Aseprite.

## Normal use on macOS

After pulling `development`, launch the app with:

```bash
open start.command
```

You can also double-click `start.command` in Finder.

On first launch, the script creates `.venv` and installs the required local Python packages. Later launches reuse that environment.

The browser interface opens at:

```text
http://127.0.0.1:8765
```

### In the app

1. Drag an image into the source area, or click the area to choose one.
2. Pick a canvas size such as 64, 80, or 96 pixels.
3. Pick the palette color limit.
4. Click **Choose Folder…** to open the native macOS folder chooser if you want the PNG written directly to a specific folder.
5. Click **Convert Image**.

If no folder is selected, the converted PNG downloads through the browser normally.

## Current features

- Local-only processing.
- Drag-and-drop source images.
- Native macOS folder chooser for output.
- Normal browser-download fallback.
- Source-image preview.
- Default output of `80 × 80` and 16 colors.
- Preserves transparent backgrounds.
- Crops transparent margins by default.
- Preserves aspect ratio and centers the sprite.
- Hardens alpha to fully transparent/opaque pixels by default.
- Nearest, Box, and Lanczos resize methods.
- Optional Floyd–Steinberg dithering.
- Command-line converter remains available for advanced use.
- Unit tests for converter and web backend.

## Requirements

- macOS for the native save-folder picker
- Python 3.10+
- Flask
- Pillow

## Tests

With the virtual environment active:

```bash
python3 -m unittest discover -s tests -v
```

## Advanced command-line use

The underlying converter can still be run directly:

```bash
python3 aseprite_image_pixel_converter.py input.png output.png --size 80 --colors 16
```

Show every option with:

```bash
python3 aseprite_image_pixel_converter.py --help
```

## Branch policy

- `main` is the stable backup branch and is not changed during normal development.
- `development` is the normal integration branch.
- Temporary feature/fix branches should be created only when useful and removed after approved integration.
