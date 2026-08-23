# Aseprite Image Pixel Converter

A small local Python utility for converting large PNG/reference images into smaller, palette-limited PNGs that are easier to refine manually in Aseprite.

The intended workflow is:

```text
large reference PNG
        ↓
crop transparent margins
        ↓
resize to a small canvas
        ↓
reduce to a controlled palette
        ↓
harden transparency
        ↓
Aseprite-ready PNG for manual cleanup
```

This tool does **not** attempt to create finished pixel art automatically. It prepares a constrained starting image so the final outlines, clusters, details, palette, and artistic decisions can be refined in Aseprite.

## Current features

- Runs completely locally.
- Default output is `80 × 80`.
- Default palette limit is 16 colors.
- Preserves transparent backgrounds.
- Crops transparent margins by default.
- Preserves aspect ratio and centers the sprite.
- Hardens alpha to fully transparent/opaque pixels by default.
- Supports Nearest Neighbor, Box, and Lanczos downscaling.
- Optional Floyd–Steinberg dithering.
- Supports non-square output sizes.
- Includes unit tests.

## Requirements

- Python 3.10+
- Pillow

## Setup on macOS

From the repository folder on `development`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

Whenever you open a new Terminal later, reactivate the environment with:

```bash
source .venv/bin/activate
```

## Basic conversion

```bash
python3 aseprite_image_pixel_converter.py input.png output.png --size 80 --colors 16
```

Example using files in Downloads:

```bash
python3 aseprite_image_pixel_converter.py \
  ~/Downloads/machine.png \
  ~/Downloads/machine-80x80.png \
  --size 80 \
  --colors 16
```

Then open the output PNG in Aseprite and clean/refine it manually.

## Compare resizing methods

Nearest Neighbor is the default:

```bash
python3 aseprite_image_pixel_converter.py input.png nearest.png --size 80 --colors 16 --resample nearest
```

For very large generated/reference images, `box` can sometimes preserve the overall silhouette better:

```bash
python3 aseprite_image_pixel_converter.py input.png box.png --size 80 --colors 16 --resample box
```

Lanczos retains more averaged shape information before palette reduction:

```bash
python3 aseprite_image_pixel_converter.py input.png lanczos.png --size 80 --colors 16 --resample lanczos
```

Compare the results in Aseprite rather than assuming one method is always best.

## Other options

Different square size:

```bash
python3 aseprite_image_pixel_converter.py input.png output.png --size 64 --colors 12
```

Rectangular output:

```bash
python3 aseprite_image_pixel_converter.py input.png output.png --width 64 --height 96 --colors 16
```

Enable dithering:

```bash
python3 aseprite_image_pixel_converter.py input.png output.png --dither floyd
```

Keep semi-transparent pixels:

```bash
python3 aseprite_image_pixel_converter.py input.png output.png --keep-soft-alpha
```

Keep original transparent margins:

```bash
python3 aseprite_image_pixel_converter.py input.png output.png --no-crop
```

Show every CLI option:

```bash
python3 aseprite_image_pixel_converter.py --help
```

## Run tests

```bash
python3 -m unittest discover -s tests -v
```

## Branch policy

- `main` is the stable backup branch and is not changed during normal development.
- `development` is the normal integration branch.
- Temporary feature/fix branches should be created only when useful and removed after approved integration.
