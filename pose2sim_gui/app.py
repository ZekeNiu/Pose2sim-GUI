from __future__ import annotations

from pathlib import Path
import shutil
import sys
from typing import Any, Iterable

from PySide6.QtCore import QProcess, Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHeaderView,
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
    QTableWidget,
    QTableWidgetItem,
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
    camera_names_from_videos,
    demo_config_path,
    display_toml_value,
    ensure_calibration_folders,
    ensure_project_config,
    ensure_standard_project_folders,
    get_nested,
    load_config,
    load_config_text,
    parse_toml_value,
    project_status,
    project_workflow_status,
    read_scene_points_csv,
    save_config,
    save_config_text,
    set_nested,
    validate_toml_text,
    validate_stage_prerequisites,
    write_scene_points_csv,
)
from .help_text import HELP_TEXTS, STAGE_LABELS
from .manual_zh import MANUAL_TEXT
from .reports import default_report_dir, export_excel, export_html, find_mot_files, find_report_video_files
from .workspace import (
    APP_ROOT,
    INPUT_DIR,
    OUTPUT_DIR,
    RAW_VIDEO_DIR,
    RESULTS_DIR,
    ensure_app_workspace,
    mirror_pose2sim_outputs,
    project_results_dir,
)


POSE_MODEL_OPTIONS = [
    ("身体+足部（默认，Body_with_feet）", "Body_with_feet"),
    ("全身+腕部（Whole_body_wrist）", "Whole_body_wrist"),
    ("全身含手脸（Whole_body）", "Whole_body"),
    ("下肢（Lower_body）", "Lower_body"),
    ("身体17点（Body）", "Body"),
    ("手部（Hand）", "Hand"),
    ("面部（Face）", "Face"),
    ("动物（Animal）", "Animal"),
]

POSE_MODE_OPTIONS = [
    ("轻量：最快，精度较低（lightweight）", "lightweight"),
    ("均衡：推荐默认（balanced）", "balanced"),
    ("高性能：较慢，通常更稳（performance）", "performance"),
]

DEVICE_OPTIONS = [
    ("自动选择（auto）", "auto"),
    ("CPU：兼容性最好", "CPU"),
    ("NVIDIA GPU（CUDA）", "CUDA"),
    ("Apple GPU（MPS）", "MPS"),
    ("AMD GPU（ROCM）", "ROCM"),
]

BACKEND_OPTIONS = [
    ("自动选择（auto）", "auto"),
    ("OpenVINO：常适合 CPU", "openvino"),
    ("ONNX Runtime：兼容性好", "onnxruntime"),
    ("OpenCV 后端", "opencv"),
]

SAVE_VIDEO_OPTIONS = [
    ("保存为视频（to_video）", "to_video"),
    ("保存为逐帧图片（to_images）", "to_images"),
    ("不保存叠加结果（none）", "none"),
]

TRACKING_OPTIONS = [
    ("Sports2D 跟踪：推荐默认（sports2d）", "sports2d"),
    ("不跟踪（none）", "none"),
    ("DeepSORT：拥挤场景更稳但更慢（deepsort）", "deepsort"),
]

CALIBRATION_TYPE_OPTIONS = [
    ("转换已有校准文件（convert）", "convert"),
    ("从素材计算校准（calculate）", "calculate"),
]

CONVERT_FROM_OPTIONS = [
    ("Qualisys", "qualisys"),
    ("Caliscope", "caliscope"),
    ("OptiTrack", "optitrack"),
    ("Vicon", "vicon"),
    ("OpenCap", "opencap"),
    ("EasyMocap", "easymocap"),
    ("bioCV", "biocv"),
    ("Anipose", "anipose"),
    ("FreeMoCap", "freemocap"),
]

EXTRINSICS_OPTIONS = [
    ("场景已知点：推荐（scene）", "scene"),
    ("地面棋盘格（board）", "board"),
]

INTERPOLATION_OPTIONS = [
    ("线性：推荐默认（linear）", "linear"),
    ("一阶样条（slinear）", "slinear"),
    ("二次插值（quadratic）", "quadratic"),
    ("三次插值（cubic）", "cubic"),
    ("不插值（none）", "none"),
]

FILTER_TYPE_OPTIONS = [
    ("Butterworth：生物力学常用（butterworth）", "butterworth"),
    ("Kalman：适合实时估计（kalman）", "kalman"),
    ("One Euro：快速自适应（one_euro）", "one_euro"),
    ("GCV 样条：自动平滑（gcv_spline）", "gcv_spline"),
    ("Gaussian：高斯平滑（gaussian）", "gaussian"),
    ("LOESS：局部回归（LOESS）", "LOESS"),
    ("Median：中值滤波（median）", "median"),
    ("速度 Butterworth（butterworth_on_speed）", "butterworth_on_speed"),
]

TWO_D_SYNC_STAGES = ("poseEstimation", "synchronization")
CALIBRATION_STAGES = ("calibration",)
FULL_3D_REPORT_STAGES = (
    "poseEstimation",
    "synchronization",
    "personAssociation",
    "triangulation",
    "filtering",
    "markerAugmentation",
    "kinematics",
)


class Pose2SimMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Pose2Sim 图形界面")
        self.resize(1180, 760)
        self.workspace = ensure_app_workspace()
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
        self.tabs.addTab(self._build_wizard_tab(), "向导")
        self.tabs.addTab(self._build_project_tab(), "项目")
        self.tabs.addTab(self._build_parameters_tab(), "参数")
        self.tabs.addTab(self._build_pipeline_tab(), "流程/高级")
        self.tabs.addTab(self._build_reports_tab(), "报告")
        self.tabs.addTab(self._build_help_tab(), "使用说明")
        layout.addWidget(self.tabs, 1)

        self.setCentralWidget(root)
        self._set_project_dependent_enabled(False)
        self.refresh_workflow_status()

    def _build_wizard_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(12)

        dashboard_group = QGroupBox("项目状态仪表盘")
        dashboard_layout = QGridLayout(dashboard_group)
        self.dashboard_labels: dict[str, QLabel] = {}
        dashboard_items = [
            ("project", "项目"),
            ("videos", "正式动作视频"),
            ("calibration_material", "校准素材"),
            ("calibration_toml", "标定文件"),
            ("pose_sync", "2D/同步结果"),
            ("three_d", "3D 结果"),
            ("reports", "报告数据"),
            ("next_step", "推荐下一步"),
        ]
        for index, (key, label_text) in enumerate(dashboard_items):
            title = QLabel(label_text)
            title.setObjectName("DashboardTitle")
            value = QLabel("未载入")
            value.setObjectName("DashboardValue")
            value.setWordWrap(True)
            self.dashboard_labels[key] = value
            row = index // 2
            col = (index % 2) * 2
            dashboard_layout.addWidget(title, row, col)
            dashboard_layout.addWidget(value, row, col + 1)
        dashboard_layout.setColumnStretch(1, 1)
        dashboard_layout.setColumnStretch(3, 1)
        content_layout.addWidget(dashboard_group)

        quick_group = QGroupBox("推荐操作")
        quick_layout = QGridLayout(quick_group)
        choose_project_btn = QPushButton(self._icon(QStyle.SP_DirOpenIcon), "选择/新建项目")
        choose_project_btn.clicked.connect(self.choose_project)
        import_videos_btn = QPushButton(self._icon(QStyle.SP_DialogOpenButton), "导入正式动作视频")
        import_videos_btn.clicked.connect(self.import_recorded_videos)
        self.create_calibration_folders_btn = QPushButton(self._icon(QStyle.SP_FileDialogNewFolder), "创建校准文件夹")
        self.create_calibration_folders_btn.clicked.connect(self.create_calibration_folders_from_videos)
        open_calib_btn = QPushButton(self._icon(QStyle.SP_DirOpenIcon), "打开 calibration")
        open_calib_btn.clicked.connect(self.open_calibration_folder)
        refresh_status_btn = QPushButton(self._icon(QStyle.SP_BrowserReload), "刷新状态")
        refresh_status_btn.clicked.connect(self.refresh_workflow_status)
        quick_layout.addWidget(choose_project_btn, 0, 0)
        quick_layout.addWidget(import_videos_btn, 0, 1)
        quick_layout.addWidget(self.create_calibration_folders_btn, 0, 2)
        quick_layout.addWidget(open_calib_btn, 0, 3)
        quick_layout.addWidget(refresh_status_btn, 0, 4)
        quick_layout.setColumnStretch(4, 1)
        content_layout.addWidget(quick_group)

        capture_group = QGroupBox("采集说明（普通手机/Redmi 推荐流程）")
        capture_layout = QVBoxLayout(capture_group)
        capture_text = QLabel(
            "1. 固定两台手机的位置、分辨率、帧率和横竖屏；锁定焦距/曝光，正式动作前后不要移动手机。\n"
            "2. 每台手机先单独拍内参素材：棋盘格或 Charuco 板覆盖画面不同位置和角度。\n"
            "3. 手机固定后拍外参素材：推荐 scene 方法，在场地布置 10 个以上分散且可测量的 3D 点，校准时按提示点击这些点。\n"
            "4. 不移动手机，录正式动作视频；没有硬件同步时，在动作开始加入明显同步事件，例如跳一下、快速抬手、拍手或闪光。\n"
            "5. 相机一旦移动，外参必须重做；分辨率、焦距或镜头明显变化时，内参也应重做。"
        )
        capture_text.setWordWrap(True)
        capture_text.setObjectName("HelpText")
        capture_layout.addWidget(capture_text)
        content_layout.addWidget(capture_group)

        calibration_group = QGroupBox("校准向导")
        calibration_layout = QVBoxLayout(calibration_group)
        route_form = QFormLayout()
        self.calibration_route = self._combo(
            [
                ("已有标定文件：把 Calib.toml 放入 calibration/ 后跳过校准", "existing"),
                ("从素材计算标定：棋盘格内参 + 场景点/棋盘格外参（推荐）", "calculate"),
                ("仅做 2D/同步检查：不进行 3D/OpenSim", "two_d_only"),
            ]
        )
        self.wizard_calibration_type = self._combo(CALIBRATION_TYPE_OPTIONS)
        self.wizard_convert_from = self._combo(CONVERT_FROM_OPTIONS)
        self.wizard_intrinsics_extension = QLineEdit("mp4")
        self.wizard_extrinsics_extension = QLineEdit("mp4")
        self.wizard_intrinsics_corners = QLineEdit("8, 5")
        self.wizard_intrinsics_square = QDoubleSpinBox()
        self.wizard_intrinsics_square.setRange(1.0, 500.0)
        self.wizard_intrinsics_square.setDecimals(1)
        self.wizard_intrinsics_square.setSingleStep(1.0)
        self.wizard_intrinsics_square.setSuffix(" mm")
        self.wizard_intrinsics_square.setValue(25.0)
        self.wizard_extrinsics_method = self._combo(EXTRINSICS_OPTIONS)
        route_form.addRow("校准路径", self._with_info(self.calibration_route, "wizard_calibration_route"))
        route_form.addRow("Pose2Sim 校准方式", self._with_info(self.wizard_calibration_type, "calibration_type"))
        route_form.addRow("已有标定来源", self._with_info(self.wizard_convert_from, "convert_from"))
        route_form.addRow("内参素材扩展名", self._with_info(self.wizard_intrinsics_extension, "intrinsics_extension"))
        route_form.addRow("外参素材扩展名", self._with_info(self.wizard_extrinsics_extension, "wizard_extrinsics_extension"))
        route_form.addRow("棋盘格内角点数", self._with_info(self.wizard_intrinsics_corners, "wizard_intrinsics_corners"))
        route_form.addRow("棋盘格方格边长", self._with_info(self.wizard_intrinsics_square, "wizard_intrinsics_square"))
        route_form.addRow("外参方法", self._with_info(self.wizard_extrinsics_method, "extrinsics_method"))
        calibration_layout.addLayout(route_form)

        scene_header = QHBoxLayout()
        scene_label = QLabel("scene 外参 3D 场景点（单位建议用米，X/Y/Z 必须与实际测量坐标一致）")
        scene_label.setWordWrap(True)
        scene_label.setObjectName("HelpText")
        scene_header.addWidget(scene_label, 1)
        add_point_btn = QPushButton("添加点")
        add_point_btn.clicked.connect(self.add_scene_point_row)
        remove_point_btn = QPushButton("删除选中点")
        remove_point_btn.clicked.connect(self.remove_selected_scene_point_rows)
        import_points_btn = QPushButton("导入 CSV")
        import_points_btn.clicked.connect(self.import_scene_points_csv)
        export_points_btn = QPushButton("导出 CSV")
        export_points_btn.clicked.connect(self.export_scene_points_csv)
        scene_header.addWidget(add_point_btn)
        scene_header.addWidget(remove_point_btn)
        scene_header.addWidget(import_points_btn)
        scene_header.addWidget(export_points_btn)
        calibration_layout.addLayout(scene_header)

        self.scene_points_table = QTableWidget(10, 4)
        self.scene_points_table.setHorizontalHeaderLabels(["点名", "X", "Y", "Z"])
        self.scene_points_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for row in range(10):
            self.scene_points_table.setItem(row, 0, QTableWidgetItem(f"P{row + 1:02d}"))
            for col in range(1, 4):
                self.scene_points_table.setItem(row, col, QTableWidgetItem(""))
        calibration_layout.addWidget(self.scene_points_table)

        calibration_button_row = QHBoxLayout()
        save_calibration_btn = QPushButton(self._icon(QStyle.SP_DialogSaveButton), "保存校准设置到 Config.toml")
        save_calibration_btn.clicked.connect(self.save_calibration_wizard_settings)
        calibration_button_row.addStretch(1)
        calibration_button_row.addWidget(save_calibration_btn)
        calibration_layout.addLayout(calibration_button_row)
        content_layout.addWidget(calibration_group)

        run_group = QGroupBox("运行")
        run_layout = QVBoxLayout(run_group)
        self.workflow_warning = QLabel("载入项目后会显示当前能运行的步骤。")
        self.workflow_warning.setObjectName("WarningText")
        self.workflow_warning.setWordWrap(True)
        run_layout.addWidget(self.workflow_warning)
        run_button_row = QHBoxLayout()
        self.run_2d_sync_btn = QPushButton(self._icon(QStyle.SP_MediaPlay), "只检查 2D/同步")
        self.run_2d_sync_btn.clicked.connect(lambda: self.run_stage_preset(TWO_D_SYNC_STAGES))
        self.run_calibration_btn = QPushButton(self._icon(QStyle.SP_MediaPlay), "运行校准")
        self.run_calibration_btn.clicked.connect(lambda: self.run_stage_preset(CALIBRATION_STAGES))
        self.run_full_3d_btn = QPushButton(self._icon(QStyle.SP_MediaPlay), "运行完整 3D + 报告")
        self.run_full_3d_btn.setObjectName("PrimaryButton")
        self.run_full_3d_btn.clicked.connect(lambda: self.run_stage_preset(FULL_3D_REPORT_STAGES))
        run_button_row.addWidget(self.run_2d_sync_btn)
        run_button_row.addWidget(self.run_calibration_btn)
        run_button_row.addWidget(self.run_full_3d_btn)
        run_button_row.addStretch(1)
        run_layout.addLayout(run_button_row)
        content_layout.addWidget(run_group)

        content_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return page

    def _build_project_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        group = QGroupBox("项目文件夹")
        grid = QGridLayout(group)
        self.project_edit = QLineEdit()
        self.project_edit.setPlaceholderText("请选择或新建 Pose2Sim 分析项目文件夹")

        browse_btn = QPushButton(self._icon(QStyle.SP_DirOpenIcon), "选择/新建项目")
        browse_btn.setToolTip("选择一个项目文件夹；若缺少 Config.toml，GUI 会自动创建默认配置")
        browse_btn.clicked.connect(self.choose_project)

        create_btn = QPushButton(self._icon(QStyle.SP_FileDialogNewFolder), "新建分析项目")
        create_btn.setToolTip("选择或创建一个文件夹，GUI 会自动复制默认 Config.toml 并创建标准文件夹")
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

        workspace_group = QGroupBox("软件工作目录")
        workspace_layout = QGridLayout(workspace_group)
        workspace_text = QLabel(
            f"软件目录：{APP_ROOT}\n"
            f"输入暂存：{INPUT_DIR}\n"
            f"结果与报告：{OUTPUT_DIR}\\pose2sim_results\n"
            "新建项目默认建议直接放在 output/pose2sim_results；报告会放在项目结果文件夹的 reports 子目录。"
        )
        workspace_text.setWordWrap(True)
        workspace_text.setObjectName("HelpText")
        open_input_btn = QPushButton(self._icon(QStyle.SP_DirOpenIcon), "打开 input")
        open_input_btn.clicked.connect(lambda: self.open_folder(INPUT_DIR))
        open_output_btn = QPushButton(self._icon(QStyle.SP_DirOpenIcon), "打开 output")
        open_output_btn.clicked.connect(lambda: self.open_folder(OUTPUT_DIR))
        workspace_layout.addWidget(workspace_text, 0, 0, 2, 1)
        workspace_layout.addWidget(open_input_btn, 0, 1)
        workspace_layout.addWidget(open_output_btn, 1, 1)
        workspace_layout.setColumnStretch(0, 1)
        layout.addWidget(workspace_group)

        self.status_text = QPlainTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setPlaceholderText("项目检查结果会显示在这里。")
        layout.addWidget(self.status_text, 1)

        note = QLabel(
            "推荐流程：选择或新建项目文件夹 → GUI 自动准备 Config.toml 和标准文件夹 → 导入录制视频/校准素材 → 调整参数 → 运行流程。"
            "Pose2Sim 实际读取项目内的 videos/、calibration/ 和 Config.toml；"
            "Pose2Sim 会自动生成 pose/、pose-sync/、pose-associated/、pose-3d/、kinematics/；"
            "本 GUI 会把这些结果集中到 output/pose2sim_results/<项目名>/，报告放在其中的 reports/ 子目录。"
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

    def _combo(self, values: tuple[str, ...] | list[str] | list[tuple[str, str]]) -> QComboBox:
        combo = QComboBox()
        for item in values:
            if isinstance(item, tuple):
                combo.addItem(item[0], item[1])
            else:
                combo.addItem(str(item), item)
        return combo

    def _combo_value(self, combo: QComboBox) -> str:
        data = combo.currentData()
        return str(data if data is not None else combo.currentText())

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
        self.pose_model = self._combo(POSE_MODEL_OPTIONS)
        self.pose_mode = self._combo(POSE_MODE_OPTIONS)
        self.device = self._combo(DEVICE_OPTIONS)
        self.backend = self._combo(BACKEND_OPTIONS)
        self.display_detection = QCheckBox("启用")
        self.overwrite_pose = QCheckBox("启用")
        self.save_video = self._combo(SAVE_VIDEO_OPTIONS)
        self.tracking_mode = self._combo(TRACKING_OPTIONS)
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
        self.calibration_type = self._combo(CALIBRATION_TYPE_OPTIONS)
        self.convert_from = self._combo(CONVERT_FROM_OPTIONS)
        self.intrinsics_extension = QLineEdit()
        self.extrinsics_method = self._combo(EXTRINSICS_OPTIONS)
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
        self.interpolation = self._combo(INTERPOLATION_OPTIONS)
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
        self.filter_type = self._combo(FILTER_TYPE_OPTIONS)
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
        self.toml_editor.setObjectName("TomlEditor")
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

        recommended_group = QGroupBox("推荐运行入口")
        recommended_layout = QVBoxLayout(recommended_group)
        self.pipeline_prereq_label = QLabel("载入项目后会根据视频、校准和结果状态启用对应按钮。")
        self.pipeline_prereq_label.setObjectName("WarningText")
        self.pipeline_prereq_label.setWordWrap(True)
        recommended_layout.addWidget(self.pipeline_prereq_label)
        preset_row = QHBoxLayout()
        self.pipeline_2d_sync_btn = QPushButton(self._icon(QStyle.SP_MediaPlay), "只检查 2D/同步")
        self.pipeline_2d_sync_btn.clicked.connect(lambda: self.run_stage_preset(TWO_D_SYNC_STAGES))
        self.pipeline_calibration_btn = QPushButton(self._icon(QStyle.SP_MediaPlay), "运行校准")
        self.pipeline_calibration_btn.clicked.connect(lambda: self.run_stage_preset(CALIBRATION_STAGES))
        self.pipeline_full_3d_btn = QPushButton(self._icon(QStyle.SP_MediaPlay), "运行完整 3D + 报告")
        self.pipeline_full_3d_btn.clicked.connect(lambda: self.run_stage_preset(FULL_3D_REPORT_STAGES))
        preset_row.addWidget(self.pipeline_2d_sync_btn)
        preset_row.addWidget(self.pipeline_calibration_btn)
        preset_row.addWidget(self.pipeline_full_3d_btn)
        preset_row.addStretch(1)
        recommended_layout.addLayout(preset_row)
        layout.addWidget(recommended_group)

        stage_group = QGroupBox("高级手动步骤（有风险）")
        stage_container = QVBoxLayout(stage_group)
        advanced_note = QLabel(
            "高级模式允许手动勾选 Pose2Sim 阶段，适合调试和复用中间结果。"
            "如果没有 calibration/*.toml，请不要运行人物匹配、三维重建、滤波、增强或运动学。"
        )
        advanced_note.setObjectName("DangerText")
        advanced_note.setWordWrap(True)
        stage_container.addWidget(advanced_note)
        stage_layout = QGridLayout()
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
        stage_container.addLayout(stage_layout)
        layout.addWidget(stage_group)

        button_row = QHBoxLayout()
        self.run_btn = QPushButton(self._icon(QStyle.SP_MediaPlay), "高级：运行勾选步骤")
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

        form_group = QGroupBox("报告数据（自动生成）")
        form = QFormLayout(form_group)
        self.mot_combo = QComboBox()
        self.mot_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.video_combo = QComboBox()
        self.video_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.video_combo.setToolTip("报告会自动使用列表中的全部视频。优先使用 pose 文件夹下的处理后 *_pose.mp4。")
        self._add_info_row(form, "OpenSim .mot 文件", self.mot_combo, "mot_file")
        self._add_info_row(form, "报告视频（自动全部使用）", self.video_combo, "report_video")
        layout.addWidget(form_group)

        button_row = QHBoxLayout()
        refresh_btn = QPushButton(self._icon(QStyle.SP_BrowserReload), "刷新文件")
        refresh_btn.clicked.connect(self.refresh_report_files)
        excel_btn = QPushButton(self._icon(QStyle.SP_DialogSaveButton), "重新生成 Excel")
        excel_btn.clicked.connect(self.generate_excel_report)
        html_btn = QPushButton(self._icon(QStyle.SP_FileDialogContentsView), "重新生成 HTML")
        html_btn.clicked.connect(self.generate_html_report)
        both_btn = QPushButton(self._icon(QStyle.SP_DialogApplyButton), "全部重新生成")
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
        viewer.setObjectName("ManualViewer")
        viewer.setReadOnly(True)
        viewer.setMarkdown(MANUAL_TEXT)
        layout.addWidget(viewer, 1)
        return page

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f4f7fb;
                color: #172033;
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
                font-size: 13px;
            }
            QLabel {
                background: transparent;
                color: #172033;
            }
            QMenuBar {
                background: #ffffff;
                border-bottom: 1px solid #d8e0ea;
            }
            QMenuBar::item:selected, QMenu::item:selected {
                background: #e8f1ff;
                color: #174ea6;
            }
            QTabWidget::pane {
                border: 1px solid #d8e0ea;
                border-radius: 8px;
                background: #ffffff;
                top: -1px;
            }
            QTabBar::tab {
                background: #eaf0f7;
                border: 1px solid #d8e0ea;
                border-bottom: none;
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
                padding: 8px 14px;
                margin-right: 3px;
                color: #475569;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #0f3d75;
                font-weight: 600;
            }
            QGroupBox {
                border: 1px solid #d8e0ea;
                border-radius: 8px;
                background: #ffffff;
                margin-top: 18px;
                padding: 18px 12px 12px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                top: 7px;
                padding: 0 6px;
                background: #ffffff;
                color: #1e293b;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                min-height: 30px;
                border: 1px solid #c8d2df;
                border-radius: 6px;
                background: #ffffff;
                padding: 4px 7px;
                selection-background-color: #1f6feb;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
            QPlainTextEdit:focus, QTextEdit:focus {
                border: 1px solid #1f6feb;
            }
            QPushButton {
                border: 1px solid #b7c4d3;
                border-radius: 6px;
                background: #ffffff;
                padding: 7px 10px;
                color: #172033;
                min-height: 28px;
            }
            QPushButton:hover {
                border-color: #1f6feb;
                background: #e8f1ff;
                color: #0f3d75;
            }
            QPushButton:pressed {
                background: #d8e8ff;
            }
            QPushButton:disabled, QWidget:disabled {
                color: #8b97a8;
                background: #edf1f6;
            }
            QCheckBox {
                spacing: 8px;
                background: transparent;
            }
            QPlainTextEdit, QTextEdit {
                border: 1px solid #d8e0ea;
                border-radius: 8px;
                background: #ffffff;
                color: #172033;
                padding: 8px;
            }
            QTableWidget {
                border: 1px solid #d8e0ea;
                border-radius: 8px;
                background: #ffffff;
                gridline-color: #e2e8f0;
                selection-background-color: #dbeafe;
            }
            QHeaderView::section {
                background: #eef3f8;
                color: #1e293b;
                border: none;
                border-right: 1px solid #d8e0ea;
                border-bottom: 1px solid #d8e0ea;
                padding: 6px;
                font-weight: 600;
            }
            QPlainTextEdit, #TomlEditor {
                font-family: Consolas, "Courier New", monospace;
                font-size: 12px;
            }
            #ManualViewer {
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
                font-size: 13px;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                background: #edf2f7;
                border: none;
                margin: 0;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: #b8c5d6;
                border-radius: 4px;
                min-height: 24px;
                min-width: 24px;
            }
            #AppTitle {
                font-size: 23px;
                font-weight: 700;
                color: #10223f;
            }
            #ProjectLabel, #HelpText {
                color: #5b677a;
            }
            #DashboardTitle {
                color: #475569;
                font-weight: 600;
            }
            #DashboardValue {
                min-height: 32px;
            }
            #WarningText {
                color: #8a4b00;
                background: #fff7e6;
                border: 1px solid #f2d091;
                border-radius: 6px;
                padding: 8px;
            }
            #DangerText {
                color: #9a1b1b;
                background: #fdecec;
                border: 1px solid #f3b5b5;
                border-radius: 6px;
                padding: 8px;
                font-weight: 500;
            }
            QPushButton#PrimaryButton {
                background: #1f6feb;
                border-color: #1f6feb;
                color: #ffffff;
                font-weight: 600;
            }
            QPushButton#PrimaryButton:hover {
                background: #1557bf;
                border-color: #1557bf;
                color: #ffffff;
            }
            QToolTip {
                background: #172033;
                color: #ffffff;
                border: 1px solid #172033;
                padding: 6px;
                border-radius: 4px;
            }
            """
        )

    def _set_project_dependent_enabled(self, enabled: bool) -> None:
        for widget in (
            self.tabs.widget(2),
            self.tabs.widget(3),
            self.tabs.widget(4),
        ):
            widget.setEnabled(enabled)
        if hasattr(self, "create_calibration_folders_btn"):
            self.create_calibration_folders_btn.setEnabled(enabled)

    def open_folder(self, folder: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def choose_project(self) -> None:
        start_dir = str(self.project_dir or RESULTS_DIR)
        folder = QFileDialog.getExistingDirectory(self, "选择或新建 Pose2Sim 分析项目文件夹", start_dir)
        if folder:
            self.load_project(Path(folder), create_if_missing=True)

    def create_project_from_demo(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择新 Pose2Sim 项目文件夹", str(RESULTS_DIR))
        if not folder:
            return
        try:
            path, created = ensure_project_config(Path(folder))
            self.load_project(path.parent)
            message = "已创建默认配置" if created else "已找到现有配置，未覆盖"
            self.status_text.appendPlainText(f"{message}：{path}")
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
            self.refresh_workflow_status()
        except Exception as exc:
            self._error("无法创建标准文件夹", exc)

    def create_calibration_folders_from_videos(self) -> None:
        if not self.project_dir:
            self._message("尚未载入项目", "请先选择或新建一个项目。")
            return
        try:
            camera_names = camera_names_from_videos(self.project_dir)
            folders = ensure_calibration_folders(self.project_dir, camera_names)
            self.status_text.appendPlainText("已创建/确认校准文件夹：")
            for folder in folders:
                self.status_text.appendPlainText(f"  {folder}")
            self.refresh_workflow_status()
            self.open_folder(self.project_dir / "calibration")
        except Exception as exc:
            self._error("无法创建校准文件夹", exc)

    def open_calibration_folder(self) -> None:
        if not self.project_dir:
            self._message("尚未载入项目", "请先选择或新建一个项目。")
            return
        ensure_standard_project_folders(self.project_dir)
        self.open_folder(self.project_dir / "calibration")

    def add_scene_point_row(self) -> None:
        row = self.scene_points_table.rowCount()
        self.scene_points_table.insertRow(row)
        self.scene_points_table.setItem(row, 0, QTableWidgetItem(f"P{row + 1:02d}"))
        for col in range(1, 4):
            self.scene_points_table.setItem(row, col, QTableWidgetItem(""))

    def remove_selected_scene_point_rows(self) -> None:
        selected_rows = sorted({index.row() for index in self.scene_points_table.selectedIndexes()}, reverse=True)
        for row in selected_rows:
            self.scene_points_table.removeRow(row)

    def _scene_points_from_table(self) -> list[dict[str, float | str]]:
        rows: list[dict[str, float | str]] = []
        for row in range(self.scene_points_table.rowCount()):
            values: list[str] = []
            for col in range(4):
                item = self.scene_points_table.item(row, col)
                values.append(item.text().strip() if item else "")
            if not any(values):
                continue
            if values[0] and not any(values[1:]):
                continue
            if not all(values):
                raise ValueError(f"第 {row + 1} 行场景点不完整，请填写点名、X、Y、Z。")
            rows.append(
                {
                    "name": values[0],
                    "x": float(values[1]),
                    "y": float(values[2]),
                    "z": float(values[3]),
                }
            )
        return rows

    def _load_scene_points_table(self, rows: list[dict[str, float | str]]) -> None:
        self.scene_points_table.setRowCount(max(len(rows), 1))
        for row, data in enumerate(rows):
            self.scene_points_table.setItem(row, 0, QTableWidgetItem(str(data.get("name", ""))))
            self.scene_points_table.setItem(row, 1, QTableWidgetItem(str(data.get("x", ""))))
            self.scene_points_table.setItem(row, 2, QTableWidgetItem(str(data.get("y", ""))))
            self.scene_points_table.setItem(row, 3, QTableWidgetItem(str(data.get("z", ""))))

    def import_scene_points_csv(self) -> None:
        start_dir = str(self.project_dir or APP_ROOT)
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "导入场景点 CSV",
            start_dir,
            "CSV 文件 (*.csv);;所有文件 (*.*)",
        )
        if not file_name:
            return
        try:
            rows = read_scene_points_csv(Path(file_name))
            self._load_scene_points_table(rows)
            self._message("导入完成", f"已导入 {len(rows)} 个场景点。")
        except Exception as exc:
            self._error("无法导入场景点 CSV", exc)

    def export_scene_points_csv(self) -> None:
        start_dir = str((self.project_dir / "calibration") if self.project_dir else APP_ROOT)
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "导出场景点 CSV",
            str(Path(start_dir) / "scene_points.csv"),
            "CSV 文件 (*.csv);;所有文件 (*.*)",
        )
        if not file_name:
            return
        try:
            rows = self._scene_points_from_table()
            write_scene_points_csv(Path(file_name), rows)
            self._message("导出完成", f"已导出 {len(rows)} 个场景点。")
        except Exception as exc:
            self._error("无法导出场景点 CSV", exc)

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
            str(RAW_VIDEO_DIR if RAW_VIDEO_DIR.exists() else project_dir),
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
            self.refresh_workflow_status()
        except Exception as exc:
            self._error("无法导入视频", exc)

    def open_installed_demo(self) -> None:
        try:
            self.load_project(demo_config_path().parent)
        except Exception as exc:
            self._error("无法打开内置示例", exc)

    def load_project(self, project_dir: Path, create_if_missing: bool = False) -> None:
        project_dir = Path(project_dir).resolve()
        try:
            if create_if_missing:
                config_path, created = ensure_project_config(project_dir)
                if created:
                    self.status_text.appendPlainText(f"已自动创建默认 Config.toml：{config_path}")
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
            self.refresh_workflow_status()
            return
        status = project_status(Path(project_text))
        self.status_text.setPlainText("\n".join(status.summary_lines()))
        self.refresh_workflow_status()

    def _set_dashboard_value(self, key: str, text: str, state: str = "neutral") -> None:
        label = self.dashboard_labels.get(key)
        if label is None:
            return
        label.setText(text)
        styles = {
            "good": "background:#e9f7ef;color:#17633a;border:1px solid #b7e2c7;border-radius:6px;padding:6px;",
            "warn": "background:#fff7e6;color:#8a4b00;border:1px solid #f2d091;border-radius:6px;padding:6px;",
            "bad": "background:#fdecec;color:#9a1b1b;border:1px solid #f3b5b5;border-radius:6px;padding:6px;",
            "neutral": "background:#f5f7fb;color:#334155;border:1px solid #d8e0ea;border-radius:6px;padding:6px;",
        }
        label.setStyleSheet(styles.get(state, styles["neutral"]))

    def _set_run_button_states(self, status_can_run: dict[str, bool]) -> None:
        pairs = [
            ("2d", ("run_2d_sync_btn", "pipeline_2d_sync_btn")),
            ("calibration", ("run_calibration_btn", "pipeline_calibration_btn")),
            ("full", ("run_full_3d_btn", "pipeline_full_3d_btn")),
        ]
        running = self.process is not None
        for key, names in pairs:
            enabled = status_can_run.get(key, False) and not running
            for name in names:
                if hasattr(self, name):
                    getattr(self, name).setEnabled(enabled)
        if hasattr(self, "run_btn"):
            self.run_btn.setEnabled(bool(self.project_dir) and not running)
        if hasattr(self, "stop_btn"):
            self.stop_btn.setEnabled(running)

    def refresh_workflow_status(self) -> None:
        if not hasattr(self, "dashboard_labels"):
            return
        if not self.project_dir:
            self._set_dashboard_value("project", "未载入项目", "bad")
            self._set_dashboard_value("videos", "等待导入正式动作视频", "neutral")
            self._set_dashboard_value("calibration_material", "等待校准素材", "neutral")
            self._set_dashboard_value("calibration_toml", "缺少 calibration/*.toml", "bad")
            self._set_dashboard_value("pose_sync", "未运行", "neutral")
            self._set_dashboard_value("three_d", "未运行", "neutral")
            self._set_dashboard_value("reports", "未生成", "neutral")
            self._set_dashboard_value("next_step", "请选择或新建 Pose2Sim 项目。", "warn")
            self.workflow_warning.setText("请选择或新建项目；普通用户不需要手写 Config.toml。")
            if hasattr(self, "pipeline_prereq_label"):
                self.pipeline_prereq_label.setText(self.workflow_warning.text())
            self._set_run_button_states({"2d": False, "calibration": False, "full": False})
            return

        status = project_workflow_status(self.project_dir)
        camera_text = ", ".join(status.camera_names) if status.camera_names else "未从视频名识别"
        calib_names = ", ".join(file.name for file in status.calibration_toml_files) or "无"
        materials = status.calibration_materials

        self._set_dashboard_value("project", str(status.project_dir), "good" if status.has_config else "bad")
        self._set_dashboard_value(
            "videos",
            f"{status.video_count} 个视频；相机名：{camera_text}",
            "good" if status.has_videos else "bad",
        )
        self._set_dashboard_value(
            "calibration_material",
            (
                f"内参素材 {materials.intrinsics_file_count} 个；"
                f"外参素材 {materials.extrinsics_file_count} 个；"
                f"校准输入文件 {materials.calibration_input_file_count} 个"
            ),
            "good" if materials.has_any_calibration_input else "warn",
        )
        self._set_dashboard_value(
            "calibration_toml",
            f"{len(status.calibration_toml_files)} 个标定文件：{calib_names}",
            "good" if status.has_calibration_toml else "bad",
        )
        self._set_dashboard_value(
            "pose_sync",
            f"2D JSON {status.pose_json_count} 个；同步 JSON {status.sync_json_count} 个",
            "good" if status.has_sync_results else ("warn" if status.has_pose_results else "neutral"),
        )
        self._set_dashboard_value(
            "three_d",
            f"三维 .trc {len(status.trc_files)} 个",
            "good" if status.has_3d_results else "neutral",
        )
        self._set_dashboard_value(
            "reports",
            f"OpenSim .mot {len(status.mot_files)} 个",
            "good" if status.has_reports else "neutral",
        )
        self._set_dashboard_value("next_step", status.recommended_next_step, "warn")

        if not status.has_calibration_toml:
            warning = (
                "完整 3D/OpenSim 已禁用：项目 calibration/ 中没有 .toml 标定文件。"
                "请先导入已有 Calib.toml，或拍摄内参/外参素材后运行校准。"
            )
        elif not status.has_videos:
            warning = "请先导入正式动作视频。"
        else:
            warning = "已满足完整 3D/OpenSim 的基本前置条件；仍建议先运行 2D/同步检查。"
        self.workflow_warning.setText(warning)
        if hasattr(self, "pipeline_prereq_label"):
            self.pipeline_prereq_label.setText(warning)

        self._set_run_button_states(
            {
                "2d": status.can_run_2d_sync,
                "calibration": status.can_run_calibration,
                "full": status.can_run_full_3d,
            }
        )

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
        self.populate_calibration_wizard_controls()

    def populate_calibration_wizard_controls(self) -> None:
        if self.config is None or not hasattr(self, "wizard_calibration_type"):
            return
        cfg = self.config
        calibration_type = get_nested(cfg, ["calibration", "calibration_type"], "convert")
        self._set_combo_value(self.wizard_calibration_type, calibration_type)
        self._set_combo_value(self.wizard_convert_from, get_nested(cfg, ["calibration", "convert", "convert_from"], "qualisys"))
        self.wizard_intrinsics_extension.setText(
            str(get_nested(cfg, ["calibration", "calculate", "intrinsics", "intrinsics_extension"], "mp4"))
        )
        self.wizard_extrinsics_extension.setText(
            str(get_nested(cfg, ["calibration", "calculate", "extrinsics", "extrinsics_extension"], "mp4"))
        )
        corners = get_nested(cfg, ["calibration", "calculate", "intrinsics", "intrinsics_corners_nb"], [8, 5])
        if isinstance(corners, (list, tuple)) and len(corners) >= 2:
            self.wizard_intrinsics_corners.setText(f"{corners[0]}, {corners[1]}")
        else:
            self.wizard_intrinsics_corners.setText(str(corners))
        self.wizard_intrinsics_square.setValue(
            float(get_nested(cfg, ["calibration", "calculate", "intrinsics", "intrinsics_square_size"], 25.0))
        )
        self._set_combo_value(
            self.wizard_extrinsics_method,
            get_nested(cfg, ["calibration", "calculate", "extrinsics", "extrinsics_method"], "scene"),
        )
        object_points = get_nested(cfg, ["calibration", "calculate", "extrinsics", "scene", "object_coords_3d"], [])
        if isinstance(object_points, list) and object_points:
            rows: list[dict[str, float | str]] = []
            for index, point in enumerate(object_points):
                if isinstance(point, (list, tuple)) and len(point) >= 3:
                    rows.append({"name": f"P{index + 1:02d}", "x": point[0], "y": point[1], "z": point[2]})
            if rows:
                self._load_scene_points_table(rows)

    def _set_combo_value(self, combo: QComboBox, value: Any) -> None:
        text = str(value)
        index = combo.findData(text)
        if index < 0:
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

        set_nested(cfg, ["pose", "pose_model"], self._combo_value(self.pose_model))
        set_nested(cfg, ["pose", "mode"], self._combo_value(self.pose_mode))
        set_nested(cfg, ["pose", "device"], self._combo_value(self.device))
        set_nested(cfg, ["pose", "backend"], self._combo_value(self.backend))
        set_nested(cfg, ["pose", "det_frequency"], self.det_frequency.value())
        set_nested(cfg, ["pose", "average_likelihood_threshold_pose"], self.average_likelihood.value())
        set_nested(cfg, ["pose", "display_detection"], self.display_detection.isChecked())
        set_nested(cfg, ["pose", "overwrite_pose"], self.overwrite_pose.isChecked())
        set_nested(cfg, ["pose", "save_video"], self._combo_value(self.save_video))
        set_nested(cfg, ["pose", "tracking_mode"], self._combo_value(self.tracking_mode))

        set_nested(cfg, ["synchronization", "synchronization_gui"], self.synchronization_gui.isChecked())
        set_nested(cfg, ["synchronization", "display_sync_plots"], self.display_sync_plots.isChecked())
        set_nested(cfg, ["synchronization", "save_sync_plots"], self.save_sync_plots.isChecked())
        set_nested(cfg, ["calibration", "calibration_type"], self._combo_value(self.calibration_type))
        set_nested(cfg, ["calibration", "convert", "convert_from"], self._combo_value(self.convert_from))
        set_nested(cfg, ["calibration", "calculate", "intrinsics", "intrinsics_extension"], self.intrinsics_extension.text().strip() or "jpg")
        set_nested(cfg, ["calibration", "calculate", "extrinsics", "extrinsics_method"], self._combo_value(self.extrinsics_method))

        set_nested(cfg, ["personAssociation", "single_person", "tracked_keypoint"], self.tracked_keypoint.text().strip() or "Neck")
        set_nested(cfg, ["personAssociation", "single_person", "reproj_error_threshold_association"], self.reproj_assoc.value())
        set_nested(cfg, ["triangulation", "reproj_error_threshold_triangulation"], self.reproj_triangulation.value())
        set_nested(cfg, ["triangulation", "min_cameras_for_triangulation"], self.min_cameras.value())
        set_nested(cfg, ["triangulation", "interpolation"], self._combo_value(self.interpolation))

        set_nested(cfg, ["filtering", "reject_outliers"], self.reject_outliers.isChecked())
        set_nested(cfg, ["filtering", "filter"], self.filter_enabled.isChecked())
        set_nested(cfg, ["filtering", "type"], self._combo_value(self.filter_type))
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
            self.refresh_workflow_status()
            QMessageBox.information(self, "已保存", message)
        except Exception as exc:
            self._error("无法保存参数", exc)

    def _parse_intrinsics_corners(self) -> list[int]:
        text = self.wizard_intrinsics_corners.text().strip().lower().replace("x", ",")
        parts = [part.strip() for part in text.replace("，", ",").split(",") if part.strip()]
        if len(parts) != 2:
            raise ValueError("棋盘格内角点数必须填写为两个整数，例如 8, 5。")
        corners = [int(parts[0]), int(parts[1])]
        if corners[0] <= 0 or corners[1] <= 0:
            raise ValueError("棋盘格内角点数必须大于 0。")
        return corners

    def save_calibration_wizard_settings(self) -> None:
        if not self.project_dir or self.config is None:
            self._message("尚未载入项目", "请先选择或新建一个项目。")
            return
        try:
            cfg = self.config
            route = self._combo_value(self.calibration_route)
            calibration_type = self._combo_value(self.wizard_calibration_type)
            if route == "calculate":
                calibration_type = "calculate"

            set_nested(cfg, ["calibration", "calibration_type"], calibration_type)
            set_nested(cfg, ["calibration", "convert", "convert_from"], self._combo_value(self.wizard_convert_from))
            set_nested(
                cfg,
                ["calibration", "calculate", "intrinsics", "intrinsics_extension"],
                self.wizard_intrinsics_extension.text().strip() or "mp4",
            )
            set_nested(
                cfg,
                ["calibration", "calculate", "intrinsics", "intrinsics_corners_nb"],
                self._parse_intrinsics_corners(),
            )
            set_nested(
                cfg,
                ["calibration", "calculate", "intrinsics", "intrinsics_square_size"],
                self.wizard_intrinsics_square.value(),
            )
            set_nested(
                cfg,
                ["calibration", "calculate", "extrinsics", "extrinsics_method"],
                self._combo_value(self.wizard_extrinsics_method),
            )
            set_nested(
                cfg,
                ["calibration", "calculate", "extrinsics", "extrinsics_extension"],
                self.wizard_extrinsics_extension.text().strip() or "mp4",
            )

            scene_points = self._scene_points_from_table()
            if self._combo_value(self.wizard_extrinsics_method) == "scene":
                set_nested(
                    cfg,
                    ["calibration", "calculate", "extrinsics", "scene", "object_coords_3d"],
                    [[point["x"], point["y"], point["z"]] for point in scene_points] if scene_points else [],
                )

            warnings = apply_beginner_safety(cfg)
            save_config(self.project_dir, cfg)
            self.config = load_config(self.project_dir)
            self.populate_beginner_controls()
            self.toml_editor.setPlainText(load_config_text(self.project_dir))
            self.toml_status.setText("Config.toml 已保存")
            self.refresh_workflow_status()

            message = "校准设置已保存到 Config.toml。"
            if self._combo_value(self.wizard_extrinsics_method) == "scene" and len(scene_points) < 10:
                message += "\n\n提示：scene 外参建议至少 10 个分散且可测量的 3D 场景点。"
            if route == "existing":
                message += "\n\n如果已经有 Calib.toml，请把它放入项目的 calibration/ 文件夹，然后刷新状态。"
            elif route == "two_d_only":
                message += "\n\n当前选择为仅做 2D/同步检查；没有 Calib.toml 时不会运行完整 3D/OpenSim。"
            if warnings:
                message += "\n\n" + "\n".join(warnings)
            QMessageBox.information(self, "已保存", message)
        except Exception as exc:
            self._error("无法保存校准设置", exc)

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
            self.refresh_workflow_status()
            QMessageBox.information(self, "已保存", "Config.toml 已保存。")
        except Exception as exc:
            self._error("无法保存 TOML", exc)

    def run_stage_preset(self, stages: tuple[str, ...]) -> None:
        if not self.project_dir:
            self._message("尚未载入项目", "请先选择或新建一个项目。")
            return
        status = project_workflow_status(self.project_dir)
        if stages == TWO_D_SYNC_STAGES and not status.can_run_2d_sync:
            self._message("无法运行 2D/同步", "请先导入正式动作视频到 videos/。")
            return
        if stages == CALIBRATION_STAGES and not status.can_run_calibration:
            self._message(
                "无法运行校准",
                "请先把棋盘格内参素材和场景点/棋盘格外参素材放入 calibration/，"
                "或把已有标定文件放入 calibration/。",
            )
            return
        if stages == FULL_3D_REPORT_STAGES and not status.can_run_full_3d:
            self._message(
                "无法运行完整 3D + 报告",
                "完整 3D/OpenSim 必须先有 calibration/*.toml。请先运行校准或导入已有 Calib.toml。",
            )
            return
        for stage, check in self.stage_checks.items():
            check.setChecked(stage in stages)
        self.run_pipeline(stages)

    def run_pipeline(self, selected_stages: Iterable[str] | None = None) -> None:
        if not self.project_dir:
            self._message("尚未载入项目", "请先载入一个项目。")
            return
        if self.process is not None:
            self._message("正在运行", "当前已有 Pose2Sim 流程在运行，请等待结束或先停止。")
            return
        stages = list(selected_stages) if selected_stages is not None else [
            stage for stage, check in self.stage_checks.items() if check.isChecked()
        ]
        if not stages:
            self._message("未选择流程步骤", "请至少选择一个 Pose2Sim 处理步骤。")
            return
        prerequisite_errors = validate_stage_prerequisites(self.project_dir, stages)
        if prerequisite_errors:
            self._message("无法运行流程", "\n\n".join(prerequisite_errors))
            return

        self.pipeline_log.clear()
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._append_process_output)
        self.process.finished.connect(self._process_finished)
        args = ["-m", "pose2sim_gui.runner", "--config", str(self.project_dir), "--stages", *stages]
        self.pipeline_log.appendPlainText(f"正在运行：{sys.executable} {' '.join(args)}\n")
        self._set_run_button_states({"2d": False, "calibration": False, "full": False})
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
        self.pipeline_log.appendPlainText(f"\n流程结束，退出码：{exit_code}。")
        self.process = None
        if exit_code == 0:
            self.generate_auto_reports()
        self.refresh_report_files()
        self.refresh_workflow_status()

    def stop_pipeline(self) -> None:
        if self.process:
            self.process.kill()
            self.pipeline_log.appendPlainText("\n已请求停止。")

    def refresh_report_files(self) -> None:
        self.mot_combo.clear()
        self.video_combo.clear()
        if not self.project_dir:
            return
        mot_files = find_mot_files(self.project_dir)
        report_videos = find_report_video_files(self.project_dir)
        for mot in mot_files:
            self.mot_combo.addItem(str(mot.relative_to(self.project_dir)), str(mot))
        self.video_combo.addItem(f"自动使用全部报告视频：{len(report_videos)} 个", None)
        for video in report_videos:
            try:
                label = str(video.relative_to(self.project_dir))
            except ValueError:
                label = str(video)
            self.video_combo.addItem(label, str(video))
        self.report_log.appendPlainText(
            f"找到 {len(mot_files)} 个 .mot 文件和 {len(report_videos)} 个报告视频。报告视频优先使用 pose/*_pose.mp4。"
        )

    def _selected_mot(self) -> Path | None:
        data = self.mot_combo.currentData()
        return Path(data) if data else None

    def _report_videos(self) -> list[Path]:
        if not self.project_dir:
            return []
        return find_report_video_files(self.project_dir)

    def _log_report_message(self, message: str) -> None:
        if hasattr(self, "report_log"):
            self.report_log.appendPlainText(message)
        if hasattr(self, "pipeline_log"):
            self.pipeline_log.appendPlainText(message)

    def generate_auto_reports(self) -> list[Path]:
        if not self.project_dir:
            return []
        try:
            mirrored = mirror_pose2sim_outputs(self.project_dir)
            result_dir = project_results_dir(self.project_dir)
            if mirrored:
                self._log_report_message(f"\n已同步 Pose2Sim 结果到：{result_dir}")
                self._log_report_message(f"  同步项目：{len(mirrored)} 个文件/文件夹")
            else:
                self._log_report_message(f"\n未发现可同步的 Pose2Sim 结果文件夹；目标目录：{result_dir}")
        except Exception as exc:
            self._log_report_message(f"\n同步 Pose2Sim 结果失败：{exc}")

        mots = find_mot_files(self.project_dir)
        if not mots:
            self._log_report_message("\n未找到 kinematics/*.mot，自动报告已跳过。请运行 OpenSim 运动学阶段后再生成报告。")
            return []
        report_dir = default_report_dir(self.project_dir)
        videos = self._report_videos()
        outputs: list[Path] = []
        self._log_report_message(f"\n正在自动生成报告，输出目录：{report_dir}")
        for mot in mots:
            excel_path = export_excel(mot, report_dir / f"{mot.stem}_关节活动度.xlsx")
            html_path, warnings = export_html(mot, videos, report_dir / f"{mot.stem}_关节活动度.html")
            outputs.extend([excel_path, html_path])
            self._log_report_message(f"  Excel：{excel_path}")
            self._log_report_message(f"  HTML：{html_path}")
            for warning in warnings:
                self._log_report_message(f"  提示：{warning}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(OUTPUT_DIR)))
        return outputs

    def generate_excel_report(self) -> Path | None:
        mot = self._selected_mot()
        if not mot:
            self._message("没有 .mot 文件", "请先运行 OpenSim 运动学，或选择已有 kinematics/*.mot 的项目。")
            return None
        try:
            report_dir = default_report_dir(self.project_dir or mot.parent)
            output = export_excel(mot, report_dir / f"{mot.stem}_关节活动度.xlsx")
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
            output, warnings = export_html(mot, self._report_videos(), report_dir / f"{mot.stem}_关节活动度.html")
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
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setApplicationName("Pose2Sim 图形界面")
    app.setApplicationVersion(__version__)
    return app


def run_gui(argv: list[str] | None = None) -> int:
    app = create_app(argv)
    window = Pose2SimMainWindow()
    window.show()
    return app.exec()
