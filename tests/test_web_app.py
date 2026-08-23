from __future__ import annotations

import io
import unittest

from PIL import Image

from web_app import app


class WebAppTests(unittest.TestCase):
    def setUp(self) -> None:
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_health_endpoint(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True})

    def test_convert_endpoint_returns_png(self) -> None:
        source = Image.new("RGBA", (120, 80), (0, 0, 0, 0))
        for x in range(20, 100):
            for y in range(10, 70):
                source.putpixel((x, y), (140, 90, 45, 255))

        source_bytes = io.BytesIO()
        source.save(source_bytes, format="PNG")
        source_bytes.seek(0)

        response = self.client.post(
            "/api/convert",
            data={
                "image": (source_bytes, "artifact.png"),
                "width": "80",
                "height": "80",
                "colors": "16",
                "resample": "box",
                "dither": "none",
                "crop_transparent": "true",
                "hard_alpha": "true",
                "alpha_threshold": "8",
                "output_name": "artifact-80x80-16c.png",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")
        self.assertEqual(response.headers["X-Output-Filename"], "artifact-80x80-16c.png")
        self.assertTrue(response.data.startswith(b"\x89PNG\r\n\x1a\n"))

        result = Image.open(io.BytesIO(response.data)).convert("RGBA")
        self.assertEqual(result.size, (80, 80))


if __name__ == "__main__":
    unittest.main()
