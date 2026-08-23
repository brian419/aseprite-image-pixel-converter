from __future__ import annotations

import argparse
from pathlib import Path
from typing import Literal

from PIL import Image

ResampleName = Literal["nearest", "box", "hamming", "bicubic", "lanczos"]
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


def convert_pil_image(
    source: Image.Image,
    *,
    width: int = 128,
    height: int = 128,
    colors: int | None = None,
    alpha_threshold: int = 8,
    resample: ResampleName = "nearest",
    dither: DitherName = "none",
    crop_transparent: bool = True,
    hard_alpha: bool = True,
) -> Image.Image:
    """Return a resized RGBA image suitable for inspection and refinement in Aseprite.

    By default the RGB colors produced by resizing are preserved. Pass ``colors``
    to intentionally quantize the visible image to a palette of 2-256 colors.
    """
    if width < 1 or height < 1:
        raise ValueError("width and height must both be at least 1.")
    if colors is not None and not 2 <= colors <= 256:
        raise ValueError("colors must be between 2 and 256 when palette limiting is enabled.")
    if not 0 <= alpha_threshold <= 254:
        raise ValueError("alpha_threshold must be between 0 and 254.")
    if resample not in {"nearest", "box", "hamming", "bicubic", "lanczos"}:
        raise ValueError("Unknown resize method.")
    if dither not in {"none", "floyd"}:
        raise ValueError("Unknown dithering mode.")

    source = source.convert("RGBA")
    working = source.crop(_visible_bbox(source, alpha_threshold)) if crop_transparent else source

    fitted_size = _fit_size(working.size, (width, height))
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
    crop_transparent: bool = True,
    hard_alpha: bool = True,
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
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, format="PNG", optimize=False)
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Resize reference images into crisp low-resolution PNGs for Aseprite, "
            "with optional palette limiting."
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
        choices=("nearest", "box", "hamming", "bicubic", "lanczos"),
        default="nearest",
        help="Downscaling filter. Default: nearest (recommended).",
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
        "--no-crop",
        action="store_true",
        help="Do not crop transparent margins before fitting the image.",
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
        crop_transparent=not args.no_crop,
        hard_alpha=not args.keep_soft_alpha,
    )
    color_note = "preserved resized colors" if args.colors is None else f"max {args.colors} visible RGB colors"
    print(f"Saved {output} ({width}x{height}, {color_note})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())