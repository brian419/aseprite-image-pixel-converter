from __future__ import annotations

import argparse
from pathlib import Path
from typing import Literal

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ResampleName = Literal["nearest", "box", "hamming", "bicubic", "lanczos", "detail"]
DitherName = Literal["none", "floyd"]


def _resample_filter(name: ResampleName) -> Image.Resampling:
    return {
        "nearest": Image.Resampling.NEAREST,
        "box": Image.Resampling.BOX,
        "hamming": Image.Resampling.HAMMING,
        "bicubic": Image.Resampling.BICUBIC,
        "lanczos": Image.Resampling.LANCZOS,
    }[name]


def _dither_mode(name: DitherName) -> Image.Dither:
    return {
        "none": Image.Dither.NONE,
        "floyd": Image.Dither.FLOYDSTEINBERG,
    }[name]


def _visible_bbox(image: Image.Image, alpha_threshold: int) -> tuple[int, int, int, int]:
    alpha = image.getchannel("A")
    binary = alpha.point(lambda value: 255 if value > alpha_threshold else 0)
    bbox = binary.getbbox()
    if bbox is None:
        raise ValueError("The input image contains no visible pixels.")
    return bbox


def _fit_size(source: tuple[int, int], target: tuple[int, int]) -> tuple[int, int]:
    source_w, source_h = source
    target_w, target_h = target
    scale = min(target_w / source_w, target_h / source_h)
    return max(1, round(source_w * scale)), max(1, round(source_h * scale))


def _edge_coordinates(size: tuple[int, int]) -> list[tuple[int, int]]:
    width, height = size
    step = max(1, min(width, height) // 128)
    coordinates: list[tuple[int, int]] = []
    for x in range(0, width, step):
        coordinates.append((x, 0))
        coordinates.append((x, height - 1))
    for y in range(0, height, step):
        coordinates.append((0, y))
        coordinates.append((width - 1, y))
    coordinates.extend(
        [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]
    )
    return coordinates


def _dominant_edge_color(source: Image.Image) -> tuple[tuple[int, int, int], int] | None:
    rgba = source.convert("RGBA")
    pixels = rgba.load()
    coordinates = _edge_coordinates(rgba.size)
    border_alphas = [pixels[x, y][3] for x, y in coordinates]

    # If the border already contains meaningful transparency, trust the source alpha
    # instead of trying to infer and remove another background.
    transparent_samples = sum(alpha < 250 for alpha in border_alphas)
    if transparent_samples >= max(1, len(border_alphas) // 20):
        return None

    samples = [
        pixels[x, y][:3]
        for x, y in coordinates
        if pixels[x, y][3] >= 250
    ]
    if not samples:
        return None

    sample_image = Image.new("RGB", (len(samples), 1))
    sample_image.putdata(samples)
    quantized = sample_image.quantize(
        colors=min(8, len(samples)),
        method=Image.Quantize.MEDIANCUT,
    )
    counts = quantized.getcolors() or []
    if not counts:
        return None
    dominant_index = max(counts, key=lambda item: item[0])[1]
    palette = quantized.getpalette()
    if palette is None:
        return None
    start = dominant_index * 3
    background = tuple(palette[start : start + 3])

    deviations = sorted(
        max(
            abs(red - background[0]),
            abs(green - background[1]),
            abs(blue - background[2]),
        )
        for red, green, blue in samples
    )
    percentile_index = min(len(deviations) - 1, int((len(deviations) - 1) * 0.90))
    tolerance = max(18, min(48, deviations[percentile_index] + 12))
    return (background[0], background[1], background[2]), tolerance


def _edge_connected_background_mask(candidates: Image.Image) -> Image.Image:
    """Return a protected edge-connected subset of a candidate background mask.

    Candidate background is first eroded before flood filling. This deliberately
    closes narrow background-colored passages through a dense foreground object,
    preventing the flood from tunneling into dark recesses or tiny mechanical gaps.
    The confirmed exterior is then expanded only a few pixels and only inside the
    original candidate mask, recovering a clean outer edge without reopening those
    narrow passages.
    """

    width, height = candidates.size
    minimum_side = min(width, height)
    guard_radius = max(1, min(3, minimum_side // 256))
    guard_size = guard_radius * 2 + 1

    protected_core = candidates.filter(ImageFilter.MinFilter(guard_size))
    flood = protected_core.copy()
    pixels = flood.load()

    for x in range(width):
        if pixels[x, 0] == 255:
            ImageDraw.floodfill(flood, (x, 0), 128)
        if pixels[x, height - 1] == 255:
            ImageDraw.floodfill(flood, (x, height - 1), 128)
    for y in range(height):
        if pixels[0, y] == 255:
            ImageDraw.floodfill(flood, (0, y), 128)
        if pixels[width - 1, y] == 255:
            ImageDraw.floodfill(flood, (width - 1, y), 128)

    confirmed = flood.point(lambda value: 255 if value == 128 else 0)
    for _ in range(guard_radius):
        expanded = confirmed.filter(ImageFilter.MaxFilter(3))
        confirmed = ImageChops.multiply(expanded, candidates)

    return confirmed


def auto_remove_background(source: Image.Image) -> Image.Image:
    """Make an inferred outer background transparent when it can be removed safely.

    Existing transparent borders are preserved as-is. For opaque images, the
    dominant border color is estimated. Similar pixels are treated as background
    candidates, but a small foreground-protection barrier is applied before the
    outer flood fill so narrow dark seams and recesses inside complex models are
    much less likely to become accidental transparency.
    """

    source = source.convert("RGBA")
    inference = _dominant_edge_color(source)
    if inference is None:
        return source

    background, tolerance = inference
    rgb = source.convert("RGB")
    difference = ImageChops.difference(
        rgb,
        Image.new("RGB", source.size, background),
    )
    red_diff, green_diff, blue_diff = difference.split()
    max_diff = ImageChops.lighter(
        ImageChops.lighter(red_diff, green_diff),
        blue_diff,
    )
    candidates = max_diff.point(lambda value: 255 if value <= tolerance else 0)
    removed_background = _edge_connected_background_mask(candidates)

    alpha = ImageChops.subtract(source.getchannel("A"), removed_background)
    result = source.copy()
    result.putalpha(alpha)
    return result


def _detail_preserving_resize(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Downscale dense references with high-quality resampling plus restrained sharpening."""

    resized = image.resize(
        size,
        Image.Resampling.LANCZOS,
        reducing_gap=3.0,
    )
    alpha = resized.getchannel("A")
    sharpened_rgb = resized.convert("RGB").filter(
        ImageFilter.UnsharpMask(radius=0.8, percent=175, threshold=2)
    )
    result = sharpened_rgb.convert("RGBA")
    result.putalpha(alpha)
    return result


def convert_pil_image(
    source: Image.Image,
    *,
    width: int = 128,
    height: int = 128,
    colors: int | None = None,
    alpha_threshold: int = 8,
    resample: ResampleName = "nearest",
    dither: DitherName = "none",
    crop_transparent: bool = False,
    hard_alpha: bool = True,
    remove_background: bool = True,
) -> Image.Image:
    """Return a resized RGBA image suitable for inspection and refinement in Aseprite.

    The converter attempts to make an inferred opaque outer background transparent.
    Transparent margins are otherwise preserved by default. RGB colors produced
    by resizing are preserved unless ``colors`` is provided to intentionally
    limit the palette.
    """
    if width < 1 or height < 1:
        raise ValueError("width and height must both be at least 1.")
    if colors is not None and not 2 <= colors <= 256:
        raise ValueError("colors must be between 2 and 256 when palette limiting is enabled.")
    if not 0 <= alpha_threshold <= 254:
        raise ValueError("alpha_threshold must be between 0 and 254.")
    if resample not in {"nearest", "box", "hamming", "bicubic", "lanczos", "detail"}:
        raise ValueError("Unknown resize method.")
    if dither not in {"none", "floyd"}:
        raise ValueError("Unknown dithering mode.")

    source = source.convert("RGBA")
    if remove_background:
        source = auto_remove_background(source)

    visible_bbox = _visible_bbox(source, alpha_threshold)
    working = source.crop(visible_bbox) if crop_transparent else source

    fitted_size = _fit_size(working.size, (width, height))
    if resample == "detail":
        resized = _detail_preserving_resize(working, fitted_size)
    else:
        resized = working.resize(fitted_size, _resample_filter(resample))

    if hard_alpha:
        alpha = resized.getchannel("A").point(
            lambda value: 255 if value > alpha_threshold else 0
        )
    else:
        alpha = resized.getchannel("A")

    if colors is None:
        converted = resized.convert("RGBA")
    else:
        converted = resized.convert("RGB").quantize(
            colors=colors,
            method=Image.Quantize.MEDIANCUT,
            dither=_dither_mode(dither),
        ).convert("RGBA")

    converted.putalpha(alpha)

    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    x = (width - converted.width) // 2
    y = (height - converted.height) // 2
    canvas.alpha_composite(converted, (x, y))
    return canvas


def convert_image(
    input_path: str | Path,
    output_path: str | Path,
    *,
    width: int = 128,
    height: int = 128,
    colors: int | None = None,
    alpha_threshold: int = 8,
    resample: ResampleName = "nearest",
    dither: DitherName = "none",
    crop_transparent: bool = False,
    hard_alpha: bool = True,
    remove_background: bool = True,
) -> Path:
    """Convert a file on disk and save the resulting PNG."""
    input_path = Path(input_path)
    output_path = Path(output_path)

    with Image.open(input_path) as opened:
        result = convert_pil_image(
            opened,
            width=width,
            height=height,
            colors=colors,
            alpha_threshold=alpha_threshold,
            resample=resample,
            dither=dither,
            crop_transparent=crop_transparent,
            hard_alpha=hard_alpha,
            remove_background=remove_background,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, format="PNG", optimize=False)
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Resize reference images into crisp low-resolution PNGs for Aseprite, "
            "with automatic background transparency and optional palette limiting."
        )
    )
    parser.add_argument("input", help="Path to the source image.")
    parser.add_argument("output", help="Path for the converted PNG.")
    parser.add_argument("--size", type=int, default=128, help="Square output size. Default: 128.")
    parser.add_argument("--width", type=int, help="Output width. Overrides --size.")
    parser.add_argument("--height", type=int, help="Output height. Overrides --size.")
    parser.add_argument(
        "--colors",
        type=int,
        default=None,
        help="Optional palette limit, 2-256. Omit to preserve resized colors.",
    )
    parser.add_argument(
        "--resample",
        choices=("nearest", "detail", "box", "hamming", "bicubic", "lanczos"),
        default="nearest",
        help="Downscaling method. Default: nearest (recommended).",
    )
    parser.add_argument(
        "--dither",
        choices=("none", "floyd"),
        default="none",
        help="Palette dithering when --colors is used. Default: none.",
    )
    parser.add_argument(
        "--alpha-threshold",
        type=int,
        default=8,
        help="Alpha values at or below this become transparent. Default: 8.",
    )
    parser.add_argument(
        "--keep-soft-alpha",
        action="store_true",
        help="Preserve semi-transparent pixels instead of hardening alpha to 0/255.",
    )
    parser.add_argument(
        "--keep-background",
        action="store_true",
        help="Skip automatic outer-background transparency.",
    )
    parser.add_argument(
        "--crop",
        action="store_true",
        help="Explicitly crop transparent margins before fitting the image.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    width = args.width if args.width is not None else args.size
    height = args.height if args.height is not None else args.size

    output = convert_image(
        args.input,
        args.output,
        width=width,
        height=height,
        colors=args.colors,
        alpha_threshold=args.alpha_threshold,
        resample=args.resample,
        dither=args.dither,
        crop_transparent=args.crop,
        hard_alpha=not args.keep_soft_alpha,
        remove_background=not args.keep_background,
    )
    color_note = "preserved resized colors" if args.colors is None else f"max {args.colors} visible RGB colors"
    print(f"Saved {output} ({width}x{height}, {color_note})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
