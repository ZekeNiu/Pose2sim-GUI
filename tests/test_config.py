from __future__ import annotations

import unittest

from pose2sim_gui.config import (
    apply_beginner_safety,
    parse_toml_value,
    selected_stages_to_runall_kwargs,
    validate_toml_text,
)


class ConfigTests(unittest.TestCase):
    def test_validate_toml_text(self) -> None:
        ok, message = validate_toml_text("[project]\nframe_rate = 'auto'\n")
        self.assertTrue(ok, message)

        ok, _ = validate_toml_text("[project\nbroken = true")
        self.assertFalse(ok)

    def test_parse_toml_value(self) -> None:
        self.assertEqual(parse_toml_value("auto"), "auto")
        self.assertEqual(parse_toml_value("'auto'"), "auto")
        self.assertEqual(parse_toml_value("[10, 300]"), [10, 300])
        self.assertEqual(parse_toml_value("70.5"), 70.5)

    def test_beginner_safety_disables_hidden_risky_settings(self) -> None:
        config = {
            "pose": {
                "output_format": "mmpose",
                "handle_LR_swap": True,
                "undistort_points": True,
                "display_detection": True,
                "parallel_workers_pose": "auto",
                "mode": "{'pose_class':'RTMO'}",
            },
            "calibration": {
                "calculate": {
                    "extrinsics": {
                        "moving_cameras": True,
                        "extrinsics_method": "keypoints",
                    }
                }
            },
        }
        warnings = apply_beginner_safety(config)
        self.assertGreaterEqual(len(warnings), 5)
        self.assertEqual(config["pose"]["output_format"], "openpose")
        self.assertFalse(config["pose"]["handle_LR_swap"])
        self.assertFalse(config["pose"]["undistort_points"])
        self.assertFalse(config["pose"]["parallel_workers_pose"])
        self.assertEqual(config["pose"]["mode"], "balanced")
        self.assertFalse(config["calibration"]["calculate"]["extrinsics"]["moving_cameras"])
        self.assertEqual(config["calibration"]["calculate"]["extrinsics"]["extrinsics_method"], "scene")

    def test_selected_stages_to_runall_kwargs(self) -> None:
        kwargs = selected_stages_to_runall_kwargs(["calibration", "kinematics"])
        self.assertTrue(kwargs["do_calibration"])
        self.assertTrue(kwargs["do_kinematics"])
        self.assertFalse(kwargs["do_poseEstimation"])
        with self.assertRaises(ValueError):
            selected_stages_to_runall_kwargs(["not-a-stage"])


if __name__ == "__main__":
    unittest.main()
