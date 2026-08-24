from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

import web_app


class SmartObjectIsolationWebTests(unittest.TestCase):
    def setUp(self) -> None:
        web_app.app.config.update(TESTING=True)
        self.client = web_app.app.test_client()
        web_app._selected_output_directory = None

    def tearDown(self) -> None:
        web_app._selected_output_directory = None

    def _source_bytes(self) -> io.BytesIO:
        source = Image.new("RGBA", (120, 80), (220, 230, 240, 255))
        for x in range(45, 85):
            for y in range(8, 72):
                source.putpixel((x, y), (40, 150, 55, 255))
        data = io.BytesIO()
        source.save(data, format="PNG")
        data.seek(0)
        return data

    def _isolated_bytes(self) -> io.BytesIO:
        source = Image.new("RGBA", (120, 80), (0, 0, 0, 0))
        for x in range(45, 85):
            for y in range(8, 72):
                source.putpixel((x, y), (40, 150, 55, 255))
        data = io.BytesIO()
        source.save(data, format="PNG")
        data.seek(0)
        return data

    def _lifted_image(self) -> Image.Image:
        with Image.open(self._isolated_bytes()) as opened:
            return opened.convert("RGBA").copy()

    def test_smart_click_endpoint_passes_selected_point_to_vision_wrapper(self) -> None:
        with mock.patch.object(web_app, "lift_subject", return_value=self._lifted_image()) as lift:
            response = self.client.post(
                "/api/isolate",
                data={
                    "image": (self._source_bytes(), "tree.png"),
                    "isolation_mode": "smart_click",
                    "selection_point": "[0.62, 0.42]",
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")
        lift.assert_called_once()
        _, kwargs = lift.call_args
        self.assertEqual(kwargs["mode"], "click")
        self.assertEqual(kwargs["point"], [0.62, 0.42])

    def test_smart_lasso_endpoint_passes_freeform_points(self) -> None:
        points = "[[0.3,0.1],[0.8,0.1],[0.82,0.9],[0.28,0.85]]"
        with mock.patch.object(web_app, "lift_subject", return_value=self._lifted_image()) as lift:
            response = self.client.post(
                "/api/isolate",
                data={
                    "image": (self._source_bytes(), "tree.png"),
                    "isolation_mode": "smart_lasso",
                    "lasso_points": points,
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        _, kwargs = lift.call_args
        self.assertEqual(kwargs["mode"], "lasso")
        self.assertEqual(len(kwargs["lasso"]), 4)

    def test_smart_mode_requires_selected_subject_for_pixel_preview(self) -> None:
        response = self.client.post(
            "/api/preview",
            data={
                "image": (self._source_bytes(), "tree.png"),
                "isolation_mode": "smart_click",
                "width": "128",
                "height": "128",
                "color_mode": "preserve",
                "colors": "32",
                "resample": "nearest",
                "dither": "none",
                "alpha_threshold": "8",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Select a subject", response.get_json()["error"])

    def test_isolated_subject_is_fitted_to_output_canvas(self) -> None:
        response = self.client.post(
            "/api/preview",
            data={
                "image": (self._source_bytes(), "tree.png"),
                "isolated_image": (self._isolated_bytes(), "isolated-subject.png"),
                "isolation_mode": "smart_click",
                "width": "128",
                "height": "128",
                "color_mode": "preserve",
                "colors": "32",
                "resample": "nearest",
                "dither": "none",
                "alpha_threshold": "8",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        with Image.open(io.BytesIO(response.data)).convert("RGBA") as result:
            bbox = result.getchannel("A").getbbox()
            self.assertIsNotNone(bbox)
            self.assertGreater(bbox[2] - bbox[0], 60)
            self.assertGreater(bbox[3] - bbox[1], 100)

    def test_saved_smart_subject_filename_mentions_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            web_app._selected_output_directory = Path(temp_dir)
            response = self.client.post(
                "/api/convert",
                data={
                    "image": (self._source_bytes(), "tree.png"),
                    "isolated_image": (self._isolated_bytes(), "isolated-subject.png"),
                    "isolation_mode": "smart_click",
                    "width": "128",
                    "height": "128",
                    "color_mode": "preserve",
                    "colors": "32",
                    "resample": "nearest",
                    "dither": "none",
                    "alpha_threshold": "8",
                    "output_name": "",
                },
                content_type="multipart/form-data",
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["filename"], "tree-128x128-nearest-isolated-preserve.png")


if __name__ == "__main__":
    unittest.main()
