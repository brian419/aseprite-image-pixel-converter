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
                source.putpixel(
                    (x, y),
                    ((x * 3) % 256, (y * 5) % 256, (x + y) % 256, 255),
                )

        source_bytes = io.BytesIO()
        source.save(source_bytes, format="PNG")
        source_bytes.seek(0)
        return source_bytes

    def _conversion_data(self, *, color_mode: str = "preserve") -> dict[str, object]:
        return {
            "image": (self._image_bytes(), "artifact.png"),
            "width": "128",
            "height": "128",
            "color_mode": color_mode,
            "colors": "32",
            "resample": "lanczos",
            "dither": "none",
            "crop_transparent": "true",
            "hard_alpha": "true",
            "alpha_threshold": "8",
            "output_name": "artifact-128x128.png" if color_mode == "preserve" else "artifact-128x128-32c.png",
        }

    def test_health_endpoint(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True})

    def test_source_preview_returns_cropped_high_resolution_png(self) -> None:
        response = self.client.post(
            "/api/source-preview",
            data={
                "image": (self._image_bytes(), "artifact.png"),
                "crop_transparent": "true",
                "alpha_threshold": "8",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")
        self.assertEqual(response.headers["Cache-Control"], "no-store")

        with Image.open(io.BytesIO(response.data)) as result:
            self.assertEqual(result.size, (80, 60))

    def test_preview_preserves_resized_colors_by_default(self) -> None:
        response = self.client.post(
            "/api/preview",
            data=self._conversion_data(),
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")
        self.assertEqual(response.headers["Cache-Control"], "no-store")

        with Image.open(io.BytesIO(response.data)).convert("RGBA") as result:
            self.assertEqual(result.size, (128, 128))
            visible_colors = {
                pixel[:3]
                for pixel in result.getdata()
                if pixel[3] > 0
            }
            self.assertGreater(len(visible_colors), 256)

    def test_preview_can_limit_palette(self) -> None:
        response = self.client.post(
            "/api/preview",
            data=self._conversion_data(color_mode="limit"),
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        with Image.open(io.BytesIO(response.data)).convert("RGBA") as result:
            visible_colors = {
                pixel[:3]
                for pixel in result.getdata()
                if pixel[3] > 0
            }
            self.assertLessEqual(len(visible_colors), 32)

    def test_convert_requires_output_folder(self) -> None:
        response = self.client.post(
            "/api/convert",
            data={"image": (self._image_bytes(), "artifact.png")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Choose an output folder before converting.")

    def test_convert_saves_preserve_color_png_to_selected_folder(self) -> None:
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
            self.assertEqual(data["filename"], "artifact-128x128.png")

            output_path = Path(data["path"])
            self.assertTrue(output_path.exists())
            with Image.open(output_path) as result:
                self.assertEqual(result.size, (128, 128))

            self.assertIsNone(web_app._selected_output_directory)


if __name__ == "__main__":
    unittest.main()
