# Aseprite Image Pixel Converter

A local utility for converting large reference images into crisp, low-resolution PNGs for refinement in Aseprite.

The converter is designed for source images that have useful visual structure but are too large or too soft to edit comfortably as pixel art. It resizes the image onto a controlled pixel grid, attempts to make inferred opaque backgrounds transparent, preserves existing transparent spacing, and can optionally limit the palette.

## Overview

The primary interface is a local browser application backed by Python. Processing stays on the local machine.

Typical workflow:

```text
reference image
    ↓
drag into the local app
    ↓
automatically infer/remove the outer background when possible
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
- Automatic outer-background transparency for opaque source images when a background can be inferred.
- Foreground protection that blocks narrow background-colored paths from tunneling into dense interior details.
- Existing transparent backgrounds and margins are preserved rather than cropped.
- Linked source and converted-output comparison views.
- Matched visual scale for direct before-and-after inspection.
- Synchronized zoom and pan between source and output views.
- Preview zoom up to 6400% for close pixel inspection.
- Smooth source rendering beside crisp pixelated output rendering.
- Live converted-output preview before saving.
- Preserve resized RGB colors by default for stronger detail retention.
- Optional palette limiting from 2 to 256 colors.
- Nearest, Detail Preserve, Lanczos, Bicubic, Hamming, and Box resize methods.
- Descriptive filenames generated from the selected conversion settings.
- Native folder chooser for explicit output selection.
- Configurable output width and height.
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
2. If the source has an opaque background, the app attempts to infer a dominant border/background color and make the confirmed outer background transparent.
3. Set the target canvas size.
4. Leave **Resize method** on **Nearest — Recommended** for normal pixel sampling, or try **Detail Preserve — complex art** for unusually dense references.
5. Leave **Color handling** on **Preserve resized colors** when you want to retain the resized image's full color detail.
6. To reduce colors deliberately, choose **Limit palette**. The visible **Palette colors** field becomes active; `32` is only a starting value and can be changed from `2` to `256`.
7. Compare the **Source Image** and **Output Preview** at the same visual scale.
8. Use the **−** and **+** controls to zoom both views together.
9. Click and drag either preview to pan; the other preview follows the same position.
10. Choose a destination folder with **Choose Folder…**.
11. Click **Convert Image** to save the displayed result.
12. Open the resulting PNG in Aseprite for final refinement.

A destination folder is selected for each conversion. Previewing does not save a file and does not require an output folder.

### Automatic background transparency

For opaque inputs, the converter estimates the dominant color along the outer border and identifies nearby colors within a conservative tolerance. Before determining which candidate pixels belong to the exterior, it temporarily shrinks the candidate background mask. This closes narrow dark seams and tiny gaps through a complex object so the outside flood cannot tunnel into interior recesses. The confirmed exterior is then expanded only a small distance and only through pixels that were already background candidates.

This protection is especially important for dense machine art containing dark engravings, gaps between mechanical parts, recessed chambers, and other regions that may resemble the surrounding background.

If the source already has meaningful transparency around its border, the converter trusts the existing alpha channel instead of trying to infer another background.

Background inference remains intentionally conservative. Highly textured, photographic, multi-color, or object-touching backgrounds may still need manual cleanup in Aseprite.

### Generated filenames

The suggested filename updates automatically when the main conversion settings change. The default preserve-colors format is:

```text
source-128x128-nearest-preserve.png
```

The dense-art mode is recorded as:

```text
source-128x128-detail-preserve.png
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

For detailed references, `128 × 128` with **Preserve resized colors** and **Nearest — Recommended** remains the normal starting point. For extremely dense references with tiny engravings, nested mechanisms, many highlights, or many layered surfaces, compare **Detail Preserve — complex art** in the live preview. Increasing the canvas to `160 × 160` or higher can still be necessary when the source contains more spatial information than 128 pixels can represent.

## Resize Methods

- **Nearest** — recommended default; preserves hard pixel sampling without interpolation.
- **Detail Preserve** — dense-reference mode; performs high-quality Lanczos reduction and then controlled local sharpening to retain more visual separation in intricate inputs.
- **Lanczos** — detailed interpolation during strong downscaling.
- **Bicubic** — balanced interpolation with a slightly softer result.
- **Hamming** — useful for a somewhat sharper interpolated reduction.
- **Box** — simple area averaging.

The existing resize methods are unchanged. **Detail Preserve** is an additional option specifically for complex source art.

## Command-Line Interface

The underlying converter remains available directly. The default CLI path preserves resized colors, preserves transparent margins, attempts automatic background transparency, and uses Nearest resizing:

```bash
python3 aseprite_image_pixel_converter.py input.png output.png --size 128
```

Use the detail-preserving method with:

```bash
python3 aseprite_image_pixel_converter.py input.png output.png --size 128 --resample detail
```

To deliberately limit the palette:

```bash
python3 aseprite_image_pixel_converter.py input.png output.png --size 128 --colors 32
```

The CLI can skip automatic background removal with `--keep-background` or explicitly crop transparent margins with `--crop`. Neither option is exposed in the streamlined browser interface.

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
