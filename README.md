# Aseprite Image Pixel Converter

A local utility for converting large reference images into crisp, low-resolution PNGs for refinement in Aseprite.

The converter is designed for source images that have useful visual structure but are too large or too soft to edit comfortably as pixel art. It resizes the image onto a controlled pixel grid, can make inferred outer backgrounds transparent, can isolate one user-selected object, preserves existing transparent spacing, and can optionally limit the palette.

## Overview

The primary interface is a local browser application backed by Python. Processing stays on the local machine.

Typical whole-image workflow:

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

Object-isolation workflow:

```text
reference image
    ↓
choose "Only one selected object"
    ↓
draw a box around the object
    ↓
optionally add Keep / Remove refinement marks
    ↓
the rest of the image becomes transparent
    ↓
the isolated object is trimmed and fitted to the target canvas
    ↓
pixel conversion uses only the isolated object
    ↓
save the PNG and refine in Aseprite
```

The converter is intended as a preparation tool, not a replacement for manual pixel-art decisions. Final silhouettes, clusters, outlines, animation, and artistic cleanup remain part of the Aseprite workflow.

## Features

- Local image processing. Source images are not sent to an external service.
- Drag-and-drop browser interface.
- Automatic outer-background transparency for opaque source images when a background can be inferred.
- Foreground protection that blocks narrow background-colored paths from tunneling into dense interior details.
- Interactive single-object isolation using OpenCV GrabCut.
- Box selection for choosing the object to keep.
- Keep and Remove refinement marks for correcting difficult selections.
- Pan mode for navigating the source while object selection is enabled.
- Object isolation works without a cloud API, text-prompt service, or downloaded AI model.
- Existing transparent backgrounds and margins are preserved.
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
- Command-line interface for the original whole-image conversion workflow.
- Unit tests for image conversion, object isolation, and the local web backend.

## Platform Support

The current launcher and native folder-selection integration are geared toward macOS. The image-conversion core is Python-based and is not inherently tied to a specific computer model.

The object-isolation dependency uses the headless OpenCV package, so no OpenCV desktop GUI is installed or required.

## Requirements

- Python 3.10 or newer
- Flask
- Pillow
- Waitress
- NumPy
- OpenCV Python Headless

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
2. Under **What should be pixelated?**, choose either the existing whole-image mode or **Only one selected object**.
3. Set the target canvas size.
4. Leave **Resize method** on **Nearest - Recommended** for normal pixel sampling, or try **Detail Preserve - complex art** for unusually dense references.
5. Leave **Color handling** on **Preserve resized colors** when you want to retain the resized image's full color detail.
6. To reduce colors deliberately, choose **Limit palette**. The visible **Palette colors** field becomes active; `32` is only a starting value and can be changed from `2` to `256`.
7. Compare the **Source Image** and **Output Preview** at the same visual scale.
8. Use the **-** and **+** controls to zoom both views together.
9. Click and drag either preview to pan when normal pan behavior is active.
10. Choose a destination folder with **Choose Folder...**.
11. Click **Convert Image** to save the displayed result.
12. Open the resulting PNG in Aseprite for final refinement.

A destination folder is selected for each conversion. Previewing does not save a file and does not require an output folder.

## Object Isolation

Object isolation is meant for cases where the image contains several things but only one should become pixel art.

For example, if a photograph contains a tree, field, sky, and distant forest, you can draw a box around the tree. The converter treats the selected region as probable foreground and the outside area as background, then runs OpenCV's GrabCut segmentation locally.

### Selection tools

- **Box**: drag a rectangle around the complete object you want to keep.
- **Keep**: click an area that should be foreground if the first result removed too much.
- **Remove**: click an area that should be transparent if the first result kept unwanted background.
- **Pan**: move around the linked source/output view while zoomed in.
- **Clear**: discard the object box and all refinement marks.

The Keep and Remove controls place local hard foreground/background hints into the GrabCut mask. You can add multiple marks and the preview is recalculated.

The selection rectangle should contain the full object while excluding as much unrelated background as practical. Difficult boundaries such as hair, foliage, branches, holes, reflections, low contrast edges, and similar foreground/background colors can require refinement marks.

Object isolation is deliberately interactive rather than text-prompt based. This keeps the tool small, private, and practical on modest CPU-only hardware. It does not need PyTorch, a large segmentation checkpoint, or an internet API.

For very large images, the segmentation working copy is capped at 1200 pixels on its longest side. The resulting mask is then mapped back to the original image before the normal pixel conversion. This prevents huge photographs from making the local segmentation unnecessarily expensive.

After segmentation, transparent space outside the selected object is trimmed before the object is fitted and centered on the requested output canvas. This makes the selected object use the available pixel resolution instead of keeping the original photograph's empty composition around it.

## Automatic Background Transparency

For opaque inputs in whole-image mode, the converter estimates the dominant color along the outer border and identifies nearby colors within a conservative tolerance. Before determining which candidate pixels belong to the exterior, it temporarily shrinks the candidate background mask. This closes narrow seams and tiny gaps through a complex object so the outside flood cannot tunnel into interior recesses. The confirmed exterior is then expanded only a small distance and only through pixels that were already background candidates.

This protection is especially important for dense machine art containing dark engravings, gaps between mechanical parts, recessed chambers, and other regions that may resemble the surrounding background.

If the source already has meaningful transparency around its border, the converter trusts the existing alpha channel instead of trying to infer another background.

Background inference remains intentionally conservative. Highly textured, photographic, multi-color, or object-touching backgrounds are where the interactive object-isolation mode is more useful.

## Generated Filenames

The suggested filename updates automatically when the main conversion settings change.

Default whole-image preserve-colors format:

```text
source-128x128-nearest-preserve.png
```

Selected-object preserve-colors format:

```text
source-128x128-nearest-isolated-preserve.png
```

Dense-art mode:

```text
source-128x128-detail-preserve.png
```

Palette-limited files include the palette size:

```text
source-128x128-nearest-32c.png
```

The filename remains editable before saving.

## Choosing Settings

Canvas size and color handling solve different problems:

- **Canvas size** controls how much spatial detail can survive the downscale. Small dimensions simplify shapes more aggressively.
- **Preserve resized colors** keeps the RGB colors created by the resize operation instead of forcing them into a limited palette.
- **Limit palette** intentionally merges colors. When enabled, the **Palette colors** field controls the maximum palette size; `32` is a starting value, not a required setting.

For detailed references, `128 x 128` with **Preserve resized colors** and **Nearest - Recommended** remains the normal starting point. For extremely dense references with tiny engravings, nested mechanisms, many highlights, or many layered surfaces, compare **Detail Preserve - complex art** in the live preview. Increasing the canvas to `160 x 160` or higher can still be necessary when the source contains more spatial information than 128 pixels can represent.

## Resize Methods

- **Nearest**: recommended default; preserves hard pixel sampling without interpolation.
- **Detail Preserve**: dense-reference mode; performs high-quality Lanczos reduction and then controlled local sharpening to retain more visual separation in intricate inputs.
- **Lanczos**: detailed interpolation during strong downscaling.
- **Bicubic**: balanced interpolation with a slightly softer result.
- **Hamming**: useful for a somewhat sharper interpolated reduction.
- **Box**: simple area averaging.

The existing resize methods are unchanged. **Detail Preserve** remains an additional option specifically for complex source art.

## Command-Line Interface

The underlying converter remains available directly. The CLI keeps the existing whole-image workflow. Object isolation is currently exposed through the interactive local browser interface because it depends on user selection coordinates.

Default CLI conversion:

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

The CLI can skip automatic background removal with `--keep-background` or explicitly crop transparent margins with `--crop`.

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
├── aseprite_image_pixel_converter.py   # existing image conversion logic and CLI
├── object_isolation.py                 # interactive GrabCut object isolation
├── web_app.py                          # local Flask backend
├── web/
│   ├── index.html                      # browser interface structure
│   ├── styles.css                      # interface styling
│   └── app.js                          # preview, zoom, pan, and selection behavior
├── tests/
│   ├── test_converter.py
│   ├── test_web_app.py
│   ├── test_object_isolation.py
│   └── test_object_isolation_web.py
├── requirements.txt                    # Python dependencies
└── start.command                       # local launcher
```
