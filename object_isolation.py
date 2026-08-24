from __future__ import annotations

from collections.abc import Sequence
from typing import TypeAlias

import cv2 as cv
import numpy as np
from PIL import Image

NormalizedRect: TypeAlias = tuple[float, float, float, float]
NormalizedPoint: TypeAlias = tuple[float, float]


def _unit_value(value: float, name: str) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number between 0 and 1.") from exc
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1.")
    return value


def _normalize_rect(rect: Sequence[float]) -> NormalizedRect:
    if len(rect) != 4:
        raise ValueError("The selection rectangle must contain x, y, width, and height.")

    x = _unit_value(rect[0], "selection x")
    y = _unit_value(rect[1], "selection y")
    width = _unit_value(rect[2], "selection width")
    height = _unit_value(rect[3], "selection height")

    if width <= 0.0 or height <= 0.0:
        raise ValueError("Draw a selection box around the object first.")
    if x + width > 1.000001 or y + height > 1.000001:
        raise ValueError("The selection box must stay inside the source image.")
    return x, y, width, height


def _normalize_points(points: Sequence[Sequence[float]], name: str) -> list[NormalizedPoint]:
    normalized: list[NormalizedPoint] = []
    if len(points) > 200:
        raise ValueError(f"{name} supports at most 200 refinement marks.")

    for point in points:
        if len(point) != 2:
            raise ValueError(f"Each {name} mark must contain x and y.")
        normalized.append((
            _unit_value(point[0], f"{name} x"),
            _unit_value(point[1], f"{name} y"),
        ))
    return normalized


def _working_size(size: tuple[int, int], maximum_side: int) -> tuple[int, int]:
    width, height = size
    largest = max(width, height)
    if largest <= maximum_side:
        return width, height

    scale = maximum_side / largest
    return max(2, round(width * scale)), max(2, round(height * scale))


def _pixel_rect(rect: NormalizedRect, size: tuple[int, int]) -> tuple[int, int, int, int]:
    width, height = size
    x, y, rect_w, rect_h = rect

    left = min(width - 1, max(0, round(x * width)))
    top = min(height - 1, max(0, round(y * height)))
    right = min(width, max(left + 1, round((x + rect_w) * width)))
    bottom = min(height, max(top + 1, round((y + rect_h) * height)))

    if right - left < 2 or bottom - top < 2:
        raise ValueError("The selection box is too small. Draw a larger box around the object.")
    return left, top, right, bottom


def _point_pixel(point: NormalizedPoint, size: tuple[int, int]) -> tuple[int, int]:
    width, height = size
    x = min(width - 1, max(0, round(point[0] * (width - 1))))
    y = min(height - 1, max(0, round(point[1] * (height - 1))))
    return x, y


def isolate_object(
    source: Image.Image,
    *,
    selection_rect: Sequence[float],
    keep_points: Sequence[Sequence[float]] = (),
    remove_points: Sequence[Sequence[float]] = (),
    refine_radius: float = 0.018,
    iterations: int = 5,
    maximum_side: int = 1200,
) -> Image.Image:
    """Return an RGBA copy with only the interactively selected object visible.

    Coordinates are normalized to the original image. A selection rectangle gives
    GrabCut its initial probable foreground region. Optional keep/remove marks are
    hard foreground/background hints for refinement.
    """
    if iterations < 1 or iterations > 12:
        raise ValueError("iterations must be between 1 and 12.")
    if maximum_side < 128 or maximum_side > 4096:
        raise ValueError("maximum_side must be between 128 and 4096.")

    rect = _normalize_rect(selection_rect)
    keeps = _normalize_points(keep_points, "keep")
    removes = _normalize_points(remove_points, "remove")

    try:
        refine_radius = float(refine_radius)
    except (TypeError, ValueError) as exc:
        raise ValueError("refine_radius must be a number between 0.002 and 0.08.") from exc
    if not 0.002 <= refine_radius <= 0.08:
        raise ValueError("refine_radius must be between 0.002 and 0.08.")

    rgba = source.convert("RGBA")
    original_width, original_height = rgba.size
    if original_width < 2 or original_height < 2:
        raise ValueError("The source image is too small for object isolation.")

    work_width, work_height = _working_size(rgba.size, maximum_side)
    if (work_width, work_height) == rgba.size:
        working = rgba
    else:
        working = rgba.resize((work_width, work_height), Image.Resampling.LANCZOS)

    rgb = np.asarray(working.convert("RGB"), dtype=np.uint8)
    bgr = cv.cvtColor(rgb, cv.COLOR_RGB2BGR)

    mask = np.full((work_height, work_width), cv.GC_BGD, dtype=np.uint8)
    left, top, right, bottom = _pixel_rect(rect, (work_width, work_height))
    mask[top:bottom, left:right] = cv.GC_PR_FGD

    source_alpha = np.asarray(working.getchannel("A"), dtype=np.uint8)
    mask[source_alpha == 0] = cv.GC_BGD

    brush_radius = max(1, round(min(work_width, work_height) * refine_radius))

    for point in keeps:
        x, y = _point_pixel(point, (work_width, work_height))
        cv.circle(mask, (x, y), brush_radius, int(cv.GC_FGD), thickness=-1)

    for point in removes:
        x, y = _point_pixel(point, (work_width, work_height))
        cv.circle(mask, (x, y), brush_radius, int(cv.GC_BGD), thickness=-1)

    # Transparent source pixels always remain background, even if a mark crosses them.
    mask[source_alpha == 0] = cv.GC_BGD

    background_model = np.zeros((1, 65), dtype=np.float64)
    foreground_model = np.zeros((1, 65), dtype=np.float64)

    try:
        cv.grabCut(
            bgr,
            mask,
            None,
            background_model,
            foreground_model,
            iterations,
            cv.GC_INIT_WITH_MASK,
        )
    except cv.error as exc:
        raise ValueError(
            "Object isolation could not separate this selection. Try a tighter box "
            "and add Keep or Remove marks."
        ) from exc

    visible = np.where(
        (mask == cv.GC_FGD) | (mask == cv.GC_PR_FGD),
        255,
        0,
    ).astype(np.uint8)

    if not np.any(visible):
        raise ValueError(
            "Object isolation found no foreground. Try a larger box or add a Keep mark."
        )

    if (work_width, work_height) != rgba.size:
        visible_image = Image.fromarray(visible, mode="L").resize(
            rgba.size,
            Image.Resampling.NEAREST,
        )
        visible = np.asarray(visible_image, dtype=np.uint8)

    original_alpha = np.asarray(rgba.getchannel("A"), dtype=np.uint8)
    final_alpha = np.minimum(original_alpha, visible)

    result = rgba.copy()
    result.putalpha(Image.fromarray(final_alpha, mode="L"))
    return result
