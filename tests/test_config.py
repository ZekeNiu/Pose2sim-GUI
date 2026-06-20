from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pose2sim_gui.config import (
    apply_beginner_safety,
    ensure_project_config,
    parse_toml_value,
    selected_stages_to_runall_kwargs,
    validate_toml_text,
    validate_stage_prerequisites,
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

    def test_ensure_project_config_creates_default_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            template = tmp_path / "template.toml"
            template.write_text("[project]\nframe_rate = 'auto'\n", encoding="utf-8")
            project = tmp_path / "trial_project"

            with patch("pose2sim_gui.config.demo_config_path", return_value=template):
                config_path, created = ensure_project_config(project)
                self.assertTrue(created)
                self.assertEqual(config_path, project / "Config.toml")
                self.assertTrue((project / "videos").is_dir())
                self.assertTrue((project / "calibration").is_dir())
                self.assertTrue((project / "reports").is_dir())

                config_path.write_text("[project]\nframe_rate = 120\n", encoding="utf-8")
                _, created_again = ensure_project_config(project)
                self.assertFalse(created_again)
                self.assertIn("120", config_path.read_text(encoding="utf-8"))

    def test_stage_prerequisites_require_calibration_file_for_3d_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "calibration").mkdir()

            errors = validate_stage_prerequisites(project, ["poseEstimation", "personAssociation", "triangulation"])
            self.assertEqual(len(errors), 1)
            self.assertIn("没有 .toml 标定文件", errors[0])

            self.assertEqual(validate_stage_prerequisites(project, ["poseEstimation", "synchronization"]), [])
            self.assertEqual(validate_stage_prerequisites(project, ["calibration", "personAssociation"]), [])

            (project / "calibration" / "Calib.toml").write_text("[calibration]\n", encoding="utf-8")
            self.assertEqual(validate_stage_prerequisites(project, ["personAssociation", "triangulation"]), [])


if __name__ == "__main__":
    unittest.main()
