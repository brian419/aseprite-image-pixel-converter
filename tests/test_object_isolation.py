from __future__ import annotations

import unittest

from PIL import Image, ImageDraw

from object_isolation import isolate_object


class ObjectIsolationTests(unittest.TestCase):
    def _source(self) -> Image.Image:
        source = Image.new("RGBA", (160, 120), (40, 120, 210, 255))
        draw = ImageDraw.Draw(source)
        draw.rectangle((45, 25, 115, 95), fill=(220, 70, 40, 255))
        draw.ellipse((5, 5, 30, 30), fill=(220, 70, 40, 255))
        return source

    def test_selection_keeps_object_and_removes_outside_background(self) -> None:
        result = isolate_object(
            self._source(),
            selection_rect=(0.25, 0.15, 0.5, 0.7),
        )

        self.assertEqual(result.getpixel((80, 60))[3], 255)
        self.assertEqual(result.getpixel((10, 10))[3], 0)
        self.assertEqual(result.getpixel((150, 110))[3], 0)

    def test_remove_mark_forces_local_background(self) -> None:
        result = isolate_object(
            self._source(),
            selection_rect=(0.25, 0.15, 0.5, 0.7),
            remove_points=[(0.5, 0.5)],
            refine_radius=0.03,
        )

        self.assertEqual(result.getpixel((80, 60))[3], 0)
        self.assertEqual(result.getpixel((60, 60))[3], 255)

    def test_existing_transparency_remains_transparent(self) -> None:
        source = self._source()
        source.putpixel((80, 60), (220, 70, 40, 0))

        result = isolate_object(
            source,
            selection_rect=(0.25, 0.15, 0.5, 0.7),
            keep_points=[(0.5, 0.5)],
        )

        self.assertEqual(result.getpixel((80, 60))[3], 0)

    def test_rejects_invalid_selection_rectangle(self) -> None:
        with self.assertRaisesRegex(ValueError, "selection box"):
            isolate_object(
                self._source(),
                selection_rect=(0.9, 0.9, 0.3, 0.3),
            )


if __name__ == "__main__":
    unittest.main()
