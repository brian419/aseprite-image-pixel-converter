from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

import web_app


class WebAppTests(unittest.TestCase):
    def setUp(self) -> None:
        web_app.app.config.update(TESTING=True)
        self.client = web_app.app.test_client()
        web_app._selected_output_directory = None

    def tearDown(self) -> None:
        web_app._selected_output_directory = None

    def _image_bytes(self) -> io.BytesIO:
        source = Image.new("RGBA", (120, 80), (0, 0, 0, 0))
        for x in range(20, 100):
            for y in range(10, 70):
                source.putpixel((x, y), (140, 90, 45, 255))

        source_bytes = io.BytesIO()
        source.save(source_bytes, format="PNG")
        source_bytes.seek(0)
        return source_bytes

    def _conversion_data(self) -> dict[str, object]:
        return {
            "image": (self._image_bytes(), "artifact.png"),
            "width": "80",
            "height": "80",
            "colors": "16",
            "resample": "box",
            "dither": "none",
            "crop_transparent": "true",
            "hard_alpha": "true",
            "alpha_threshold": "8",
            "output_name": "artifact-80x80-16c.png",
        }

    def test_health_endpoint(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True})

    def test_preview_returns_converted_png_without_output_folder(self) -> None:
        response = self.client.post(
            "/api/preview",
            data=self._conversion_data(),
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertTrue(response.data.startswith(b"\x89PNG\r\n\x1a\n"))

        with Image.open(io.BytesIO(response.data)) as result:
            self.assertEqual(result.size, (80, 80))

    def test_convert_requires_output_folder(self) -> None:
        response = self.client.post(
            "/api/convert",
            data={"image": (self._image_bytes(), "artifact.png")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Choose an output folder before converting.")

    def test_convert_saves_png_to_selected_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            web_app._selected_output_directory = Path(temp_dir)

            response = self.client.post(
                "/api/convert",
                data=self._conversion_data(),
                content_type="multipart/form-data",
            )

            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data["saved"])
            self.assertEqual(data["filename"], "artifact-80x80-16c.png")

            output_path = Path(data["path"])
            self.assertTrue(output_path.exists())
            with Image.open(output_path) as result:
                self.assertEqual(result.size, (80, 80))

            self.assertIsNone(web_app._selected_output_directory)


if __name__ == "__main__":
    unittest.main()
