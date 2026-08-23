# Aseprite Image Pixel Converter

A local macOS-friendly utility for turning large reference images into smaller, palette-limited PNGs that are easier to refine manually in Aseprite.

The primary experience is a local browser app:

```text
drag in an image
        ↓
choose canvas size and palette
        ↓
choose an output folder
        ↓
click Convert Image
        ↓
open the result in Aseprite
```

The converter runs on your own Mac. It does not upload source images to an external service.

## Easiest way to run it

After pulling the latest `development` branch, open the repository in Finder and double-click:

```text
start.command
```

The launcher will:

1. create a local `.venv` if needed,
2. install/update the small Python dependencies if they are missing,
3. start the local converter,
4. open the app in your default browser.

Keep the Terminal window opened by `start.command` running while you use the app. Close it or press Control-C when you are finished.

The local app runs at:

```text
http://127.0.0.1:8765
```

## GUI features

- Drag-and-drop image input.
- Click-to-browse image input.
- Source preview.
- Simple 64, 80, and 96 pixel presets.
- Custom width and height.
- Configurable palette size.
- Resize method selector.
- Editable output filename.
- Folder picker in supported Chromium browsers such as Brave.
- Standard browser download fallback if a folder is not selected.
- Advanced transparency and dithering controls kept out of the main workflow.
- Light and dark appearance using native system preferences.
- Uses the macOS system font stack and restrained, platform-oriented UI styling.

## Default conversion behavior

The GUI starts with:

- `80 × 80` output.
- 16 visible RGB colors maximum.
- Box resampling, which is often a useful starting point for very large reference images.
- Transparent margins cropped before resize.
- Hard transparent/opaque output edges.
- No dithering.

The goal is not automatic finished pixel art. The output is a smaller, controlled starting image for manual Aseprite cleanup.

## Requirements

- macOS or another system with Python 3.10+
- Flask
- Pillow

`start.command` handles the virtual environment and package installation for normal use.

## Terminal launch, if needed

You can also start the GUI manually:

```bash
source .venv/bin/activate
python3 web_app.py
```

## Command-line converter

The original CLI remains available for advanced or scripted use:

```bash
python3 aseprite_image_pixel_converter.py input.png output.png --size 80 --colors 16
```

Show every CLI option:

```bash
python3 aseprite_image_pixel_converter.py --help
```

## Run tests

```bash
source .venv/bin/activate
python3 -m unittest discover -s tests -v
```

## Branch policy

- `main` is the stable backup branch and is not changed during normal development.
- `development` is the normal integration branch.
- Temporary feature/fix branches should be created only when useful and removed after approved integration.
