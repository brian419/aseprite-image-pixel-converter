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
from PIL import Image, ImageOps, UnidentifiedImageError
from waitress import serve

from apple_subject_lift import SubjectIsolationError, lift_subject
from aseprite_image_pixel_converter import auto_remove_background, convert_pil_image

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
    if mode not in {"auto", "smart_click", "smart_lasso"}:
        raise ValueError("Unknown smart subject isolation mode.")
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


def _read_uploaded_rgba(field_name: str = "image") -> tuple[Image.Image, str]:
    upload = request.files.get(field_name)
    if upload is None or not upload.filename:
        if field_name == "image":
            raise ValueError("Choose an image first.")
        raise ValueError(f"Missing uploaded {field_name} image.")

    with Image.open(upload.stream) as opened:
        source = ImageOps.exif_transpose(opened).convert("RGBA")

    return source, upload.filename


def _read_conversion_source() -> tuple[Image.Image, str, bool]:
    source, source_name = _read_uploaded_rgba("image")
    mode = _isolation_mode()

    isolated_upload = request.files.get("isolated_image")
    if isolated_upload is not None and isolated_upload.filename:
        with Image.open(isolated_upload.stream) as opened:
            isolated = ImageOps.exif_transpose(opened).convert("RGBA")
        if isolated.getchannel("A").getbbox() is None:
            raise ValueError("The isolated subject image contains no visible pixels.")
        return isolated, source_name, True

    if mode != "auto":
        raise ValueError("Select a subject in the Source Image before previewing or converting.")
    return source, source_name, False


def _convert_request_image() -> tuple[Image.Image, str, int, int, int | None, bool]:
    source, source_name, isolated = _read_conversion_source()

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
        crop_transparent=isolated,
        hard_alpha=True,
        remove_background=not isolated,
    )
    return result, source_name, width, height, colors, isolated


def _png_response(image: Image.Image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=False)
    buffer.seek(0)
    response = send_file(buffer, mimetype="image/png", as_attachment=False)
    response.headers["Cache-Control"] = "no-store"
    return response


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
        if _isolation_mode() == "auto":
            source = auto_remove_background(source)
        return _png_response(source)
    except (ValueError, UnidentifiedImageError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/isolate")
def isolate():
    try:
        source, _source_name = _read_uploaded_rgba()
        mode = _isolation_mode()
        if mode == "smart_click":
            selection_point = _json_form("selection_point", None)
            result = lift_subject(source, mode="click", point=selection_point)
        elif mode == "smart_lasso":
            lasso_points = _json_form("lasso_points", None)
            result = lift_subject(source, mode="lasso", lasso=lasso_points)
        else:
            raise ValueError("Choose Smart Click or Smart Lasso before selecting a subject.")
        return _png_response(result)
    except (ValueError, SubjectIsolationError, UnidentifiedImageError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/preview")
def preview():
    try:
        result, _source_name, _width, _height, _colors, _isolated = _convert_request_image()
        return _png_response(result)
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
