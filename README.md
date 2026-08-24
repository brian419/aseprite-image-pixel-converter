# Aseprite Image Pixel Converter

A local macOS utility for converting large reference images into crisp, low-resolution PNGs for refinement in Aseprite.

The app supports both whole-image conversion and smart single-subject isolation. In smart mode, the user can click a foreground subject or draw a loose lasso around it. The selected subject is isolated with the rest of the image made transparent, then passed through the same pixel conversion pipeline.

The user-facing interface describes this simply as **Smart subject isolation** and **Runs locally on this Mac**. Internally, the current macOS implementation uses Apple's Vision framework through a small native Swift helper.

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
smart subject detection identifies the foreground subject under the click
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
smart subject detection finds foreground subjects inside the loop
    ↓
the best-matching detected subject is isolated
    ↓
subject is pixel-converted and saved
```

Smart Lasso is intentionally a rough-selection tool. The user does not need to trace the exact object edge. The lasso is used to choose among the foreground subjects already detected by the local subject-isolation system.

## Features

- Local browser interface served from `127.0.0.1:8765`.
- Existing whole-image automatic outer-background transparency remains available.
- Smart Click subject isolation by clicking directly on the desired object.
- Smart Lasso subject isolation using a loose freeform loop.
- Click tolerance near thin branches, hair, edge pixels, and small holes by searching a small nearby region when the exact click lands on background.
- No cloud API and no external segmentation model download.
- No PyTorch, OpenCV, or model checkpoint required for subject isolation.
- Isolated subject is reused for resize and palette preview changes instead of rerunning detection every time.
- Transparent subject is automatically cropped before fitting to the requested output canvas.
- Linked Source Image and Output Preview views.
- Smart Click, Smart Lasso, Pan, and Clear controls placed below the Source Image so the two comparison views remain vertically aligned.
- Smart subject status card with a local-processing badge and current selection status.
- Synchronized zoom and pan between source and output views.
- Preview zoom up to 6400%.
- Preserve resized colors by default or optionally limit the palette to 2-256 colors.
- Nearest, Detail Preserve, Lanczos, Bicubic, Hamming, and Box resize methods.
- Native macOS folder chooser.
- Configurable output width and height.
- Editable generated filename before saving.
- Existing command-line whole-image converter remains available.

## Platform support

The browser/Python converter is local. Smart Click and Smart Lasso currently use the macOS Vision framework internally.

Smart subject isolation requires:

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

There is no OpenCV dependency in the current smart-subject implementation.

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
4. Wait for the local smart-subject detector to isolate it.
5. The Output Preview shows only the selected subject after pixel conversion.
6. If the wrong subject was selected, choose **Smart Click** below the Source Image and click a different location.
7. Use **Pan** when you want to navigate the linked comparison views without selecting another subject.
8. Use **Clear** to discard the current selection.
9. Choose a save folder and convert.

A click does not need to land on the exact center. If the exact point is background, the helper searches a small nearby area for the nearest detected foreground subject. This helps with foliage, branches, hair, and narrow object edges.

## Using Smart Lasso

1. Choose **One subject - Smart Lasso**.
2. Draw a rough loop around the object in the Source Image.
3. The local subject detector identifies foreground subjects in the image.
4. The helper determines which detected subject occupies the largest useful portion of the lasso.
5. The selected subject is isolated with transparency and sent through the normal converter.

Smart Lasso is useful when a click is ambiguous or when several detected subjects are close together. The lasso does not define the final cutout boundary, so it does not need to trace the object precisely.

## User interface behavior

The comparison area keeps Source Image and Output Preview aligned at the top. When a smart subject mode is enabled, its controls appear below the Source Image rather than above it.

The smart-subject settings card contains:

- **Smart subject isolation**
- **Runs locally on this Mac**
- A short mode-specific instruction
- **Selection status**, which reports whether a subject is selected or whether another selection is needed

The user-facing UI intentionally avoids exposing framework-specific implementation branding. Technical implementation details remain documented below.

## Technical implementation of smart subject isolation

The native helper uses Apple's Vision framework:

1. `VNGenerateForegroundInstanceMaskRequest` detects noticeable foreground instances.
2. `VNInstanceMaskObservation.instanceMask` labels detected subjects separately from background.
3. Smart Click maps the browser click into Vision coordinates and reads the instance label under or near that point.
4. Smart Lasso maps the freeform polygon into the instance mask and chooses the most represented non-background instance.
5. `generateMaskedImage(ofInstances:from:croppedToInstancesExtent:)` produces an image containing only the selected instance, with the remaining pixels transparent.
6. Pillow receives that transparent PNG and the existing converter crops, resizes, centers, and optionally palette-limits it.

The app performs the expensive subject-detection step only when the user chooses a subject. The returned transparent PNG is retained in browser memory and reused when output size, palette, or resize settings change.

All of this processing stays on the local Mac. Images are not sent to an external service.

## Automatic whole-image background transparency

Whole-image mode keeps the existing conservative background inference. For opaque images, the converter estimates the dominant outer-border color and removes confirmed edge-connected background pixels while protecting narrow interior gaps from accidental transparency.

Highly textured or photographic backgrounds are where Smart Click is usually more appropriate.

## Output settings

### Canvas size

Set the target pixel dimensions manually or use the included presets such as 64, 80, 96, 128, and 160 pixels.

### Color handling

- **Preserve resized colors** keeps the colors produced by the resize operation without applying a palette limit.
- **Limit palette** enables the Palette colors field, which accepts values from 2 to 256.

### Resize methods

- **Nearest - Recommended**: normal pixel-art reduction with hard pixel sampling.
- **Detail Preserve - complex art**: high-quality reduction with controlled sharpening for dense references.
- **Lanczos**: detailed interpolation during strong downscaling.
- **Bicubic**: balanced interpolation.
- **Hamming**: somewhat sharper interpolated reduction.
- **Box**: simple area averaging.

## Generated filenames

Whole-image example:

```text
source-128x128-nearest-preserve.png
```

Smart subject example:

```text
source-128x128-nearest-isolated-preserve.png
```

Palette-limited smart subject example:

```text
source-128x128-nearest-isolated-32c.png
```

The filename remains editable before saving.

## Command-line converter

The existing CLI continues to provide the whole-image workflow:

```bash
python3 aseprite_image_pixel_converter.py input.png output.png --size 128
```

Detail-preserving resize:

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

The Python subject-wrapper tests mock the native process so validation can run independently of the macOS Vision framework. The real native subject-isolation helper requires a macOS 14+ machine for end-to-end execution.

## Project structure

```text
aseprite-image-pixel-converter/
├── aseprite_image_pixel_converter.py   # pixel conversion logic and CLI
├── apple_subject_lift.py               # Python validation and native-helper bridge
├── native/
│   └── apple_subject_lift.swift        # native macOS foreground-instance selector
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

## Privacy

The web interface is served only from localhost. Smart subject detection and pixel conversion run locally on the Mac. The application does not require a cloud image-processing API.
