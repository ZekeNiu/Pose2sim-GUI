from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from openpyxl import load_workbook

from pose2sim_gui.reports import export_excel, export_html, read_mot, split_motion_columns


MOT_TEXT = """Coordinates
version=1
nRows=3
nColumns=5
inDegrees=yes
endheader
time pelvis_tx hip_flexion_r knee_angle_r ankle_angle_r
0.00 0.10 12.0 30.0 5.0
0.01 0.11 13.0 31.0 6.0
0.02 0.12 14.0 32.0 7.0
"""


class ReportTests(unittest.TestCase):
    def test_read_mot_and_split_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mot = Path(tmp) / "trial.mot"
            mot.write_text(MOT_TEXT, encoding="utf-8")
            data, header = read_mot(mot)
            self.assertEqual(len(header), 6)
            self.assertEqual(list(data.columns), ["time", "pelvis_tx", "hip_flexion_r", "knee_angle_r", "ankle_angle_r"])
            angles, translations = split_motion_columns(data)
            self.assertEqual(translations, ["pelvis_tx"])
            self.assertIn("hip_flexion_r", angles)

    def test_export_excel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mot = Path(tmp) / "trial.mot"
            mot.write_text(MOT_TEXT, encoding="utf-8")
            output = export_excel(mot)
            self.assertTrue(output.exists())
            workbook = load_workbook(output, read_only=True)
            try:
                self.assertEqual(set(workbook.sheetnames), {"joint_angles", "translations", "summary"})
                self.assertEqual(workbook["joint_angles"]["A1"].value, "time")
                self.assertEqual(workbook["joint_angles"]["B1"].value, "hip_flexion_r")
                self.assertEqual(workbook["translations"]["B1"].value, "pelvis_tx")
            finally:
                workbook.close()

    def test_export_html_contains_plot_video_and_sync_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            mot = tmp_path / "trial.mot"
            video = tmp_path / "cam01.mp4"
            mot.write_text(MOT_TEXT, encoding="utf-8")
            video.write_bytes(b"")
            output, warnings = export_html(mot, video)
            self.assertEqual(warnings, [])
            html = output.read_text(encoding="utf-8")
            self.assertIn("Plotly.newPlot", html)
            self.assertIn("<video", html)
            self.assertIn("plotly_hover", html)
            self.assertIn("hip_flexion_r", html)


if __name__ == "__main__":
    unittest.main()
