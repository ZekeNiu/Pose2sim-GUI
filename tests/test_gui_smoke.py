from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pose2sim_gui.app import Pose2SimMainWindow, create_app


class GuiSmokeTests(unittest.TestCase):
    def test_main_window_instantiates(self) -> None:
        app = create_app([])
        window = Pose2SimMainWindow()
        self.assertEqual(window.windowTitle(), "Pose2Sim 图形界面")
        self.assertEqual(window.tabs.count(), 5)
        window.close()
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
