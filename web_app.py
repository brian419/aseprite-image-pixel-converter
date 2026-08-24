from __future__ import annotations

import io
import json
import logging
import re
import subprocess
import threading
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, request, send_file
from PIL import Image, UnidentifiedImageError
from waitress import serve

from aseprite_image_pixel_converter import auto_remove_background, convert_pil_image
from object_isolation import isolate_object

APP_HOST = "127.0.0.1"
APP_PORT = 8765
APP_URL = f"http://{APP_HOST}:{APP_PORT}"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

app = Flask(__name__, static_folder="web", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

_selected_output_directory: Path | None = None


def _int_form(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = request.form.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a whole number.") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return value


def _float_form(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = request.form.get(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number.") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return value


def _json_form(name: str, default):
    raw = request.form.get(name)
    if raw is None or raw == "":
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} contains invalid selection data.") from exc


def _isolation_mode() -> str:
    mode = request.form.get("isolation_mode", "auto")
    if mode not in {"auto", "object"}:
        raise ValueError("Unknown object isolation mode.")
    return mode


def _safe_stem(filename: str) -> str:
    stem = Path(filename).stem.strip() or "converted-image"
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "-", stem)
    return stem[:100] or "converted-image"


def _safe_output_name(
    requested: str,
    source_name: str,
    width: int,
    height: int,
    colors: int | None,
    resample: str,
    dither: str,
    isolated: bool = False,
) -> str:
    requested = requested.strip()
    if requested.lower().endswith(".png"):
        name = Path(requested).name
        stem = _safe_stem(name)
        return f"{stem}.png" if not stem.lower().endswith(".png") else stem

    parts = [_safe_stem(source_name), f"{width}x{height}", resample]
    if isolated:
        parts.append("isolated")
    if colors is None:
        parts.append("preserve")
    else:
        parts.append(f"{colors}c")
        if dither == "floyd":
            parts.append("floyd")
    return "-".join(parts) + ".png"


def _choose_output_folder() -> Path | None:
    script = 'POSIX path of (choose folder with prompt "Choose where the converted image should be saved")'
    completed = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if completed.returncode == 0:
        path = Path(completed.stdout.strip()).expanduser()
        if path.is_dir():
            return path.resolve()
        raise RuntimeError("The selected folder is invalid.")

    error_text = completed.stderr.strip()
    if "User canceled" in error_text or "(-128)" in error_text:
        return None
    raise RuntimeError(error_text or "Could not open the folder chooser.")


def _read_uploaded_rgba() -> tuple[Image.Image, str]:
    upload = request.files.get("image")
    if upload is None or not upload.filename:
        raise ValueError("Choose an image first.")

    with Image.open(upload.stream) as opened:
        source = opened.convert("RGBA")

    return source, upload.filename


def _isolate_if_requested(source: Image.Image) -> tuple[Image.Image, bool]:
    mode = _isolation_mode()
    if mode == "auto":
        return source, False

    selection_rect = _json_form("selection_rect", None)
    if selection_rect is None:
        raise ValueError("Draw a selection box around the object first.")

    keep_points = _json_form("keep_points", [])
    remove_points = _json_form("remove_points", [])
    refine_radius = _float_form("refine_radius", 0.018, 0.002, 0.08)

    isolated = isolate_object(
        source,
        selection_rect=selection_rect,
        keep_points=keep_points,
        remove_points=remove_points,
        refine_radius=refine_radius,
    )
    return isolated, True


def _convert_request_image() -> tuple[Image.Image, str, int, int, int | None, bool]:
    source, source_name = _read_uploaded_rgba()
    source, isolated = _isolate_if_requested(source)

    width = _int_form("width", 128, 8, 1024)
    height = _int_form("height", 128, 8, 1024)
    alpha_threshold = _int_form("alpha_threshold", 8, 0, 254)

    color_mode = request.form.get("color_mode", "preserve")
    if color_mode not in {"preserve", "limit"}:
        raise ValueError("Unknown color handling mode.")
    colors = _int_form("colors", 32, 2, 256) if color_mode == "limit" else None

    resample = request.form.get("resample", "nearest")
    if resample not in {"nearest", "detail", "box", "hamming", "bicubic", "lanczos"}:
        raise ValueError("Unknown resize method.")

    dither = request.form.get("dither", "none")
    if dither not in {"none", "floyd"}:
        raise ValueError("Unknown dithering mode.")

    result = convert_pil_image(
        source,
        width=width,
        height=height,
        colors=colors,
        alpha_threshold=alpha_threshold,
        resample=resample,
        dither=dither,
        crop_transparent=False,
        hard_alpha=True,
        remove_background=not isolated,
    )
    return result, source_name, width, height, colors, isolated


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.post("/api/choose-folder")
def choose_folder():
    global _selected_output_directory
    try:
        selected = _choose_output_folder()
        if selected is None:
            return jsonify({"cancelled": True})
        _selected_output_directory = selected
        return jsonify({"cancelled": False, "path": str(selected), "name": selected.name or str(selected)})
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/api/source-preview")
def source_preview():
    try:
        source, _source_name = _read_uploaded_rgba()
        # In object-selection mode the unmodified source stays visible so the user
        # can draw and refine the selection against the full image.
        if _isolation_mode() == "auto":
            source = auto_remove_background(source)

        buffer = io.BytesIO()
        source.save(buffer, format="PNG", optimize=False)
        buffer.seek(0)
        response = send_file(buffer, mimetype="image/png", as_attachment=False)
        response.headers["Cache-Control"] = "no-store"
        return response
    except (ValueError, UnidentifiedImageError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/preview")
def preview():
    try:
        result, _source_name, _width, _height, _colors, _isolated = _convert_request_image()
        buffer = io.BytesIO()
        result.save(buffer, format="PNG", optimize=False)
        buffer.seek(0)
        response = send_file(buffer, mimetype="image/png", as_attachment=False)
        response.headers["Cache-Control"] = "no-store"
        return response
    except (ValueError, UnidentifiedImageError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/convert")
def convert():
    global _selected_output_directory

    if _selected_output_directory is None:
        return jsonify({"error": "Choose an output folder before converting."}), 400

    try:
        result, source_name, width, height, colors, isolated = _convert_request_image()
        resample = request.form.get("resample", "nearest")
        dither = request.form.get("dither", "none")
        output_name = _safe_output_name(
            request.form.get("output_name", ""),
            source_name,
            width,
            height,
            colors,
            resample,
            dither,
            isolated=isolated,
        )

        output_directory = _selected_output_directory
        output_path = output_directory / output_name
        result.save(output_path, format="PNG", optimize=False)
        _selected_output_directory = None

        return jsonify({
            "saved": True,
            "filename": output_name,
            "path": str(output_path),
        })

    except (ValueError, UnidentifiedImageError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "That image is too large. Maximum upload size is 50 MB."}), 413


def _open_browser() -> None:
    webbrowser.open(APP_URL)


if __name__ == "__main__":
    logging.getLogger("waitress").setLevel(logging.ERROR)
    threading.Timer(0.7, _open_browser).start()
    print(f"Aseprite Image Pixel Converter is running at {APP_URL}")
    print("Keep this Terminal window open while you use the app. Press Control-C to stop it.")
    serve(app, host=APP_HOST, port=APP_PORT, threads=4)
