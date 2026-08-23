from __future__ import annotations

import io
import re
import subprocess
import threading
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, request, send_file
from PIL import Image, UnidentifiedImageError

from aseprite_image_pixel_converter import convert_pil_image

APP_URL = "http://127.0.0.1:8765"
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


def _safe_stem(filename: str) -> str:
    stem = Path(filename).stem.strip() or "converted-image"
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "-", stem)
    return stem[:100] or "converted-image"


def _safe_output_name(requested: str, source_name: str, width: int, height: int, colors: int) -> str:
    requested = requested.strip()
    if requested.lower().endswith(".png"):
        name = Path(requested).name
        stem = _safe_stem(name)
        return f"{stem}.png" if not stem.lower().endswith(".png") else stem
    return f"{_safe_stem(source_name)}-{width}x{height}-{colors}c.png"


def _choose_native_folder() -> Path | None:
    script = 'POSIX path of (choose folder with prompt "Choose where converted images should be saved")'
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
        raise RuntimeError("The folder chooser returned an invalid folder.")

    error_text = completed.stderr.strip()
    if "User canceled" in error_text or "(-128)" in error_text:
        return None
    raise RuntimeError(error_text or "Could not open the folder chooser.")


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
        selected = _choose_native_folder()
        if selected is None:
            return jsonify({"cancelled": True})
        _selected_output_directory = selected
        return jsonify({"cancelled": False, "path": str(selected), "name": selected.name or str(selected)})
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/api/clear-folder")
def clear_folder():
    global _selected_output_directory
    _selected_output_directory = None
    return jsonify({"ok": True})


@app.post("/api/convert")
def convert():
    upload = request.files.get("image")
    if upload is None or not upload.filename:
        return jsonify({"error": "Choose an image first."}), 400

    try:
        width = _int_form("width", 80, 8, 1024)
        height = _int_form("height", 80, 8, 1024)
        colors = _int_form("colors", 16, 2, 256)
        alpha_threshold = _int_form("alpha_threshold", 8, 0, 254)

        resample = request.form.get("resample", "box")
        if resample not in {"nearest", "box", "lanczos"}:
            raise ValueError("Unknown resize method.")

        dither = request.form.get("dither", "none")
        if dither not in {"none", "floyd"}:
            raise ValueError("Unknown dithering mode.")

        crop_transparent = request.form.get("crop_transparent", "true") == "true"
        hard_alpha = request.form.get("hard_alpha", "true") == "true"

        with Image.open(upload.stream) as opened:
            source = opened.convert("RGBA")

        result = convert_pil_image(
            source,
            width=width,
            height=height,
            colors=colors,
            alpha_threshold=alpha_threshold,
            resample=resample,
            dither=dither,
            crop_transparent=crop_transparent,
            hard_alpha=hard_alpha,
        )

        output_name = _safe_output_name(
            request.form.get("output_name", ""),
            upload.filename,
            width,
            height,
            colors,
        )

        save_to_folder = request.form.get("save_to_folder", "false") == "true"
        if save_to_folder and _selected_output_directory is not None:
            output_path = _selected_output_directory / output_name
            result.save(output_path, format="PNG", optimize=False)
            return jsonify({
                "saved": True,
                "filename": output_name,
                "path": str(output_path),
                "folder": str(_selected_output_directory),
            })

        buffer = io.BytesIO()
        result.save(buffer, format="PNG", optimize=False)
        buffer.seek(0)
        response = send_file(
            buffer,
            mimetype="image/png",
            as_attachment=True,
            download_name=output_name,
        )
        response.headers["X-Output-Filename"] = output_name
        return response

    except (ValueError, UnidentifiedImageError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "That image is too large. Maximum upload size is 50 MB."}), 413


def _open_browser() -> None:
    webbrowser.open(APP_URL)


if __name__ == "__main__":
    threading.Timer(0.7, _open_browser).start()
    print(f"Aseprite Image Pixel Converter is running at {APP_URL}")
    print("Keep this Terminal window open while you use the app. Press Control-C to stop it.")
    app.run(host="127.0.0.1", port=8765, debug=False, use_reloader=False)
