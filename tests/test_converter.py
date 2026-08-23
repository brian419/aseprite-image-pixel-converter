from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from aseprite_image_pixel_converter import convert_image


class ConverterTests(unittest.TestCase):
    def test_conversion_limits_size_palette_and_alpha(self) -> None:
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
            self.assertEqual(result.size, (80, 80))

            pixels = list(result.getdata())
            alpha_values = {alpha for _, _, _, alpha in pixels}
            visible_colors = {
                (red, green, blue)
                for red, green, blue, alpha in pixels
                if alpha > 0
            }

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
            convert_image(source_path, output_path, width=80, height=80, colors=4)

            result = Image.open(output_path).convert("RGBA")
            bbox = result.getchannel("A").getbbox()
            self.assertEqual(bbox, (0, 20, 80, 60))

    def test_transparent_margins_are_cropped_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source_path = temp / "margin.png"
            output_path = temp / "margin-output.png"

            image = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
            for x in range(40, 60):
                for y in range(20, 80):
                    image.putpixel((x, y), (40, 80, 120, 255))
            image.save(source_path)

            convert_image(source_path, output_path, width=80, height=80, colors=4)

            result = Image.open(output_path).convert("RGBA")
            bbox = result.getchannel("A").getbbox()
            self.assertEqual(bbox, (26, 0, 53, 80))

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
