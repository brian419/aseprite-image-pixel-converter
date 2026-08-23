# Aseprite Image Pixel Converter

A local utility for converting large reference images into smaller, palette-limited PNGs for refinement in Aseprite.

The project is designed for workflows where a source image has useful visual structure but is too large, too soft, or contains too many colors to edit comfortably as pixel art. The converter reduces the image to a controlled canvas and palette while preserving transparency and overall composition, producing a cleaner starting point for manual work in Aseprite.

## Overview

The primary interface is a local browser application backed by Python. Processing stays on the local machine.

Typical workflow:

```text
reference image
    ↓
drag into the local app
    ↓
choose canvas size and palette limit
    ↓
choose an output folder
    ↓
convert
    ↓
open and refine in Aseprite
```

The converter is intended as a preparation tool, not a replacement for manual pixel-art decisions. Final silhouettes, clusters, outlines, animation, and artistic cleanup remain part of the Aseprite workflow.

## Features

- Local image processing; source images are not sent to an external service.
- Drag-and-drop browser interface.
- Source-image preview.
- Native folder chooser for direct output.
- Browser-download fallback when no folder is selected.
- Configurable output width and height.
- Configurable palette size from 2 to 256 colors.
- Transparent-background preservation.
- Optional cropping of transparent margins before resizing.
- Aspect-ratio preservation and automatic centering.
- Optional hard alpha for fully transparent or fully opaque edges.
- Nearest Neighbor, Box, and Lanczos resize methods.
- Optional Floyd–Steinberg dithering.
- Command-line interface for advanced or scripted use.
- Unit tests for the image converter and local web backend.

## Platform Support

The current launcher and native folder-selection integration are geared toward macOS. The image-conversion core is Python-based and is not inherently tied to a specific computer model.

## Requirements

- Python 3.10 or newer
- Flask
- Pillow

Dependencies are installed automatically into a local virtual environment by the launcher on first use.

## Getting Started

Clone the repository:

```bash
git clone https://github.com/brian419/aseprite-image-pixel-converter.git
cd aseprite-image-pixel-converter
```

Launch the application:

```bash
open start.command
```

You can also double-click `start.command` in Finder.

On first launch, the script creates `.venv`, installs the required dependencies, starts the local server, and opens the application in the default browser.

The interface is served locally at:

```text
http://127.0.0.1:8765
```

## Using the App

1. Drag an image into the source area, or click the source area to choose a file.
2. Set the target canvas size.
3. Set the palette color limit.
4. Choose a resize method.
5. Optionally choose a destination folder with **Choose Folder…**.
6. Click **Convert Image**.
7. Open the resulting PNG in Aseprite for final refinement.

If no output folder is selected, the converted image is downloaded through the browser.

### Choosing settings

Smaller canvases and smaller palettes simplify the image more aggressively. Higher values retain more information from detailed source images.

A practical starting range for detailed generated or painted references is:

- `96–128 px` with `16–32 colors` for stronger simplification.
- `128–192 px` with `32–64 colors` when more source detail should be retained.

The appropriate settings depend on the source image and the desired final pixel-art scale.

## Advanced Options

The interface also exposes:

- **Dithering** — optional Floyd–Steinberg color dithering.
- **Crop transparent margins** — removes unused transparent space before resizing.
- **Hard transparent/opaque edges** — converts alpha to fully transparent or fully opaque pixels.

The defaults are intended to work well for most transparent sprite references.

## Command-Line Interface

The underlying converter remains available directly:

```bash
python3 aseprite_image_pixel_converter.py input.png output.png --size 80 --colors 16
```

View all options:

```bash
python3 aseprite_image_pixel_converter.py --help
```

## Tests

With the project virtual environment active:

```bash
python3 -m unittest discover -s tests -v
```

## Project Structure

```text
aseprite-image-pixel-converter/
├── aseprite_image_pixel_converter.py   # image conversion logic and CLI
├── web_app.py                          # local Flask backend
├── web/
│   └── index.html                      # browser interface
├── tests/                              # automated tests
├── requirements.txt                    # Python dependencies
└── start.command                       # local launcher
```
