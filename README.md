# Aseprite Image Pixel Converter

A local macOS utility for converting large reference images into crisp, low-resolution PNGs for refinement in Aseprite.

The app keeps the existing whole-image conversion workflow and adds Apple Vision smart subject lifting. In smart mode, the user can click a detected foreground subject or draw a loose lasso around it. The selected subject is lifted with the rest of the image made transparent, then passed through the same pixel conversion pipeline.

## Main workflows

### Whole image

```text
reference image
    ↓
drag into the local app
    ↓
automatically infer/remove the outer background when possible
    ↓
choose canvas size, resize method, and color handling
    ↓
preview and save the pixel-sized PNG
```

### Smart Click

```text
reference image
    ↓
choose One subject - Smart Click
    ↓
click directly on the tree / person / car / other foreground subject
    ↓
Apple Vision identifies the foreground instance under the click
    ↓
background becomes transparent
    ↓
subject is trimmed, fitted, and centered on the target pixel canvas
    ↓
preview and save
```

### Smart Lasso

```text
reference image
    ↓
choose One subject - Smart Lasso
    ↓
draw a loose loop around the subject
    ↓
Apple Vision detects foreground instances inside the loop
    ↓
the best-matching detected subject is lifted
    ↓
subject is pixel-converted and saved
```

Smart Lasso is intentionally a rough-selection tool. The user does not need to trace the exact object edge. The lasso is used to choose among the foreground instances already detected by Apple Vision.

## Features

- Local browser interface served from `127.0.0.1`.
- Existing whole-image automatic outer-background transparency remains available.
- Smart Click subject selection using Apple's `VNGenerateForegroundInstanceMaskRequest`.
- Smart Lasso selection that chooses the dominant detected Vision subject inside a freeform loop.
- Click tolerance near thin branches, hair, edge pixels, and small holes by searching a small nearby region when the exact click lands on background.
- No cloud API and no external segmentation model download.
- No PyTorch, OpenCV, or model checkpoint required for subject lifting.
- Isolated subject is reused for resize and palette preview changes instead of rerunning Vision every time.
- Transparent subject is automatically cropped before fitting to the requested output canvas.
- Linked source and output comparison views.
- Synchronized zoom and pan.
- Preview zoom up to 6400%.
- Preserve resized colors by default or optionally limit the palette to 2-256 colors.
- Nearest, Detail Preserve, Lanczos, Bicubic, Hamming, and Box resize methods.
- Native macOS folder chooser.
- Configurable output width and height.
- Existing command-line whole-image converter remains available.

## Platform support

The browser/Python converter is local, but Smart Click and Smart Lasso intentionally use the macOS Vision framework.

Smart subject lifting requires:

- macOS 14 or newer.
- Xcode Command Line Tools with `swiftc` available through `xcrun` so the small native helper can be compiled locally.

The helper is compiled for the Mac on which `start.command` is launched. The helper source is stored in the repository and the generated executable is written under `.build/`, which is ignored by Git.

If the native helper cannot be compiled, the launcher still starts the app so the original whole-image conversion workflow remains usable. Smart modes will display a clear error until the helper is available.

## Requirements

- Python 3.10 or newer
- Flask
- Pillow
- Waitress
- macOS 14+ for Smart Click / Smart Lasso
- Xcode Command Line Tools for building the local Swift helper

There is no OpenCV dependency in the smart-subject implementation.

## Getting started

Clone the repository and launch the app:

```bash
git clone https://github.com/brian419/aseprite-image-pixel-converter.git
cd aseprite-image-pixel-converter
open start.command
```

You can also double-click `start.command` in Finder.

On first launch the script:

1. Creates `.venv` if necessary.
2. Installs the Python dependencies locally.
3. Compiles `native/apple_subject_lift.swift` to `.build/apple_subject_lift` when the helper is missing or its source changed.
4. Starts the Flask/Waitress local server.
5. Opens the app in the default browser.

The interface is served at:

```text
http://127.0.0.1:8765
```

## Using Smart Click

1. Load an image.
2. Under **What should be pixelated?**, choose **One subject - Smart Click**.
3. Click the subject in the Source Image.
4. Wait for Apple Vision to identify and lift the subject.
5. The Output Preview shows only the selected subject after pixel conversion.
6. If the wrong subject was selected, choose **Smart Click** in the toolbar and click a different location.
7. Choose a save folder and convert.

A click does not need to land on the exact center. If the exact point is background, the helper searches a small nearby area for the nearest detected foreground instance. This helps with foliage, branches, hair, and narrow object edges.

## Using Smart Lasso

1. Choose **One subject - Smart Lasso**.
2. Draw a rough loop around the object.
3. Apple Vision first detects foreground instances in the full image.
4. The helper counts the detected instance labels inside the lasso and selects the subject occupying the largest portion of the loop.
5. The selected subject is lifted with transparency and sent through the normal converter.

Smart Lasso is useful when a click is ambiguous or when several detected subjects are close together.

## How smart subject lifting works

The native helper uses Apple's Vision framework:

1. `VNGenerateForegroundInstanceMaskRequest` detects noticeable foreground instances.
2. `VNInstanceMaskObservation.instanceMask` labels the detected subjects separately from background.
3. Smart Click maps the browser click into Vision coordinates and reads the instance label under or near that point.
4. Smart Lasso maps the freeform polygon into the instance mask and chooses the most represented non-background instance.
5. `generateMaskedImage(ofInstances:from:croppedToInstancesExtent:)` produces an image containing only the selected instance, with the remaining pixels transparent.
6. Pillow receives that transparent PNG and the existing converter crops, resizes, centers, and optionally palette-limits it.

The app performs the expensive subject-detection step only when the user chooses a subject. The returned transparent PNG is retained in browser memory and reused when output size, palette, or resize settings change.

## Automatic whole-image background transparency

Whole-image mode keeps the existing conservative background inference. For opaque images, the converter estimates the dominant outer-border color and removes confirmed edge-connected background pixels while protecting narrow interior gaps from accidental transparency.

Highly textured or photographic backgrounds are where Smart Click is usually more appropriate.

## Generated filenames

Whole-image example:

```text
source-128x128-nearest-preserve.png
```

Smart subject example:

```text
source-128x128-nearest-isolated-preserve.png
```

Palette-limited example:

```text
source-128x128-nearest-isolated-32c.png
```

The filename remains editable before saving.

## Command-line converter

The existing CLI continues to provide the whole-image workflow:

```bash
python3 aseprite_image_pixel_converter.py input.png output.png --size 128
```

Detail preserving resize:

```bash
python3 aseprite_image_pixel_converter.py input.png output.png --size 128 --resample detail
```

Palette limit:

```bash
python3 aseprite_image_pixel_converter.py input.png output.png --size 128 --colors 32
```

Smart Click and Smart Lasso are currently exposed through the local browser interface because they depend on interactive image coordinates.

## Tests

With the project virtual environment active:

```bash
python3 -m unittest discover -s tests -v
```

The Python subject-wrapper tests mock the native process so validation can run independently of Vision. The real Vision helper itself requires a macOS 14+ machine.

## Project structure

```text
aseprite-image-pixel-converter/
├── aseprite_image_pixel_converter.py   # existing pixel conversion logic and CLI
├── apple_subject_lift.py               # Python validation and native-helper bridge
├── native/
│   └── apple_subject_lift.swift        # Apple Vision foreground instance selector
├── web_app.py                          # local Flask backend
├── web/
│   ├── index.html                      # browser interface
│   ├── styles.css                      # interface styling
│   └── app.js                          # preview, zoom, pan, Smart Click, Smart Lasso
├── tests/
│   ├── test_converter.py
│   ├── test_web_app.py
│   ├── test_apple_subject_lift.py
│   └── test_object_isolation_web.py
├── requirements.txt
└── start.command
```
