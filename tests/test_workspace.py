from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import pose2sim_gui.workspace as workspace


class WorkspaceTests(unittest.TestCase):
    def test_mirror_pose2sim_outputs_copies_result_dirs_without_videos(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            (project / "Config.toml").write_text("[project]\n", encoding="utf-8")
            (project / "videos").mkdir()
            (project / "videos" / "raw.mp4").write_bytes(b"raw")
            (project / "kinematics").mkdir()
            (project / "kinematics" / "trial.mot").write_text("mot", encoding="utf-8")
            (project / "kinematics" / "trial.osim").write_text("osim", encoding="utf-8")
            (project / "pose-3d").mkdir()
            (project / "pose-3d" / "trial.trc").write_text("trc", encoding="utf-8")

            original_results_dir = workspace.RESULTS_DIR
            workspace.RESULTS_DIR = root / "output" / "pose2sim_results"
            try:
                copied = workspace.mirror_pose2sim_outputs(project)
                result_dir = workspace.project_results_dir(project)
            finally:
                workspace.RESULTS_DIR = original_results_dir

            self.assertTrue(copied)
            self.assertTrue((result_dir / "kinematics" / "trial.mot").exists())
            self.assertTrue((result_dir / "kinematics" / "trial.osim").exists())
            self.assertTrue((result_dir / "pose-3d" / "trial.trc").exists())
            self.assertTrue((result_dir / "Config.toml").exists())
            self.assertFalse((result_dir / "videos" / "raw.mp4").exists())


if __name__ == "__main__":
    unittest.main()
