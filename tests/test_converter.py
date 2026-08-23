from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from aseprite_image_pixel_converter import (
    auto_remove_background,
    convert_image,
    convert_pil_image,
)


class ConverterTests(unittest.TestCase):
    def test_preserve_colors_is_default(self) -> None:
        source = Image.new("RGBA", (256, 256), (0, 0, 0, 255))
        for x in range(256):
            for y in range(256):
                source.putpixel((x, y), (x, y, (x + y) % 256, 255))

        result = convert_pil_image(
            source,
            width=128,
            height=128,
            resample="lanczos",
            remove_background=False,
        )
        visible_colors = {
            (red, green, blue)
            for red, green, blue, alpha in result.getdata()
            if alpha > 0
        }

        self.assertEqual(result.size, (128, 128))
        self.assertGreater(len(visible_colors), 256)

    def test_palette_limit_is_applied_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source_path = temp / "source.png"
            output_path = temp / "output.png"

            image = Image.new("RGBA", (120, 80), (0, 0, 0, 0))
            for x in range(20, 100):
                for y in range(10, 70):
                    image.putpixel(
                        (x, y),
                        ((x * 3) % 256, (y * 5) % 256, (x + y) % 256, 255),
                    )
            image.save(source_path)

            convert_image(source_path, output_path, width=80, height=80, colors=16)

            result = Image.open(output_path).convert("RGBA")
            pixels = list(result.getdata())
            alpha_values = {alpha for _, _, _, alpha in pixels}
            visible_colors = {
                (red, green, blue)
                for red, green, blue, alpha in pixels
                if alpha > 0
            }

            self.assertEqual(result.size, (80, 80))
            self.assertTrue(alpha_values.issubset({0, 255}))
            self.assertLessEqual(len(visible_colors), 16)
            self.assertIn(0, alpha_values)
            self.assertIn(255, alpha_values)

    def test_aspect_ratio_is_preserved_and_centered(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source_path = temp / "wide.png"
            output_path = temp / "wide-output.png"

            Image.new("RGBA", (200, 100), (255, 0, 0, 255)).save(source_path)
            convert_image(
                source_path,
                output_path,
                width=80,
                height=80,
                remove_background=False,
            )

            result = Image.open(output_path).convert("RGBA")
            bbox = result.getchannel("A").getbbox()
            self.assertEqual(bbox, (0, 20, 80, 60))

    def test_transparent_margins_are_preserved_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source_path = temp / "margin.png"
            output_path = temp / "margin-output.png"

            image = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
            for x in range(40, 60):
                for y in range(20, 80):
                    image.putpixel((x, y), (40, 80, 120, 255))
            image.save(source_path)

            convert_image(source_path, output_path, width=80, height=80)

            result = Image.open(output_path).convert("RGBA")
            bbox = result.getchannel("A").getbbox()
            self.assertEqual(bbox, (32, 16, 48, 64))

    def test_auto_background_removal_only_removes_edge_connected_background(self) -> None:
        image = Image.new("RGBA", (80, 80), (12, 12, 12, 255))
        for x in range(15, 65):
            for y in range(10, 70):
                image.putpixel((x, y), (170, 110, 40, 255))
        for x in range(35, 45):
            for y in range(35, 45):
                image.putpixel((x, y), (12, 12, 12, 255))

        result = auto_remove_background(image)
        self.assertEqual(result.getpixel((0, 0))[3], 0)
        self.assertEqual(result.getpixel((20, 20))[3], 255)
        self.assertEqual(result.getpixel((40, 40))[3], 255)

    def test_auto_background_removal_blocks_narrow_tunnels_into_foreground(self) -> None:
        image = Image.new("RGBA", (80, 80), (12, 12, 12, 255))
        for x in range(10, 70):
            for y in range(10, 70):
                image.putpixel((x, y), (175, 115, 45, 255))

        # An enclosed dark recess is connected to the outer background by a
        # deliberately narrow two-pixel seam. The protection barrier should
        # keep that seam from turning the whole recess transparent.
        for x in range(30, 50):
            for y in range(30, 50):
                image.putpixel((x, y), (12, 12, 12, 255))
        for x in range(39, 41):
            for y in range(0, 31):
                image.putpixel((x, y), (12, 12, 12, 255))

        result = auto_remove_background(image)
        self.assertEqual(result.getpixel((0, 0))[3], 0)
        self.assertEqual(result.getpixel((40, 40))[3], 255)
        self.assertEqual(result.getpixel((20, 20))[3], 255)

    def test_existing_transparent_border_is_left_intact(self) -> None:
        image = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
        for x in range(10, 30):
            for y in range(10, 30):
                image.putpixel((x, y), (20, 20, 20, 255))

        result = auto_remove_background(image)
        self.assertEqual(result.tobytes(), image.tobytes())

    def test_detail_preserve_resize_is_supported(self) -> None:
        source = Image.new("RGBA", (512, 512), (20, 20, 20, 255))
        for x in range(80, 432, 8):
            for y in range(80, 432, 8):
                source.putpixel((x, y), ((x * 3) % 256, (y * 5) % 256, 180, 255))

        result = convert_pil_image(
            source,
            width=128,
            height=128,
            resample="detail",
            remove_background=False,
        )
        self.assertEqual(result.size, (128, 128))

    def test_additional_resize_filters_are_supported(self) -> None:
        source = Image.new("RGBA", (64, 64), (120, 80, 40, 255))
        for method in ("hamming", "bicubic"):
            with self.subTest(method=method):
                result = convert_pil_image(
                    source,
                    width=32,
                    height=32,
                    resample=method,
                    remove_background=False,
                )
                self.assertEqual(result.size, (32, 32))

    def test_rejects_fully_transparent_image(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source_path = temp / "transparent.png"
            output_path = temp / "output.png"

            Image.new("RGBA", (20, 20), (0, 0, 0, 0)).save(source_path)

            with self.assertRaises(ValueError):
                convert_image(source_path, output_path)


if __name__ == "__main__":
    unittest.main()
