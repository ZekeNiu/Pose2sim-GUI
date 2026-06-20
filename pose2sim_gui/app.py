from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

from PySide6.QtCore import QProcess, Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .config import (
    BACKENDS,
    DEVICES,
    FILTER_TYPES,
    POSE_MODELS,
    POSE_MODES,
    STAGES,
    TRACKING_MODES,
    apply_beginner_safety,
    copy_demo_config,
    demo_config_path,
    display_toml_value,
    get_nested,
    load_config,
    load_config_text,
    parse_toml_value,
    project_status,
    save_config,
    save_config_text,
    set_nested,
    validate_toml_text,
)
from .reports import export_excel, export_html, find_mot_files, find_video_files


class Pose2SimMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Pose2Sim GUI")
        self.resize(1180, 760)
        self.project_dir: Path | None = None
        self.config: dict[str, Any] | None = None
        self.process: QProcess | None = None

        self._build_actions()
        self._build_ui()
        self._apply_style()

    def _icon(self, standard_pixmap: QStyle.StandardPixmap):
        return self.style().standardIcon(standard_pixmap)

    def _build_actions(self) -> None:
        quit_action = QAction("Exit", self)
        quit_action.triggered.connect(self.close)

        open_action = QAction("Open Project", self)
        open_action.triggered.connect(self.choose_project)

        menu = self.menuBar().addMenu("File")
        menu.addAction(open_action)
        menu.addSeparator()
        menu.addAction(quit_action)

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        title = QLabel("Pose2Sim GUI")
        title.setObjectName("AppTitle")
        self.project_label = QLabel("No project loaded")
        self.project_label.setObjectName("ProjectLabel")
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(self.project_label)
        layout.addLayout(title_row)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_project_tab(), "Project")
        self.tabs.addTab(self._build_parameters_tab(), "Parameters")
        self.tabs.addTab(self._build_pipeline_tab(), "Pipeline")
        self.tabs.addTab(self._build_reports_tab(), "Reports")
        layout.addWidget(self.tabs, 1)

        self.setCentralWidget(root)
        self._set_project_dependent_enabled(False)

    def _build_project_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        group = QGroupBox("Project folder")
        grid = QGridLayout(group)
        self.project_edit = QLineEdit()
        self.project_edit.setPlaceholderText("Choose a folder containing Config.toml")

        browse_btn = QPushButton(self._icon(QStyle.SP_DirOpenIcon), "Browse")
        browse_btn.setToolTip("Choose an existing Pose2Sim project folder")
        browse_btn.clicked.connect(self.choose_project)

        create_btn = QPushButton(self._icon(QStyle.SP_FileDialogNewFolder), "Create From Demo Config")
        create_btn.setToolTip("Create Config.toml in an empty project folder")
        create_btn.clicked.connect(self.create_project_from_demo)

        demo_btn = QPushButton(self._icon(QStyle.SP_ComputerIcon), "Open Installed Demo")
        demo_btn.setToolTip("Open Pose2Sim's installed single-person demo")
        demo_btn.clicked.connect(self.open_installed_demo)

        validate_btn = QPushButton(self._icon(QStyle.SP_DialogApplyButton), "Validate")
        validate_btn.clicked.connect(self.validate_project)

        grid.addWidget(self.project_edit, 0, 0, 1, 4)
        grid.addWidget(browse_btn, 1, 0)
        grid.addWidget(create_btn, 1, 1)
        grid.addWidget(demo_btn, 1, 2)
        grid.addWidget(validate_btn, 1, 3)
        grid.setColumnStretch(0, 1)
        layout.addWidget(group)

        self.status_text = QPlainTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setPlaceholderText("Project validation details will appear here.")
        layout.addWidget(self.status_text, 1)

        note = QLabel(
            "Expected project shape: Config.toml, videos folder, and calibration folder. "
            "Pipeline outputs are written by Pose2Sim into pose-2d, pose-3d, and kinematics folders."
        )
        note.setWordWrap(True)
        note.setObjectName("HelpText")
        layout.addWidget(note)
        return page

    def _build_parameters_tab(self) -> QWidget:
        outer = QTabWidget()
        outer.addTab(self._build_beginner_parameters(), "Beginner")
        outer.addTab(self._build_advanced_parameters(), "Advanced TOML")
        return outer

    def _combo(self, values: tuple[str, ...] | list[str]) -> QComboBox:
        combo = QComboBox()
        combo.addItems(list(values))
        return combo

    def _build_beginner_parameters(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form_layout = QVBoxLayout(content)
        form_layout.setSpacing(12)

        project_group = QGroupBox("Project")
        project_form = QFormLayout(project_group)
        self.multi_person = QCheckBox("Analyze multiple people")
        self.participant_height = QLineEdit()
        self.participant_mass = QLineEdit()
        self.frame_rate = QLineEdit()
        self.frame_range = QLineEdit()
        project_form.addRow("Multi-person", self.multi_person)
        project_form.addRow("Participant height", self.participant_height)
        project_form.addRow("Participant mass", self.participant_mass)
        project_form.addRow("Frame rate", self.frame_rate)
        project_form.addRow("Frame range", self.frame_range)
        form_layout.addWidget(project_group)

        pose_group = QGroupBox("Pose estimation")
        pose_form = QFormLayout(pose_group)
        self.pose_model = self._combo(POSE_MODELS)
        self.pose_mode = self._combo(POSE_MODES)
        self.device = self._combo(DEVICES)
        self.backend = self._combo(BACKENDS)
        self.display_detection = QCheckBox("Show detection window")
        self.overwrite_pose = QCheckBox("Overwrite existing pose files")
        self.save_video = self._combo(["to_video", "to_images", "none"])
        self.tracking_mode = self._combo(TRACKING_MODES)
        self.det_frequency = QSpinBox()
        self.det_frequency.setRange(1, 9999)
        self.average_likelihood = QDoubleSpinBox()
        self.average_likelihood.setRange(0.0, 1.0)
        self.average_likelihood.setSingleStep(0.05)
        pose_form.addRow("Pose model", self.pose_model)
        pose_form.addRow("Mode", self.pose_mode)
        pose_form.addRow("Device", self.device)
        pose_form.addRow("Backend", self.backend)
        pose_form.addRow("Detection frequency", self.det_frequency)
        pose_form.addRow("Average likelihood threshold", self.average_likelihood)
        pose_form.addRow("Display detection", self.display_detection)
        pose_form.addRow("Overwrite pose", self.overwrite_pose)
        pose_form.addRow("Save overlay", self.save_video)
        pose_form.addRow("Tracking mode", self.tracking_mode)
        form_layout.addWidget(pose_group)

        sync_calib_group = QGroupBox("Synchronization and calibration")
        sync_form = QFormLayout(sync_calib_group)
        self.synchronization_gui = QCheckBox("Manual sync player")
        self.display_sync_plots = QCheckBox("Display sync plots")
        self.save_sync_plots = QCheckBox("Save sync plots")
        self.calibration_type = self._combo(["convert", "calculate"])
        self.convert_from = self._combo(
            ["qualisys", "caliscope", "optitrack", "vicon", "opencap", "easymocap", "biocv", "anipose", "freemocap"]
        )
        self.intrinsics_extension = QLineEdit()
        self.extrinsics_method = self._combo(["scene", "board"])
        sync_form.addRow("Synchronization GUI", self.synchronization_gui)
        sync_form.addRow("Display sync plots", self.display_sync_plots)
        sync_form.addRow("Save sync plots", self.save_sync_plots)
        sync_form.addRow("Calibration type", self.calibration_type)
        sync_form.addRow("Convert from", self.convert_from)
        sync_form.addRow("Intrinsics extension", self.intrinsics_extension)
        sync_form.addRow("Extrinsics method", self.extrinsics_method)
        form_layout.addWidget(sync_calib_group)

        association_group = QGroupBox("Association and triangulation")
        assoc_form = QFormLayout(association_group)
        self.tracked_keypoint = QLineEdit()
        self.reproj_assoc = QDoubleSpinBox()
        self.reproj_assoc.setRange(0.0, 10000.0)
        self.reproj_assoc.setSuffix(" px")
        self.reproj_triangulation = QDoubleSpinBox()
        self.reproj_triangulation.setRange(0.0, 10000.0)
        self.reproj_triangulation.setSuffix(" px")
        self.min_cameras = QSpinBox()
        self.min_cameras.setRange(2, 64)
        self.interpolation = self._combo(["linear", "slinear", "quadratic", "cubic", "none"])
        assoc_form.addRow("Tracked keypoint", self.tracked_keypoint)
        assoc_form.addRow("Association reprojection error", self.reproj_assoc)
        assoc_form.addRow("Triangulation reprojection error", self.reproj_triangulation)
        assoc_form.addRow("Minimum cameras", self.min_cameras)
        assoc_form.addRow("Interpolation", self.interpolation)
        form_layout.addWidget(association_group)

        filtering_group = QGroupBox("Filtering")
        filtering_form = QFormLayout(filtering_group)
        self.reject_outliers = QCheckBox("Reject outliers")
        self.filter_enabled = QCheckBox("Filter coordinates")
        self.filter_type = self._combo(FILTER_TYPES)
        self.filter_cutoff = QDoubleSpinBox()
        self.filter_cutoff.setRange(0.0, 1000.0)
        self.filter_cutoff.setSuffix(" Hz")
        self.filter_order = QSpinBox()
        self.filter_order.setRange(1, 32)
        self.display_figures = QCheckBox("Display figures")
        self.save_filt_plots = QCheckBox("Save plots")
        filtering_form.addRow("Reject outliers", self.reject_outliers)
        filtering_form.addRow("Filtering", self.filter_enabled)
        filtering_form.addRow("Filter type", self.filter_type)
        filtering_form.addRow("Butterworth cutoff", self.filter_cutoff)
        filtering_form.addRow("Butterworth order", self.filter_order)
        filtering_form.addRow("Display figures", self.display_figures)
        filtering_form.addRow("Save filter plots", self.save_filt_plots)
        form_layout.addWidget(filtering_group)

        kin_group = QGroupBox("Marker augmentation and OpenSim kinematics")
        kin_form = QFormLayout(kin_group)
        self.feet_on_floor = QCheckBox("Place feet on floor")
        self.use_augmentation = QCheckBox("Use augmented markers")
        self.use_simple_model = QCheckBox("Use simple OpenSim model")
        self.right_left_symmetry = QCheckBox("Assume right-left symmetry")
        self.default_height = QDoubleSpinBox()
        self.default_height.setRange(0.5, 2.5)
        self.default_height.setSingleStep(0.01)
        self.default_height.setSuffix(" m")
        kin_form.addRow("Feet on floor", self.feet_on_floor)
        kin_form.addRow("Use augmentation", self.use_augmentation)
        kin_form.addRow("Simple model", self.use_simple_model)
        kin_form.addRow("Right-left symmetry", self.right_left_symmetry)
        kin_form.addRow("Default height", self.default_height)
        form_layout.addWidget(kin_group)

        scroll.setWidget(content)
        page_layout.addWidget(scroll, 1)

        button_row = QHBoxLayout()
        self.save_beginner_btn = QPushButton(self._icon(QStyle.SP_DialogSaveButton), "Save Beginner Settings")
        self.save_beginner_btn.clicked.connect(self.save_beginner_settings)
        self.reload_beginner_btn = QPushButton(self._icon(QStyle.SP_BrowserReload), "Reload")
        self.reload_beginner_btn.clicked.connect(self.reload_config)
        button_row.addStretch(1)
        button_row.addWidget(self.reload_beginner_btn)
        button_row.addWidget(self.save_beginner_btn)
        page_layout.addLayout(button_row)
        return page

    def _build_advanced_parameters(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.toml_editor = QTextEdit()
        self.toml_editor.setLineWrapMode(QTextEdit.NoWrap)
        self.toml_editor.setPlaceholderText("Load a project to edit Config.toml.")
        layout.addWidget(self.toml_editor, 1)

        button_row = QHBoxLayout()
        self.toml_status = QLabel("No Config.toml loaded")
        self.toml_status.setObjectName("HelpText")
        validate_btn = QPushButton(self._icon(QStyle.SP_DialogApplyButton), "Validate TOML")
        validate_btn.clicked.connect(self.validate_toml_editor)
        save_btn = QPushButton(self._icon(QStyle.SP_DialogSaveButton), "Save TOML")
        save_btn.clicked.connect(self.save_advanced_toml)
        reload_btn = QPushButton(self._icon(QStyle.SP_BrowserReload), "Reload")
        reload_btn.clicked.connect(self.reload_config)
        button_row.addWidget(self.toml_status)
        button_row.addStretch(1)
        button_row.addWidget(validate_btn)
        button_row.addWidget(reload_btn)
        button_row.addWidget(save_btn)
        layout.addLayout(button_row)
        return page

    def _build_pipeline_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        stage_group = QGroupBox("Pipeline stages")
        stage_layout = QGridLayout(stage_group)
        self.stage_checks: dict[str, QCheckBox] = {}
        for index, stage in enumerate(STAGES):
            check = QCheckBox(stage)
            check.setChecked(True)
            self.stage_checks[stage] = check
            stage_layout.addWidget(check, index // 4, index % 4)
        layout.addWidget(stage_group)

        button_row = QHBoxLayout()
        self.run_btn = QPushButton(self._icon(QStyle.SP_MediaPlay), "Run Selected Stages")
        self.run_btn.clicked.connect(self.run_pipeline)
        self.stop_btn = QPushButton(self._icon(QStyle.SP_MediaStop), "Stop")
        self.stop_btn.clicked.connect(self.stop_pipeline)
        self.stop_btn.setEnabled(False)
        button_row.addStretch(1)
        button_row.addWidget(self.run_btn)
        button_row.addWidget(self.stop_btn)
        layout.addLayout(button_row)

        self.pipeline_log = QPlainTextEdit()
        self.pipeline_log.setReadOnly(True)
        self.pipeline_log.setPlaceholderText("Pose2Sim logs will stream here while the pipeline runs.")
        layout.addWidget(self.pipeline_log, 1)
        return page

    def _build_reports_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        form_group = QGroupBox("Report inputs")
        form = QFormLayout(form_group)
        self.mot_combo = QComboBox()
        self.mot_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.video_combo = QComboBox()
        self.video_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        form.addRow("OpenSim .mot", self.mot_combo)
        form.addRow("Video", self.video_combo)
        layout.addWidget(form_group)

        button_row = QHBoxLayout()
        refresh_btn = QPushButton(self._icon(QStyle.SP_BrowserReload), "Refresh Files")
        refresh_btn.clicked.connect(self.refresh_report_files)
        excel_btn = QPushButton(self._icon(QStyle.SP_DialogSaveButton), "Generate Excel")
        excel_btn.clicked.connect(self.generate_excel_report)
        html_btn = QPushButton(self._icon(QStyle.SP_FileDialogContentsView), "Generate HTML")
        html_btn.clicked.connect(self.generate_html_report)
        both_btn = QPushButton(self._icon(QStyle.SP_DialogApplyButton), "Generate Both")
        both_btn.clicked.connect(self.generate_both_reports)
        button_row.addStretch(1)
        button_row.addWidget(refresh_btn)
        button_row.addWidget(excel_btn)
        button_row.addWidget(html_btn)
        button_row.addWidget(both_btn)
        layout.addLayout(button_row)

        self.report_log = QPlainTextEdit()
        self.report_log.setReadOnly(True)
        self.report_log.setPlaceholderText("Generated report paths and video compatibility notes will appear here.")
        layout.addWidget(self.report_log, 1)
        return page

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f6f7f9;
                color: #1f2933;
                font-size: 13px;
            }
            QTabWidget::pane, QGroupBox, QPlainTextEdit, QTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                border: 1px solid #cfd6df;
                border-radius: 6px;
                background: #ffffff;
            }
            QGroupBox {
                margin-top: 12px;
                padding: 12px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QPushButton {
                border: 1px solid #aab4c2;
                border-radius: 6px;
                background: #ffffff;
                padding: 7px 10px;
            }
            QPushButton:hover { background: #eef4ff; }
            QPushButton:disabled { color: #8a95a3; background: #eef0f3; }
            QPlainTextEdit, QTextEdit {
                padding: 8px;
                font-family: Consolas, "Courier New", monospace;
            }
            #AppTitle {
                font-size: 22px;
                font-weight: 700;
            }
            #ProjectLabel, #HelpText {
                color: #52606d;
            }
            """
        )

    def _set_project_dependent_enabled(self, enabled: bool) -> None:
        for widget in (
            self.tabs.widget(1),
            self.tabs.widget(2),
            self.tabs.widget(3),
        ):
            widget.setEnabled(enabled)

    def choose_project(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose Pose2Sim project folder")
        if folder:
            self.load_project(Path(folder))

    def create_project_from_demo(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose a folder for the new Pose2Sim project")
        if not folder:
            return
        try:
            path = copy_demo_config(Path(folder))
            self.load_project(path.parent)
            self.status_text.appendPlainText(f"Created {path}")
        except Exception as exc:
            self._error("Could not create project", exc)

    def open_installed_demo(self) -> None:
        try:
            self.load_project(demo_config_path().parent)
        except Exception as exc:
            self._error("Could not open installed demo", exc)

    def load_project(self, project_dir: Path) -> None:
        project_dir = Path(project_dir).resolve()
        try:
            self.config = load_config(project_dir)
            self.project_dir = project_dir
            self.project_edit.setText(str(project_dir))
            self.project_label.setText(str(project_dir))
            self._set_project_dependent_enabled(True)
            self.populate_beginner_controls()
            self.toml_editor.setPlainText(load_config_text(project_dir))
            self.toml_status.setText("Config.toml loaded")
            self.validate_project()
            self.refresh_report_files()
        except Exception as exc:
            self._set_project_dependent_enabled(False)
            self._error("Could not load project", exc)

    def reload_config(self) -> None:
        if not self.project_dir:
            return
        self.load_project(self.project_dir)

    def validate_project(self) -> None:
        project_text = self.project_edit.text().strip()
        if not project_text:
            self.status_text.setPlainText("Choose a project folder first.")
            return
        status = project_status(Path(project_text))
        self.status_text.setPlainText("\n".join(status.summary_lines()))

    def populate_beginner_controls(self) -> None:
        if self.config is None:
            return
        cfg = self.config
        self.multi_person.setChecked(bool(get_nested(cfg, ["project", "multi_person"], False)))
        self.participant_height.setText(display_toml_value(get_nested(cfg, ["project", "participant_height"], "auto")))
        self.participant_mass.setText(display_toml_value(get_nested(cfg, ["project", "participant_mass"], 70.0)))
        self.frame_rate.setText(display_toml_value(get_nested(cfg, ["project", "frame_rate"], "auto")))
        self.frame_range.setText(display_toml_value(get_nested(cfg, ["project", "frame_range"], "auto")))

        self._set_combo_value(self.pose_model, get_nested(cfg, ["pose", "pose_model"], "Body_with_feet"))
        self._set_combo_value(self.pose_mode, get_nested(cfg, ["pose", "mode"], "balanced"))
        self._set_combo_value(self.device, get_nested(cfg, ["pose", "device"], "auto"))
        self._set_combo_value(self.backend, get_nested(cfg, ["pose", "backend"], "auto"))
        self.det_frequency.setValue(int(get_nested(cfg, ["pose", "det_frequency"], 4)))
        self.average_likelihood.setValue(float(get_nested(cfg, ["pose", "average_likelihood_threshold_pose"], 0.5)))
        self.display_detection.setChecked(bool(get_nested(cfg, ["pose", "display_detection"], True)))
        self.overwrite_pose.setChecked(bool(get_nested(cfg, ["pose", "overwrite_pose"], False)))
        self._set_combo_value(self.save_video, get_nested(cfg, ["pose", "save_video"], "to_video"))
        self._set_combo_value(self.tracking_mode, get_nested(cfg, ["pose", "tracking_mode"], "sports2d"))

        self.synchronization_gui.setChecked(bool(get_nested(cfg, ["synchronization", "synchronization_gui"], True)))
        self.display_sync_plots.setChecked(bool(get_nested(cfg, ["synchronization", "display_sync_plots"], True)))
        self.save_sync_plots.setChecked(bool(get_nested(cfg, ["synchronization", "save_sync_plots"], True)))
        self._set_combo_value(self.calibration_type, get_nested(cfg, ["calibration", "calibration_type"], "convert"))
        self._set_combo_value(self.convert_from, get_nested(cfg, ["calibration", "convert", "convert_from"], "qualisys"))
        self.intrinsics_extension.setText(str(get_nested(cfg, ["calibration", "calculate", "intrinsics", "intrinsics_extension"], "jpg")))
        self._set_combo_value(self.extrinsics_method, get_nested(cfg, ["calibration", "calculate", "extrinsics", "extrinsics_method"], "scene"))

        self.tracked_keypoint.setText(str(get_nested(cfg, ["personAssociation", "single_person", "tracked_keypoint"], "Neck")))
        self.reproj_assoc.setValue(float(get_nested(cfg, ["personAssociation", "single_person", "reproj_error_threshold_association"], 20)))
        self.reproj_triangulation.setValue(float(get_nested(cfg, ["triangulation", "reproj_error_threshold_triangulation"], 15)))
        self.min_cameras.setValue(int(get_nested(cfg, ["triangulation", "min_cameras_for_triangulation"], 2)))
        self._set_combo_value(self.interpolation, get_nested(cfg, ["triangulation", "interpolation"], "linear"))

        self.reject_outliers.setChecked(bool(get_nested(cfg, ["filtering", "reject_outliers"], True)))
        self.filter_enabled.setChecked(bool(get_nested(cfg, ["filtering", "filter"], True)))
        self._set_combo_value(self.filter_type, get_nested(cfg, ["filtering", "type"], "butterworth"))
        self.filter_cutoff.setValue(float(get_nested(cfg, ["filtering", "butterworth", "cut_off_frequency"], 6)))
        self.filter_order.setValue(int(get_nested(cfg, ["filtering", "butterworth", "order"], 4)))
        self.display_figures.setChecked(bool(get_nested(cfg, ["filtering", "display_figures"], True)))
        self.save_filt_plots.setChecked(bool(get_nested(cfg, ["filtering", "save_filt_plots"], True)))

        self.feet_on_floor.setChecked(bool(get_nested(cfg, ["markerAugmentation", "feet_on_floor"], False)))
        self.use_augmentation.setChecked(bool(get_nested(cfg, ["kinematics", "use_augmentation"], True)))
        self.use_simple_model.setChecked(bool(get_nested(cfg, ["kinematics", "use_simple_model"], False)))
        self.right_left_symmetry.setChecked(bool(get_nested(cfg, ["kinematics", "right_left_symmetry"], True)))
        self.default_height.setValue(float(get_nested(cfg, ["kinematics", "default_height"], 1.7)))

    def _set_combo_value(self, combo: QComboBox, value: Any) -> None:
        text = str(value)
        index = combo.findText(text)
        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            combo.setCurrentIndex(0)

    def save_beginner_settings(self) -> None:
        if not self.project_dir or self.config is None:
            return
        cfg = self.config
        set_nested(cfg, ["project", "multi_person"], self.multi_person.isChecked())
        set_nested(cfg, ["project", "participant_height"], parse_toml_value(self.participant_height.text()))
        set_nested(cfg, ["project", "participant_mass"], parse_toml_value(self.participant_mass.text()))
        set_nested(cfg, ["project", "frame_rate"], parse_toml_value(self.frame_rate.text()))
        set_nested(cfg, ["project", "frame_range"], parse_toml_value(self.frame_range.text()))

        set_nested(cfg, ["pose", "pose_model"], self.pose_model.currentText())
        set_nested(cfg, ["pose", "mode"], self.pose_mode.currentText())
        set_nested(cfg, ["pose", "device"], self.device.currentText())
        set_nested(cfg, ["pose", "backend"], self.backend.currentText())
        set_nested(cfg, ["pose", "det_frequency"], self.det_frequency.value())
        set_nested(cfg, ["pose", "average_likelihood_threshold_pose"], self.average_likelihood.value())
        set_nested(cfg, ["pose", "display_detection"], self.display_detection.isChecked())
        set_nested(cfg, ["pose", "overwrite_pose"], self.overwrite_pose.isChecked())
        set_nested(cfg, ["pose", "save_video"], self.save_video.currentText())
        set_nested(cfg, ["pose", "tracking_mode"], self.tracking_mode.currentText())

        set_nested(cfg, ["synchronization", "synchronization_gui"], self.synchronization_gui.isChecked())
        set_nested(cfg, ["synchronization", "display_sync_plots"], self.display_sync_plots.isChecked())
        set_nested(cfg, ["synchronization", "save_sync_plots"], self.save_sync_plots.isChecked())
        set_nested(cfg, ["calibration", "calibration_type"], self.calibration_type.currentText())
        set_nested(cfg, ["calibration", "convert", "convert_from"], self.convert_from.currentText())
        set_nested(cfg, ["calibration", "calculate", "intrinsics", "intrinsics_extension"], self.intrinsics_extension.text().strip() or "jpg")
        set_nested(cfg, ["calibration", "calculate", "extrinsics", "extrinsics_method"], self.extrinsics_method.currentText())

        set_nested(cfg, ["personAssociation", "single_person", "tracked_keypoint"], self.tracked_keypoint.text().strip() or "Neck")
        set_nested(cfg, ["personAssociation", "single_person", "reproj_error_threshold_association"], self.reproj_assoc.value())
        set_nested(cfg, ["triangulation", "reproj_error_threshold_triangulation"], self.reproj_triangulation.value())
        set_nested(cfg, ["triangulation", "min_cameras_for_triangulation"], self.min_cameras.value())
        set_nested(cfg, ["triangulation", "interpolation"], self.interpolation.currentText())

        set_nested(cfg, ["filtering", "reject_outliers"], self.reject_outliers.isChecked())
        set_nested(cfg, ["filtering", "filter"], self.filter_enabled.isChecked())
        set_nested(cfg, ["filtering", "type"], self.filter_type.currentText())
        set_nested(cfg, ["filtering", "butterworth", "cut_off_frequency"], self.filter_cutoff.value())
        set_nested(cfg, ["filtering", "butterworth", "order"], self.filter_order.value())
        set_nested(cfg, ["filtering", "display_figures"], self.display_figures.isChecked())
        set_nested(cfg, ["filtering", "save_filt_plots"], self.save_filt_plots.isChecked())

        set_nested(cfg, ["markerAugmentation", "feet_on_floor"], self.feet_on_floor.isChecked())
        set_nested(cfg, ["kinematics", "use_augmentation"], self.use_augmentation.isChecked())
        set_nested(cfg, ["kinematics", "use_simple_model"], self.use_simple_model.isChecked())
        set_nested(cfg, ["kinematics", "right_left_symmetry"], self.right_left_symmetry.isChecked())
        set_nested(cfg, ["kinematics", "default_height"], self.default_height.value())

        warnings = apply_beginner_safety(cfg)
        try:
            save_config(self.project_dir, cfg)
            self.toml_editor.setPlainText(load_config_text(self.project_dir))
            message = "Beginner settings saved."
            if warnings:
                message += "\n\n" + "\n".join(warnings)
            QMessageBox.information(self, "Saved", message)
        except Exception as exc:
            self._error("Could not save settings", exc)

    def validate_toml_editor(self) -> None:
        ok, message = validate_toml_text(self.toml_editor.toPlainText())
        self.toml_status.setText(message)
        if ok:
            QMessageBox.information(self, "TOML", message)
        else:
            QMessageBox.warning(self, "TOML", message)

    def save_advanced_toml(self) -> None:
        if not self.project_dir:
            return
        try:
            save_config_text(self.project_dir, self.toml_editor.toPlainText())
            self.config = load_config(self.project_dir)
            self.populate_beginner_controls()
            self.toml_status.setText("Config.toml saved")
            QMessageBox.information(self, "Saved", "Config.toml saved.")
        except Exception as exc:
            self._error("Could not save TOML", exc)

    def run_pipeline(self) -> None:
        if not self.project_dir:
            self._message("No project", "Load a project first.")
            return
        stages = [stage for stage, check in self.stage_checks.items() if check.isChecked()]
        if not stages:
            self._message("No stages selected", "Choose at least one pipeline stage.")
            return

        self.pipeline_log.clear()
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._append_process_output)
        self.process.finished.connect(self._process_finished)
        args = ["-m", "pose2sim_gui.runner", "--config", str(self.project_dir), "--stages", *stages]
        self.pipeline_log.appendPlainText(f"Running: {sys.executable} {' '.join(args)}\n")
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.process.start(sys.executable, args)

    def _append_process_output(self) -> None:
        if not self.process:
            return
        data = bytes(self.process.readAllStandardOutput()).decode(errors="replace")
        if data:
            self.pipeline_log.moveCursor(self.pipeline_log.textCursor().MoveOperation.End)
            self.pipeline_log.insertPlainText(data)
            self.pipeline_log.moveCursor(self.pipeline_log.textCursor().MoveOperation.End)

    def _process_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.pipeline_log.appendPlainText(f"\nProcess finished with exit code {exit_code}.")
        self.refresh_report_files()
        self.process = None

    def stop_pipeline(self) -> None:
        if self.process:
            self.process.kill()
            self.pipeline_log.appendPlainText("\nStop requested.")

    def refresh_report_files(self) -> None:
        self.mot_combo.clear()
        self.video_combo.clear()
        self.video_combo.addItem("No video", None)
        if not self.project_dir:
            return
        for mot in find_mot_files(self.project_dir):
            self.mot_combo.addItem(str(mot.relative_to(self.project_dir)), str(mot))
        for video in find_video_files(self.project_dir):
            self.video_combo.addItem(str(video.relative_to(self.project_dir)), str(video))
        self.report_log.appendPlainText(
            f"Found {self.mot_combo.count()} .mot file(s) and {max(0, self.video_combo.count() - 1)} video file(s)."
        )

    def _selected_mot(self) -> Path | None:
        data = self.mot_combo.currentData()
        return Path(data) if data else None

    def _selected_video(self) -> Path | None:
        data = self.video_combo.currentData()
        return Path(data) if data else None

    def generate_excel_report(self) -> Path | None:
        mot = self._selected_mot()
        if not mot:
            self._message("No .mot file", "Run kinematics first or choose a project with kinematics/*.mot.")
            return None
        try:
            output = export_excel(mot)
            self.report_log.appendPlainText(f"Excel report: {output}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(output.parent)))
            return output
        except Exception as exc:
            self._error("Could not generate Excel report", exc)
            return None

    def generate_html_report(self) -> Path | None:
        mot = self._selected_mot()
        if not mot:
            self._message("No .mot file", "Run kinematics first or choose a project with kinematics/*.mot.")
            return None
        try:
            output, warnings = export_html(mot, self._selected_video())
            self.report_log.appendPlainText(f"HTML report: {output}")
            for warning in warnings:
                self.report_log.appendPlainText(f"Warning: {warning}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(output)))
            return output
        except Exception as exc:
            self._error("Could not generate HTML report", exc)
            return None

    def generate_both_reports(self) -> None:
        self.generate_excel_report()
        self.generate_html_report()

    def _message(self, title: str, text: str) -> None:
        QMessageBox.information(self, title, text)

    def _error(self, title: str, exc: Exception) -> None:
        QMessageBox.critical(self, title, str(exc))


def create_app(argv: list[str] | None = None) -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(argv or sys.argv)
    app.setApplicationName("Pose2Sim GUI")
    app.setApplicationVersion(__version__)
    return app


def run_gui(argv: list[str] | None = None) -> int:
    app = create_app(argv)
    window = Pose2SimMainWindow()
    window.show()
    return app.exec()
