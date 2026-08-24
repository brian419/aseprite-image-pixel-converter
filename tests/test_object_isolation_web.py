from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

import web_app


class ObjectIsolationWebTests(unittest.TestCase):
    def setUp(self) -> None:
        web_app.app.config.update(TESTING=True)
        self.client = web_app.app.test_client()
        web_app._selected_output_directory = None

    def tearDown(self) -> None:
        web_app._selected_output_directory = None

    def _image_bytes(self) -> io.BytesIO:
        source = Image.new("RGBA", (160, 120), (40, 120, 210, 255))
        draw = ImageDraw.Draw(source)
        draw.rectangle((45, 25, 115, 95), fill=(220, 70, 40, 255))

        buffer = io.BytesIO()
        source.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    def _data(self, *, output_name: str = "") -> dict[str, object]:
        return {
            "image": (self._image_bytes(), "artifact.png"),
            "width": "128",
            "height": "128",
            "color_mode": "preserve",
            "colors": "32",
            "resample": "nearest",
            "dither": "none",
            "alpha_threshold": "8",
            "isolation_mode": "object",
            "selection_rect": json.dumps([0.25, 0.15, 0.5, 0.7]),
            "keep_points": "[]",
            "remove_points": "[]",
            "refine_radius": "0.018",
            "output_name": output_name,
        }

    def test_object_preview_keeps_only_selected_object(self) -> None:
        response = self.client.post(
            "/api/preview",
            data=self._data(),
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        with Image.open(io.BytesIO(response.data)).convert("RGBA") as result:
            self.assertEqual(result.size, (128, 128))
            self.assertEqual(result.getpixel((64, 64))[3], 255)
            self.assertEqual(result.getpixel((4, 4))[3], 0)

    def test_object_mode_requires_selection_box(self) -> None:
        data = self._data()
        del data["selection_rect"]

        response = self.client.post(
            "/api/preview",
            data=data,
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Draw a selection box", response.get_json()["error"])

    def test_source_preview_stays_unmodified_in_object_mode(self) -> None:
        response = self.client.post(
            "/api/source-preview",
            data={
                "image": (self._image_bytes(), "artifact.png"),
                "isolation_mode": "object",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        with Image.open(io.BytesIO(response.data)).convert("RGBA") as result:
            self.assertEqual(result.getpixel((0, 0))[3], 255)

    def test_isolated_fallback_filename_is_descriptive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            web_app._selected_output_directory = Path(temp_dir)
            response = self.client.post(
                "/api/convert",
                data=self._data(output_name=""),
                content_type="multipart/form-data",
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.get_json()["filename"],
                "artifact-128x128-nearest-isolated-preserve.png",
            )


if __name__ == "__main__":
    unittest.main()
