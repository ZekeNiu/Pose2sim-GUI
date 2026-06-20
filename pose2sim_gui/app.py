from __future__ import annotations

from pathlib import Path
import shutil
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
    ensure_standard_project_folders,
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
from .help_text import HELP_TEXTS, MANUAL_TEXT, STAGE_LABELS
from .reports import default_report_dir, export_excel, export_html, find_mot_files, find_video_files


class Pose2SimMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Pose2Sim 图形界面")
        self.resize(1180, 760)
        self.project_dir: Path | None = None
        self.config: dict[str, Any] | None = None
        self.process: QProcess | None = None

        self._build_actions()
        self._build_ui()
        self._apply_style()

    def _icon(self, standard_pixmap: QStyle.StandardPixmap):
        return self.style().standardIcon(standard_pixmap)

    def _info_button(self, key: str, title: str = "说明") -> QPushButton:
        button = QPushButton("?")
        button.setFixedSize(26, 26)
        button.setToolTip("点击查看详细说明")
        button.clicked.connect(lambda: self.show_help(key, title))
        return button

    def _with_info(self, widget: QWidget, key: str) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(widget, 1)
        layout.addWidget(self._info_button(key))
        help_text = HELP_TEXTS.get(key)
        if help_text:
            widget.setToolTip(help_text)
        return container

    def _add_info_row(self, form: QFormLayout, label: str, widget: QWidget, key: str) -> None:
        form.addRow(label, self._with_info(widget, key))

    def show_help(self, key: str, title: str = "说明") -> None:
        QMessageBox.information(self, title, HELP_TEXTS.get(key, "暂无说明。"))

    def _build_actions(self) -> None:
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.close)

        open_action = QAction("打开项目", self)
        open_action.triggered.connect(self.choose_project)

        menu = self.menuBar().addMenu("文件")
        menu.addAction(open_action)
        menu.addSeparator()
        menu.addAction(quit_action)

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        title = QLabel("Pose2Sim 图形界面")
        title.setObjectName("AppTitle")
        self.project_label = QLabel("尚未载入项目")
        self.project_label.setObjectName("ProjectLabel")
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(self.project_label)
        layout.addLayout(title_row)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_project_tab(), "项目")
        self.tabs.addTab(self._build_parameters_tab(), "参数")
        self.tabs.addTab(self._build_pipeline_tab(), "流程")
        self.tabs.addTab(self._build_reports_tab(), "报告")
        self.tabs.addTab(self._build_help_tab(), "使用说明")
        layout.addWidget(self.tabs, 1)

        self.setCentralWidget(root)
        self._set_project_dependent_enabled(False)

    def _build_project_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        group = QGroupBox("项目文件夹")
        grid = QGridLayout(group)
        self.project_edit = QLineEdit()
        self.project_edit.setPlaceholderText("请选择包含 Config.toml 的 Pose2Sim 项目文件夹")

        browse_btn = QPushButton(self._icon(QStyle.SP_DirOpenIcon), "浏览项目")
        browse_btn.setToolTip("选择已有 Pose2Sim 项目文件夹")
        browse_btn.clicked.connect(self.choose_project)

        create_btn = QPushButton(self._icon(QStyle.SP_FileDialogNewFolder), "用示例配置新建")
        create_btn.setToolTip("在空文件夹中复制 Pose2Sim 示例 Config.toml，并创建标准文件夹")
        create_btn.clicked.connect(self.create_project_from_demo)

        demo_btn = QPushButton(self._icon(QStyle.SP_ComputerIcon), "打开内置示例")
        demo_btn.setToolTip("打开已安装 Pose2Sim 的单人示例项目")
        demo_btn.clicked.connect(self.open_installed_demo)

        folders_btn = QPushButton(self._icon(QStyle.SP_DirIcon), "创建标准文件夹")
        folders_btn.setToolTip("在当前项目中创建 videos、calibration、reports 文件夹")
        folders_btn.clicked.connect(self.create_standard_folders)

        import_btn = QPushButton(self._icon(QStyle.SP_DialogOpenButton), "导入录制视频")
        import_btn.setToolTip("把已经录制好的多机位视频复制到当前项目的 videos 文件夹")
        import_btn.clicked.connect(self.import_recorded_videos)

        validate_btn = QPushButton(self._icon(QStyle.SP_DialogApplyButton), "检查项目")
        validate_btn.clicked.connect(self.validate_project)

        info_btn = self._info_button("project_folder")
        grid.addWidget(self.project_edit, 0, 0, 1, 5)
        grid.addWidget(info_btn, 0, 5)
        grid.addWidget(browse_btn, 1, 0)
        grid.addWidget(create_btn, 1, 1)
        grid.addWidget(demo_btn, 1, 2)
        grid.addWidget(folders_btn, 1, 3)
        grid.addWidget(import_btn, 1, 4)
        grid.addWidget(validate_btn, 1, 5)
        grid.setColumnStretch(0, 1)
        layout.addWidget(group)

        self.status_text = QPlainTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setPlaceholderText("项目检查结果会显示在这里。")
        layout.addWidget(self.status_text, 1)

        note = QLabel(
            "推荐结构：Config.toml、videos/、calibration/。录制好的视频放入 videos/；校准文件或校准素材放入 calibration/；"
            "Pose2Sim 会自动生成 pose/、pose-sync/、pose-3d/、kinematics/，本 GUI 的报告放入 reports/。"
        )
        note.setWordWrap(True)
        note.setObjectName("HelpText")
        layout.addWidget(note)
        return page

    def _build_parameters_tab(self) -> QWidget:
        outer = QTabWidget()
        outer.addTab(self._build_beginner_parameters(), "新手参数")
        outer.addTab(self._build_advanced_parameters(), "高级 TOML")
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

        project_group = QGroupBox("项目参数")
        project_form = QFormLayout(project_group)
        self.multi_person = QCheckBox("启用")
        self.participant_height = QLineEdit()
        self.participant_mass = QLineEdit()
        self.frame_rate = QLineEdit()
        self.frame_range = QLineEdit()
        self._add_info_row(project_form, "多人分析", self.multi_person, "multi_person")
        self._add_info_row(project_form, "被试身高", self.participant_height, "participant_height")
        self._add_info_row(project_form, "被试体重", self.participant_mass, "participant_mass")
        self._add_info_row(project_form, "视频帧率", self.frame_rate, "frame_rate")
        self._add_info_row(project_form, "分析帧范围", self.frame_range, "frame_range")
        form_layout.addWidget(project_group)

        pose_group = QGroupBox("二维姿态识别")
        pose_form = QFormLayout(pose_group)
        self.pose_model = self._combo(POSE_MODELS)
        self.pose_mode = self._combo(POSE_MODES)
        self.device = self._combo(DEVICES)
        self.backend = self._combo(BACKENDS)
        self.display_detection = QCheckBox("启用")
        self.overwrite_pose = QCheckBox("启用")
        self.save_video = self._combo(["to_video", "to_images", "none"])
        self.tracking_mode = self._combo(TRACKING_MODES)
        self.det_frequency = QSpinBox()
        self.det_frequency.setRange(1, 9999)
        self.average_likelihood = QDoubleSpinBox()
        self.average_likelihood.setRange(0.0, 1.0)
        self.average_likelihood.setSingleStep(0.05)
        self._add_info_row(pose_form, "姿态模型", self.pose_model, "pose_model")
        self._add_info_row(pose_form, "模型模式", self.pose_mode, "pose_mode")
        self._add_info_row(pose_form, "计算设备", self.device, "device")
        self._add_info_row(pose_form, "推理后端", self.backend, "backend")
        self._add_info_row(pose_form, "人体检测间隔", self.det_frequency, "det_frequency")
        self._add_info_row(pose_form, "平均置信度阈值", self.average_likelihood, "average_likelihood")
        self._add_info_row(pose_form, "显示识别窗口", self.display_detection, "display_detection")
        self._add_info_row(pose_form, "覆盖已有姿态结果", self.overwrite_pose, "overwrite_pose")
        self._add_info_row(pose_form, "保存叠加结果", self.save_video, "save_video")
        self._add_info_row(pose_form, "跟踪方式", self.tracking_mode, "tracking_mode")
        form_layout.addWidget(pose_group)

        sync_calib_group = QGroupBox("同步与校准")
        sync_form = QFormLayout(sync_calib_group)
        self.synchronization_gui = QCheckBox("启用")
        self.display_sync_plots = QCheckBox("启用")
        self.save_sync_plots = QCheckBox("启用")
        self.calibration_type = self._combo(["convert", "calculate"])
        self.convert_from = self._combo(
            ["qualisys", "caliscope", "optitrack", "vicon", "opencap", "easymocap", "biocv", "anipose", "freemocap"]
        )
        self.intrinsics_extension = QLineEdit()
        self.extrinsics_method = self._combo(["scene", "board"])
        self._add_info_row(sync_form, "同步交互窗口", self.synchronization_gui, "synchronization_gui")
        self._add_info_row(sync_form, "显示同步图", self.display_sync_plots, "display_sync_plots")
        self._add_info_row(sync_form, "保存同步图", self.save_sync_plots, "save_sync_plots")
        self._add_info_row(sync_form, "校准方式", self.calibration_type, "calibration_type")
        self._add_info_row(sync_form, "校准来源", self.convert_from, "convert_from")
        self._add_info_row(sync_form, "内参素材扩展名", self.intrinsics_extension, "intrinsics_extension")
        self._add_info_row(sync_form, "外参方法", self.extrinsics_method, "extrinsics_method")
        form_layout.addWidget(sync_calib_group)

        association_group = QGroupBox("人物匹配与三维重建")
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
        self._add_info_row(assoc_form, "跟踪关键点", self.tracked_keypoint, "tracked_keypoint")
        self._add_info_row(assoc_form, "人物匹配重投影误差", self.reproj_assoc, "reproj_assoc")
        self._add_info_row(assoc_form, "三维重建重投影误差", self.reproj_triangulation, "reproj_triangulation")
        self._add_info_row(assoc_form, "最少相机数", self.min_cameras, "min_cameras")
        self._add_info_row(assoc_form, "缺失点插值", self.interpolation, "interpolation")
        form_layout.addWidget(association_group)

        filtering_group = QGroupBox("轨迹滤波")
        filtering_form = QFormLayout(filtering_group)
        self.reject_outliers = QCheckBox("启用")
        self.filter_enabled = QCheckBox("启用")
        self.filter_type = self._combo(FILTER_TYPES)
        self.filter_cutoff = QDoubleSpinBox()
        self.filter_cutoff.setRange(0.0, 1000.0)
        self.filter_cutoff.setSuffix(" Hz")
        self.filter_order = QSpinBox()
        self.filter_order.setRange(1, 32)
        self.display_figures = QCheckBox("启用")
        self.save_filt_plots = QCheckBox("启用")
        self._add_info_row(filtering_form, "异常值剔除", self.reject_outliers, "reject_outliers")
        self._add_info_row(filtering_form, "继续滤波", self.filter_enabled, "filter_enabled")
        self._add_info_row(filtering_form, "滤波方法", self.filter_type, "filter_type")
        self._add_info_row(filtering_form, "Butterworth 截止频率", self.filter_cutoff, "filter_cutoff")
        self._add_info_row(filtering_form, "Butterworth 阶数", self.filter_order, "filter_order")
        self._add_info_row(filtering_form, "显示滤波图", self.display_figures, "display_figures")
        self._add_info_row(filtering_form, "保存滤波图", self.save_filt_plots, "save_filt_plots")
        form_layout.addWidget(filtering_group)

        kin_group = QGroupBox("虚拟标记点增强与 OpenSim 运动学")
        kin_form = QFormLayout(kin_group)
        self.feet_on_floor = QCheckBox("启用")
        self.use_augmentation = QCheckBox("启用")
        self.use_simple_model = QCheckBox("启用")
        self.right_left_symmetry = QCheckBox("启用")
        self.default_height = QDoubleSpinBox()
        self.default_height.setRange(0.5, 2.5)
        self.default_height.setSingleStep(0.01)
        self.default_height.setSuffix(" m")
        self._add_info_row(kin_form, "足部对齐地面", self.feet_on_floor, "feet_on_floor")
        self._add_info_row(kin_form, "使用增强标记点", self.use_augmentation, "use_augmentation")
        self._add_info_row(kin_form, "使用简化模型", self.use_simple_model, "use_simple_model")
        self._add_info_row(kin_form, "左右对称假设", self.right_left_symmetry, "right_left_symmetry")
        self._add_info_row(kin_form, "默认身高", self.default_height, "default_height")
        form_layout.addWidget(kin_group)

        scroll.setWidget(content)
        page_layout.addWidget(scroll, 1)

        button_row = QHBoxLayout()
        self.save_beginner_btn = QPushButton(self._icon(QStyle.SP_DialogSaveButton), "保存新手参数")
        self.save_beginner_btn.clicked.connect(self.save_beginner_settings)
        self.reload_beginner_btn = QPushButton(self._icon(QStyle.SP_BrowserReload), "重新载入")
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
        self.toml_editor.setPlaceholderText("请先载入项目，然后在这里编辑完整 Config.toml。")
        layout.addWidget(self.toml_editor, 1)

        button_row = QHBoxLayout()
        self.toml_status = QLabel("尚未载入 Config.toml")
        self.toml_status.setObjectName("HelpText")
        validate_btn = QPushButton(self._icon(QStyle.SP_DialogApplyButton), "检查 TOML")
        validate_btn.clicked.connect(self.validate_toml_editor)
        save_btn = QPushButton(self._icon(QStyle.SP_DialogSaveButton), "保存 TOML")
        save_btn.clicked.connect(self.save_advanced_toml)
        reload_btn = QPushButton(self._icon(QStyle.SP_BrowserReload), "重新载入")
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
        stage_group = QGroupBox("Pose2Sim 处理流程")
        stage_layout = QGridLayout(stage_group)
        self.stage_checks: dict[str, QCheckBox] = {}
        for index, stage in enumerate(STAGES):
            check = QCheckBox(STAGE_LABELS.get(stage, stage))
            check.setChecked(True)
            self.stage_checks[stage] = check
            stage_widget = QWidget()
            stage_widget_layout = QHBoxLayout(stage_widget)
            stage_widget_layout.setContentsMargins(0, 0, 0, 0)
            stage_widget_layout.addWidget(check, 1)
            stage_widget_layout.addWidget(self._info_button(f"stage_{stage}", STAGE_LABELS.get(stage, stage)))
            stage_layout.addWidget(stage_widget, index // 4, index % 4)
        layout.addWidget(stage_group)

        button_row = QHBoxLayout()
        self.run_btn = QPushButton(self._icon(QStyle.SP_MediaPlay), "运行选中步骤")
        self.run_btn.clicked.connect(self.run_pipeline)
        self.stop_btn = QPushButton(self._icon(QStyle.SP_MediaStop), "停止")
        self.stop_btn.clicked.connect(self.stop_pipeline)
        self.stop_btn.setEnabled(False)
        button_row.addStretch(1)
        button_row.addWidget(self.run_btn)
        button_row.addWidget(self.stop_btn)
        layout.addLayout(button_row)

        self.pipeline_log = QPlainTextEdit()
        self.pipeline_log.setReadOnly(True)
        self.pipeline_log.setPlaceholderText("运行流程时，Pose2Sim 日志会实时显示在这里。")
        layout.addWidget(self.pipeline_log, 1)
        return page

    def _build_reports_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        form_group = QGroupBox("报告输入")
        form = QFormLayout(form_group)
        self.mot_combo = QComboBox()
        self.mot_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.video_combo = QComboBox()
        self.video_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._add_info_row(form, "OpenSim .mot 文件", self.mot_combo, "mot_file")
        self._add_info_row(form, "同步显示视频", self.video_combo, "report_video")
        layout.addWidget(form_group)

        button_row = QHBoxLayout()
        refresh_btn = QPushButton(self._icon(QStyle.SP_BrowserReload), "刷新文件")
        refresh_btn.clicked.connect(self.refresh_report_files)
        excel_btn = QPushButton(self._icon(QStyle.SP_DialogSaveButton), "生成 Excel")
        excel_btn.clicked.connect(self.generate_excel_report)
        html_btn = QPushButton(self._icon(QStyle.SP_FileDialogContentsView), "生成 HTML")
        html_btn.clicked.connect(self.generate_html_report)
        both_btn = QPushButton(self._icon(QStyle.SP_DialogApplyButton), "全部生成")
        both_btn.clicked.connect(self.generate_both_reports)
        button_row.addStretch(1)
        button_row.addWidget(refresh_btn)
        button_row.addWidget(excel_btn)
        button_row.addWidget(html_btn)
        button_row.addWidget(both_btn)
        layout.addLayout(button_row)

        self.report_log = QPlainTextEdit()
        self.report_log.setReadOnly(True)
        self.report_log.setPlaceholderText("报告路径和视频兼容性提示会显示在这里。")
        layout.addWidget(self.report_log, 1)
        return page

    def _build_help_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        viewer = QTextEdit()
        viewer.setReadOnly(True)
        viewer.setMarkdown(MANUAL_TEXT)
        layout.addWidget(viewer, 1)
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
        folder = QFileDialog.getExistingDirectory(self, "选择 Pose2Sim 项目文件夹")
        if folder:
            self.load_project(Path(folder))

    def create_project_from_demo(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择新 Pose2Sim 项目文件夹")
        if not folder:
            return
        try:
            path = copy_demo_config(Path(folder))
            self.load_project(path.parent)
            self.status_text.appendPlainText(f"已创建：{path}")
        except Exception as exc:
            self._error("无法创建项目", exc)

    def create_standard_folders(self) -> None:
        project_text = self.project_edit.text().strip()
        if not project_text:
            self._message("尚未选择项目", "请先选择或新建一个项目文件夹。")
            return
        try:
            folders = ensure_standard_project_folders(Path(project_text))
            self.status_text.appendPlainText("已确认标准文件夹：")
            for folder in folders:
                self.status_text.appendPlainText(f"  {folder}")
            if self.project_dir:
                self.refresh_report_files()
        except Exception as exc:
            self._error("无法创建标准文件夹", exc)

    def import_recorded_videos(self) -> None:
        project_text = self.project_edit.text().strip()
        if not project_text:
            self._message("尚未选择项目", "请先选择或新建一个项目文件夹。")
            return
        project_dir = Path(project_text).resolve()
        videos_dir = project_dir / "videos"
        videos_dir.mkdir(parents=True, exist_ok=True)
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择要导入的录制视频",
            str(project_dir),
            "视频文件 (*.mp4 *.m4v *.mov *.avi *.mkv *.webm *.ogg *.ogv);;所有文件 (*.*)",
        )
        if not files:
            return
        try:
            copied: list[Path] = []
            for file_name in files:
                source = Path(file_name)
                destination = videos_dir / source.name
                if source.resolve() != destination.resolve():
                    shutil.copy2(source, destination)
                copied.append(destination)
            self.status_text.appendPlainText("已导入视频到 videos/：")
            for item in copied:
                self.status_text.appendPlainText(f"  {item.name}")
            if self.project_dir:
                self.refresh_report_files()
        except Exception as exc:
            self._error("无法导入视频", exc)

    def open_installed_demo(self) -> None:
        try:
            self.load_project(demo_config_path().parent)
        except Exception as exc:
            self._error("无法打开内置示例", exc)

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
            self.toml_status.setText("Config.toml 已载入")
            self.validate_project()
            self.refresh_report_files()
        except Exception as exc:
            self._set_project_dependent_enabled(False)
            self._error("无法载入项目", exc)

    def reload_config(self) -> None:
        if not self.project_dir:
            return
        self.load_project(self.project_dir)

    def validate_project(self) -> None:
        project_text = self.project_edit.text().strip()
        if not project_text:
            self.status_text.setPlainText("请先选择项目文件夹。")
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
            message = "新手参数已保存。"
            if warnings:
                message += "\n\n" + "\n".join(warnings)
            QMessageBox.information(self, "已保存", message)
        except Exception as exc:
            self._error("无法保存参数", exc)

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
            self.toml_status.setText("Config.toml 已保存")
            QMessageBox.information(self, "已保存", "Config.toml 已保存。")
        except Exception as exc:
            self._error("无法保存 TOML", exc)

    def run_pipeline(self) -> None:
        if not self.project_dir:
            self._message("尚未载入项目", "请先载入一个项目。")
            return
        stages = [stage for stage, check in self.stage_checks.items() if check.isChecked()]
        if not stages:
            self._message("未选择流程步骤", "请至少选择一个 Pose2Sim 处理步骤。")
            return

        self.pipeline_log.clear()
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._append_process_output)
        self.process.finished.connect(self._process_finished)
        args = ["-m", "pose2sim_gui.runner", "--config", str(self.project_dir), "--stages", *stages]
        self.pipeline_log.appendPlainText(f"正在运行：{sys.executable} {' '.join(args)}\n")
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
        self.pipeline_log.appendPlainText(f"\n流程结束，退出码：{exit_code}。")
        self.refresh_report_files()
        self.process = None

    def stop_pipeline(self) -> None:
        if self.process:
            self.process.kill()
            self.pipeline_log.appendPlainText("\n已请求停止。")

    def refresh_report_files(self) -> None:
        self.mot_combo.clear()
        self.video_combo.clear()
        self.video_combo.addItem("不使用视频", None)
        if not self.project_dir:
            return
        for mot in find_mot_files(self.project_dir):
            self.mot_combo.addItem(str(mot.relative_to(self.project_dir)), str(mot))
        for video in find_video_files(self.project_dir):
            self.video_combo.addItem(str(video.relative_to(self.project_dir)), str(video))
        self.report_log.appendPlainText(
            f"找到 {self.mot_combo.count()} 个 .mot 文件和 {max(0, self.video_combo.count() - 1)} 个视频文件。"
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
            self._message("没有 .mot 文件", "请先运行 OpenSim 运动学，或选择已有 kinematics/*.mot 的项目。")
            return None
        try:
            report_dir = default_report_dir(self.project_dir or mot.parent)
            output = export_excel(mot, report_dir / f"{mot.stem}_joint_angles.xlsx")
            self.report_log.appendPlainText(f"Excel 报告：{output}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(output.parent)))
            return output
        except Exception as exc:
            self._error("无法生成 Excel 报告", exc)
            return None

    def generate_html_report(self) -> Path | None:
        mot = self._selected_mot()
        if not mot:
            self._message("没有 .mot 文件", "请先运行 OpenSim 运动学，或选择已有 kinematics/*.mot 的项目。")
            return None
        try:
            report_dir = default_report_dir(self.project_dir or mot.parent)
            output, warnings = export_html(mot, self._selected_video(), report_dir / f"{mot.stem}_joint_angles.html")
            self.report_log.appendPlainText(f"HTML 报告：{output}")
            for warning in warnings:
                self.report_log.appendPlainText(f"提示：{warning}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(output)))
            return output
        except Exception as exc:
            self._error("无法生成 HTML 报告", exc)
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
    app.setApplicationName("Pose2Sim 图形界面")
    app.setApplicationVersion(__version__)
    return app


def run_gui(argv: list[str] | None = None) -> int:
    app = create_app(argv)
    window = Pose2SimMainWindow()
    window.show()
    return app.exec()
