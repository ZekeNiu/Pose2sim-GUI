from __future__ import annotations

import unittest

from pose2sim_gui.__main__ import version_report


class VersionTests(unittest.TestCase):
    def test_version_report_mentions_executable(self) -> None:
        report = version_report()
        self.assertIn("pose2sim-gui", report)
        self.assertIn("executable", report)


if __name__ == "__main__":
    unittest.main()
