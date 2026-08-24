from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from PIL import Image

SelectionMode = Literal["click", "lasso"]
NormalizedPoint = tuple[float, float]


class SubjectIsolationError(RuntimeError):
    """Raised when the native macOS subject-lifting helper cannot isolate a subject."""


def _unit_value(value: float, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number between 0 and 1.") from exc
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1.")
    return number


def _normalized_point(point: Sequence[float], name: str = "selection point") -> NormalizedPoint:
    if len(point) != 2:
        raise ValueError(f"{name} must contain x and y.")
    return _unit_value(point[0], f"{name} x"), _unit_value(point[1], f"{name} y")


def _normalized_lasso(points: Sequence[Sequence[float]]) -> list[NormalizedPoint]:
    if len(points) < 3:
        raise ValueError("Draw a lasso around the object first.")
    if len(points) > 800:
        raise ValueError("The lasso contains too many points. Draw a simpler loop around the object.")

    normalized = [_normalized_point(point, "lasso point") for point in points]

    # A tiny or effectively straight lasso does not provide enough area to select a subject.
    area = 0.0
    for index, (x1, y1) in enumerate(normalized):
        x2, y2 = normalized[(index + 1) % len(normalized)]
        area += x1 * y2 - x2 * y1
    if abs(area) * 0.5 < 0.00005:
        raise ValueError("Draw a larger lasso around the object.")
    return normalized


def _helper_path() -> Path:
    override = os.environ.get("ASEPRITE_SUBJECT_HELPER")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parent / ".build" / "apple_subject_lift"


def _request_payload(
    mode: SelectionMode,
    *,
    point: Sequence[float] | None,
    lasso: Sequence[Sequence[float]] | None,
) -> dict[str, object]:
    if mode == "click":
        if point is None:
            raise ValueError("Click the object you want to isolate first.")
        return {"mode": "click", "point": list(_normalized_point(point))}
    if mode == "lasso":
        if lasso is None:
            raise ValueError("Draw a lasso around the object first.")
        return {"mode": "lasso", "points": [list(item) for item in _normalized_lasso(lasso)]}
    raise ValueError("Unknown smart subject selection mode.")


def lift_subject(
    source: Image.Image,
    *,
    mode: SelectionMode,
    point: Sequence[float] | None = None,
    lasso: Sequence[Sequence[float]] | None = None,
    timeout_seconds: int = 90,
) -> Image.Image:
    """Return the Apple Vision foreground subject selected by a click or rough lasso.

    Browser selection coordinates use a top-left origin and values from 0 to 1.
    The native helper converts them to Vision coordinates, determines the detected
    foreground instance, and writes a transparent PNG containing only that subject.
    """

    if sys.platform != "darwin":
        raise SubjectIsolationError(
            "Smart subject isolation requires macOS 14 or newer because it uses Apple's local Vision framework."
        )

    helper = _helper_path()
    if not helper.is_file() or not os.access(helper, os.X_OK):
        raise SubjectIsolationError(
            "The Apple Vision subject helper is not built. Close the app and launch start.command again."
        )

    payload = _request_payload(mode, point=point, lasso=lasso)

    with tempfile.TemporaryDirectory(prefix="aseprite-subject-") as temp_dir:
        temp = Path(temp_dir)
        input_path = temp / "source.png"
        request_path = temp / "selection.json"
        output_path = temp / "subject.png"

        # Re-encode through Pillow so the native helper always receives an upright,
        # conventional PNG regardless of the original browser upload format.
        source.convert("RGBA").save(input_path, format="PNG", optimize=False)
        request_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

        try:
            completed = subprocess.run(
                [str(helper), str(input_path), str(request_path), str(output_path)],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SubjectIsolationError(
                "Apple Vision took too long to isolate this subject. Try a smaller image or a clearer subject."
            ) from exc

        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip()
            raise SubjectIsolationError(message or "Apple Vision could not isolate a subject from that selection.")
        if not output_path.is_file():
            raise SubjectIsolationError("Apple Vision did not produce an isolated subject image.")

        with Image.open(output_path) as opened:
            result = opened.convert("RGBA").copy()

    if result.getchannel("A").getbbox() is None:
        raise SubjectIsolationError("Apple Vision returned an empty subject mask. Try clicking nearer the object's center.")
    return result
