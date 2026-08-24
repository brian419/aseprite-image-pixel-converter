from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

import apple_subject_lift
from apple_subject_lift import SubjectIsolationError, _request_payload, lift_subject


class AppleSubjectLiftTests(unittest.TestCase):
    def test_click_payload_normalizes_point(self) -> None:
        payload = _request_payload("click", point=[0.25, 0.75], lasso=None)
        self.assertEqual(payload, {"mode": "click", "point": [0.25, 0.75]})

    def test_lasso_payload_requires_real_area(self) -> None:
        with self.assertRaisesRegex(ValueError, "larger lasso"):
            _request_payload(
                "lasso",
                point=None,
                lasso=[[0.1, 0.1], [0.2, 0.2], [0.3, 0.3]],
            )

    def test_lasso_payload_accepts_rough_loop(self) -> None:
        payload = _request_payload(
            "lasso",
            point=None,
            lasso=[[0.1, 0.1], [0.8, 0.1], [0.8, 0.8], [0.1, 0.8]],
        )
        self.assertEqual(payload["mode"], "lasso")
        self.assertEqual(len(payload["points"]), 4)

    def test_non_macos_has_clear_error(self) -> None:
        source = Image.new("RGBA", (20, 20), (255, 0, 0, 255))
        with mock.patch.object(sys, "platform", "linux"):
            with self.assertRaisesRegex(SubjectIsolationError, "requires macOS 14"):
                lift_subject(source, mode="click", point=[0.5, 0.5])

    def test_native_helper_result_is_loaded_as_rgba(self) -> None:
        source = Image.new("RGBA", (20, 20), (255, 0, 0, 255))
        with tempfile.TemporaryDirectory() as temp_dir:
            helper = Path(temp_dir) / "helper"
            helper.write_text("test", encoding="utf-8")
            helper.chmod(0o755)

            def fake_run(args, **_kwargs):
                output_path = Path(args[3])
                result = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
                for x in range(5, 15):
                    for y in range(4, 16):
                        result.putpixel((x, y), (10, 180, 30, 255))
                result.save(output_path, format="PNG")
                return subprocess.CompletedProcess(args, 0, stdout='{"instance":1}\n', stderr="")

            with (
                mock.patch.object(sys, "platform", "darwin"),
                mock.patch.object(apple_subject_lift, "_helper_path", return_value=helper),
                mock.patch.object(subprocess, "run", side_effect=fake_run),
            ):
                result = lift_subject(source, mode="click", point=[0.5, 0.5])

            self.assertEqual(result.mode, "RGBA")
            self.assertEqual(result.size, (20, 20))
            self.assertEqual(result.getpixel((0, 0))[3], 0)
            self.assertEqual(result.getpixel((10, 10))[3], 255)


if __name__ == "__main__":
    unittest.main()
