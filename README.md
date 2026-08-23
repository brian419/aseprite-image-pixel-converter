# Aseprite Image Pixel Converter

A local utility for converting large reference images into crisp, low-resolution PNGs for refinement in Aseprite.

The converter is designed for source images that have useful visual structure but are too large or too soft to edit comfortably as pixel art. It resizes the image onto a controlled pixel grid while preserving transparency and composition. Color reduction is optional rather than mandatory, allowing detail to be retained when the source benefits from a broader range of resized colors.

## Overview

The primary interface is a local browser application backed by Python. Processing stays on the local machine.

Typical workflow:

```text
reference image
    ↓
drag into the local app
    ↓
choose canvas size and resize method
    ↓
preserve resized colors or optionally limit the palette
    ↓
compare the linked source and converted views
    ↓
zoom and pan the same area in both views
    ↓
choose an output folder
    ↓
convert and save
    ↓
open and refine in Aseprite
```

The converter is intended as a preparation tool, not a replacement for manual pixel-art decisions. Final silhouettes, clusters, outlines, animation, and artistic cleanup remain part of the Aseprite workflow.

## Features

- Local image processing; source images are not sent to an external service.
- Drag-and-drop browser interface.
- Linked source and converted-output comparison views.
- Matched visual scale for direct before-and-after inspection.
- Synchronized zoom and pan between source and output views.
- Preview zoom up to 6400% for close pixel inspection.
- Smooth source rendering beside crisp pixelated output rendering.
- Live converted-output preview before saving.
- Preserve resized RGB colors by default for stronger detail retention.
- Optional palette limiting from 2 to 256 colors.
- Nearest, Lanczos, Bicubic, Hamming, and Box resize methods.
- Descriptive filenames generated from the selected conversion settings.
- Native folder chooser for explicit output selection.
- Configurable output width and height.
- Transparent-background preservation and automatic edge cleanup.
- Aspect-ratio preservation and automatic centering.
- Command-line interface for advanced or scripted use.
- Unit tests for the image converter and local web backend.

## Platform Support

The current launcher and native folder-selection integration are geared toward macOS. The image-conversion core is Python-based and is not inherently tied to a specific computer model.

## Requirements

- Python 3.10 or newer
- Flask
- Pillow
- Waitress

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
3. Leave **Resize method** on **Nearest — Recommended**, or compare another method in the live preview.
4. Leave **Color handling** on **Preserve resized colors** when you want to retain the resized image's full color detail.
5. To reduce colors deliberately, choose **Limit palette**. The visible **Palette colors** field becomes active; `32` is only a starting value and can be changed from `2` to `256`.
6. Compare the **Source Image** and **Output Preview** at the same visual scale.
7. Use the **−** and **+** controls to zoom both views together.
8. Click and drag either preview to pan; the other preview follows the same position.
9. Choose a destination folder with **Choose Folder…**.
10. Click **Convert Image** to save the displayed result.
11. Open the resulting PNG in Aseprite for final refinement.

A destination folder is selected for each conversion. Previewing does not save a file and does not require an output folder.

### Generated filenames

The suggested filename updates automatically when the main conversion settings change. The default preserve-colors format is:

```text
source-128x128-nearest-preserve.png
```

Palette-limited files include the palette size:

```text
source-128x128-nearest-32c.png
```

The filename remains editable before saving.

### Choosing settings

Canvas size and color handling solve different problems:

- **Canvas size** controls how much spatial detail can survive the downscale. Small dimensions simplify shapes more aggressively.
- **Preserve resized colors** keeps the RGB colors created by the resize operation instead of forcing them into a limited palette.
- **Limit palette** intentionally merges colors. When enabled, the **Palette colors** field controls the maximum palette size; `32` is a starting value, not a required setting.

For detailed references, `128 × 128` with **Preserve resized colors** and **Nearest — Recommended** is the default starting point. Increase the canvas to `160 × 160` or higher when small interior shapes still disappear. Use palette limiting only when color simplification is part of the desired look.

## Resize Methods

- **Nearest** — recommended default; preserves hard pixel sampling without interpolation.
- **Lanczos** — detailed interpolation during strong downscaling.
- **Bicubic** — balanced interpolation with a slightly softer result.
- **Hamming** — useful for a somewhat sharper interpolated reduction.
- **Box** — simple area averaging.

The best method depends on the source. The linked preview makes it possible to compare them before saving.

## Command-Line Interface

The underlying converter remains available directly. The default CLI path preserves resized colors and uses Nearest resizing:

```bash
python3 aseprite_image_pixel_converter.py input.png output.png --size 128
```

To deliberately limit the palette:

```bash
python3 aseprite_image_pixel_converter.py input.png output.png --size 128 --colors 32
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
