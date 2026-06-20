from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Any, Iterable

import toml


STAGES: tuple[str, ...] = (
    "calibration",
    "poseEstimation",
    "synchronization",
    "personAssociation",
    "triangulation",
    "filtering",
    "markerAugmentation",
    "kinematics",
)

RUNALL_FLAGS: dict[str, str] = {
    "calibration": "do_calibration",
    "poseEstimation": "do_poseEstimation",
    "synchronization": "do_synchronization",
    "personAssociation": "do_personAssociation",
    "triangulation": "do_triangulation",
    "filtering": "do_filtering",
    "markerAugmentation": "do_markerAugmentation",
    "kinematics": "do_kinematics",
}

CALIBRATION_FILE_REQUIRED_STAGES: tuple[str, ...] = ("personAssociation", "triangulation")

POSE_MODELS: tuple[str, ...] = (
    "Body_with_feet",
    "Whole_body_wrist",
    "Whole_body",
    "Lower_body",
    "Body",
    "Hand",
    "Face",
    "Animal",
)

POSE_MODES: tuple[str, ...] = ("lightweight", "balanced", "performance")
DEVICES: tuple[str, ...] = ("auto", "CPU", "CUDA", "MPS", "ROCM")
BACKENDS: tuple[str, ...] = ("auto", "openvino", "onnxruntime", "opencv")
TRACKING_MODES: tuple[str, ...] = ("sports2d", "none", "deepsort")
FILTER_TYPES: tuple[str, ...] = (
    "butterworth",
    "kalman",
    "one_euro",
    "gcv_spline",
    "gaussian",
    "LOESS",
    "median",
    "butterworth_on_speed",
)

VIDEO_EXTENSIONS: tuple[str, ...] = (
    ".mp4",
    ".m4v",
    ".mov",
    ".avi",
    ".mkv",
    ".webm",
    ".ogg",
    ".ogv",
)

CALIBRATION_MEDIA_EXTENSIONS: tuple[str, ...] = VIDEO_EXTENSIONS + (
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".tif",
    ".tiff",
)


@dataclass(frozen=True)
class ProjectStatus:
    project_dir: Path
    has_config: bool
    has_videos: bool
    has_calibration: bool
    mot_files: tuple[Path, ...]

    @property
    def ready_for_config(self) -> bool:
        return self.has_config

    def summary_lines(self) -> list[str]:
        return [
            f"项目路径：{self.project_dir}",
            f"Config.toml：{'已找到' if self.has_config else '缺失'}",
            f"videos 文件夹：{'已找到' if self.has_videos else '缺失'}",
            f"calibration 标定文件：{'已找到' if self.has_calibration else '缺失'}",
            f"kinematics .mot 文件：{len(self.mot_files)} 个",
        ]


@dataclass(frozen=True)
class CalibrationMaterialStatus:
    camera_names: tuple[str, ...]
    intrinsics_file_count: int
    extrinsics_file_count: int
    calibration_input_file_count: int

    @property
    def has_intrinsics_material(self) -> bool:
        return self.intrinsics_file_count > 0

    @property
    def has_extrinsics_material(self) -> bool:
        return self.extrinsics_file_count > 0

    @property
    def has_any_calibration_input(self) -> bool:
        return self.calibration_input_file_count > 0


@dataclass(frozen=True)
class WorkflowStatus:
    project_dir: Path
    has_config: bool
    video_files: tuple[Path, ...]
    camera_names: tuple[str, ...]
    calibration_toml_files: tuple[Path, ...]
    calibration_materials: CalibrationMaterialStatus
    pose_json_count: int
    sync_json_count: int
    trc_files: tuple[Path, ...]
    mot_files: tuple[Path, ...]
    recommended_next_step: str

    @property
    def video_count(self) -> int:
        return len(self.video_files)

    @property
    def has_videos(self) -> bool:
        return bool(self.video_files)

    @property
    def has_calibration_toml(self) -> bool:
        return bool(self.calibration_toml_files)

    @property
    def has_pose_results(self) -> bool:
        return self.pose_json_count > 0

    @property
    def has_sync_results(self) -> bool:
        return self.sync_json_count > 0

    @property
    def has_3d_results(self) -> bool:
        return bool(self.trc_files)

    @property
    def has_reports(self) -> bool:
        return bool(self.mot_files)

    @property
    def can_run_2d_sync(self) -> bool:
        return self.has_config and self.video_count >= 1

    @property
    def can_run_calibration(self) -> bool:
        return self.has_config and (
            self.has_calibration_toml
            or self.calibration_materials.has_any_calibration_input
        )

    @property
    def can_run_full_3d(self) -> bool:
        return self.has_config and self.has_videos and self.has_calibration_toml


def demo_config_path() -> Path:
    import Pose2Sim

    package_dir = Path(Pose2Sim.__file__).resolve().parent
    demo_path = package_dir / "Demo_SinglePerson" / "Config.toml"
    if not demo_path.exists():
        raise FileNotFoundError(f"未找到 Pose2Sim 示例 Config.toml：{demo_path}")
    return demo_path


def copy_demo_config(project_dir: Path) -> Path:
    project_dir = Path(project_dir).resolve()
    project_dir.mkdir(parents=True, exist_ok=True)
    ensure_standard_project_folders(project_dir)
    destination = project_dir / "Config.toml"
    if destination.exists():
        raise FileExistsError(f"{destination} 已存在")
    shutil.copy2(demo_config_path(), destination)
    sanitize_new_project_config(destination)
    return destination


def ensure_project_config(project_dir: Path) -> tuple[Path, bool]:
    project_dir = Path(project_dir).resolve()
    project_dir.mkdir(parents=True, exist_ok=True)
    ensure_standard_project_folders(project_dir)
    destination = project_dir / "Config.toml"
    if destination.exists():
        return destination, False
    shutil.copy2(demo_config_path(), destination)
    sanitize_new_project_config(destination)
    return destination, True


def ensure_standard_project_folders(project_dir: Path) -> list[Path]:
    project_dir = Path(project_dir).resolve()
    created_or_existing: list[Path] = []
    for name in ("videos", "calibration", "reports"):
        folder = project_dir / name
        folder.mkdir(parents=True, exist_ok=True)
        created_or_existing.append(folder)
    return created_or_existing


def video_files(project_dir: Path) -> tuple[Path, ...]:
    videos_dir = Path(project_dir).resolve() / "videos"
    if not videos_dir.is_dir():
        return ()
    return tuple(
        sorted(
            file
            for file in videos_dir.iterdir()
            if file.is_file() and file.suffix.lower() in VIDEO_EXTENSIONS
        )
    )


def camera_names_from_videos(project_dir: Path) -> tuple[str, ...]:
    names: list[str] = []
    for file in video_files(project_dir):
        name = normalize_camera_name(file.stem)
        if name not in names:
            names.append(name)
    return tuple(names)


def normalize_camera_name(name: str) -> str:
    clean = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in name.strip())
    clean = clean.strip("._-")
    return clean or "camera"


def ensure_calibration_folders(project_dir: Path, camera_names: Iterable[str] | None = None) -> list[Path]:
    project_dir = Path(project_dir).resolve()
    ensure_standard_project_folders(project_dir)
    names = tuple(normalize_camera_name(name) for name in (camera_names or camera_names_from_videos(project_dir)))
    if not names:
        names = ("cam01", "cam02")

    created_or_existing: list[Path] = []
    for base in ("intrinsics", "extrinsics"):
        base_dir = project_dir / "calibration" / base
        base_dir.mkdir(parents=True, exist_ok=True)
        created_or_existing.append(base_dir)
        for name in names:
            folder = base_dir / name
            folder.mkdir(parents=True, exist_ok=True)
            created_or_existing.append(folder)
    return created_or_existing


def calibration_toml_files(project_dir: Path) -> list[Path]:
    calibration_dir = Path(project_dir).resolve() / "calibration"
    if not calibration_dir.is_dir():
        return []
    return sorted(file for file in calibration_dir.glob("*.toml") if file.is_file())


def _count_files(folder: Path, extensions: tuple[str, ...] | None = None) -> int:
    if not folder.is_dir():
        return 0
    return sum(
        1
        for file in folder.rglob("*")
        if file.is_file()
        and (extensions is None or file.suffix.lower() in extensions)
    )


def calibration_material_status(project_dir: Path) -> CalibrationMaterialStatus:
    project_dir = Path(project_dir).resolve()
    calibration_dir = project_dir / "calibration"
    camera_names = camera_names_from_videos(project_dir)
    if not camera_names and calibration_dir.is_dir():
        folder_names: set[str] = set()
        for base_name in ("intrinsics", "extrinsics"):
            base_dir = calibration_dir / base_name
            if base_dir.is_dir():
                folder_names.update(child.name for child in base_dir.iterdir() if child.is_dir())
        camera_names = tuple(sorted(normalize_camera_name(name) for name in folder_names))

    intrinsics_dir = calibration_dir / "intrinsics"
    extrinsics_dir = calibration_dir / "extrinsics"
    return CalibrationMaterialStatus(
        camera_names=tuple(camera_names),
        intrinsics_file_count=_count_files(intrinsics_dir, CALIBRATION_MEDIA_EXTENSIONS),
        extrinsics_file_count=_count_files(extrinsics_dir, CALIBRATION_MEDIA_EXTENSIONS),
        calibration_input_file_count=_count_files(calibration_dir),
    )


def validate_stage_prerequisites(project_dir: Path, stages: Iterable[str]) -> list[str]:
    selected = set(stages)
    errors: list[str] = []
    calibration_required = selected.intersection(CALIBRATION_FILE_REQUIRED_STAGES)
    if calibration_required and "calibration" not in selected and not calibration_toml_files(project_dir):
        stage_names = ", ".join(stage for stage in STAGES if stage in calibration_required)
        errors.append(
            "当前选择了需要相机标定文件的步骤："
            f"{stage_names}。但项目 calibration/ 文件夹中没有 .toml 标定文件，且本次没有勾选“相机校准”。"
            "请先完成相机校准生成 Calib.toml，或导入/转换已有标定文件；如果只想检查二维姿态和软件同步，"
            "本次只运行“二维姿态识别”和“多相机同步”。"
        )
    return errors


def validate_toml_text(text: str) -> tuple[bool, str]:
    try:
        toml.loads(text)
    except Exception as exc:  # toml raises multiple parser exceptions.
        return False, str(exc)
    return True, "TOML 语法正确。"


def load_config(project_dir: Path) -> dict[str, Any]:
    config_path = Path(project_dir) / "Config.toml"
    if not config_path.exists():
        raise FileNotFoundError(f"未在 {Path(project_dir).resolve()} 中找到 Config.toml")
    return toml.load(config_path)


def load_config_text(project_dir: Path) -> str:
    return (Path(project_dir) / "Config.toml").read_text(encoding="utf-8")


def save_config(project_dir: Path, config: dict[str, Any]) -> Path:
    config_path = Path(project_dir) / "Config.toml"
    config_path.write_text(toml.dumps(config), encoding="utf-8")
    return config_path


def sanitize_new_project_config(config_path: Path) -> None:
    """Remove demo-only calibration coordinates from a copied template."""

    try:
        config = toml.load(config_path)
    except Exception:
        return
    scene = (
        config.setdefault("calibration", {})
        .setdefault("calculate", {})
        .setdefault("extrinsics", {})
        .setdefault("scene", {})
    )
    scene["object_coords_3d"] = []
    Path(config_path).write_text(toml.dumps(config), encoding="utf-8")


def save_config_text(project_dir: Path, text: str) -> Path:
    ok, message = validate_toml_text(text)
    if not ok:
        raise ValueError(message)
    config_path = Path(project_dir) / "Config.toml"
    config_path.write_text(text, encoding="utf-8")
    return config_path


def get_nested(config: dict[str, Any], path: Iterable[str], default: Any = None) -> Any:
    cursor: Any = config
    for key in path:
        if not isinstance(cursor, dict) or key not in cursor:
            return default
        cursor = cursor[key]
    return cursor


def set_nested(config: dict[str, Any], path: Iterable[str], value: Any) -> None:
    keys = list(path)
    cursor = config
    for key in keys[:-1]:
        cursor = cursor.setdefault(key, {})
    cursor[keys[-1]] = value


def parse_toml_value(text: str) -> Any:
    stripped = text.strip()
    if stripped == "":
        return ""
    try:
        return toml.loads(f"value = {stripped}")["value"]
    except Exception:
        return stripped.strip("'\"")


def display_toml_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return toml.dumps({"value": value}).split("=", 1)[1].strip()


def project_status(project_dir: Path) -> ProjectStatus:
    project_dir = Path(project_dir).resolve()
    mot_files = tuple(sorted(project_dir.rglob("kinematics/*.mot"))) if project_dir.exists() else ()
    return ProjectStatus(
        project_dir=project_dir,
        has_config=(project_dir / "Config.toml").exists(),
        has_videos=(project_dir / "videos").is_dir(),
        has_calibration=bool(calibration_toml_files(project_dir)) if project_dir.exists() else False,
        mot_files=mot_files,
    )


def project_workflow_status(project_dir: Path) -> WorkflowStatus:
    project_dir = Path(project_dir).resolve()
    exists = project_dir.exists()
    videos = video_files(project_dir) if exists else ()
    calib_files = tuple(calibration_toml_files(project_dir)) if exists else ()
    materials = calibration_material_status(project_dir) if exists else CalibrationMaterialStatus((), 0, 0, 0)
    pose_json_count = _count_files(project_dir / "pose", (".json",)) if exists else 0
    sync_json_count = _count_files(project_dir / "pose-sync", (".json",)) if exists else 0
    trc_files = tuple(sorted(project_dir.rglob("pose-3d/*.trc"))) if exists else ()
    mot_files = tuple(sorted(project_dir.rglob("kinematics/*.mot"))) if exists else ()
    has_config = (project_dir / "Config.toml").exists() if exists else False

    if not exists or not has_config:
        next_step = "选择或新建项目；GUI 会自动创建 Config.toml 和标准文件夹。"
    elif not videos:
        next_step = "导入正式动作视频到 videos/，每个相机一个视频。"
    elif not calib_files and not materials.has_any_calibration_input:
        next_step = "创建校准文件夹并补拍/导入棋盘格内参素材与场景点外参素材。"
    elif not calib_files:
        next_step = "先运行相机校准，生成 calibration/*.toml；相机移动后必须重做外参。"
    elif not pose_json_count:
        next_step = "可以先运行“只检查 2D/同步”，确认识别和时间同步质量。"
    elif not mot_files:
        next_step = "已有校准与 2D 结果，可以运行“完整 3D + 报告”。"
    else:
        next_step = "已生成 OpenSim .mot，可在“报告”页打开 HTML/Excel。"

    return WorkflowStatus(
        project_dir=project_dir,
        has_config=has_config,
        video_files=videos,
        camera_names=camera_names_from_videos(project_dir) if exists else (),
        calibration_toml_files=calib_files,
        calibration_materials=materials,
        pose_json_count=pose_json_count,
        sync_json_count=sync_json_count,
        trc_files=trc_files,
        mot_files=mot_files,
        recommended_next_step=next_step,
    )


def read_scene_points_csv(path: Path) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            name = (row.get("name") or row.get("点名") or row.get("point") or "").strip()
            x_value = row.get("x") or row.get("X")
            y_value = row.get("y") or row.get("Y")
            z_value = row.get("z") or row.get("Z")
            if x_value is None or y_value is None or z_value is None:
                raise ValueError("场景点 CSV 必须包含 name/x/y/z 列，或中文点名列加 X/Y/Z 列。")
            rows.append(
                {
                    "name": name,
                    "x": float(x_value),
                    "y": float(y_value),
                    "z": float(z_value),
                }
            )
    return rows


def write_scene_points_csv(path: Path, rows: Iterable[dict[str, float | str]]) -> Path:
    path = Path(path)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["name", "x", "y", "z"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "name": row.get("name", ""),
                    "x": row.get("x", ""),
                    "y": row.get("y", ""),
                    "z": row.get("z", ""),
                }
            )
    return path


def apply_beginner_safety(config: dict[str, Any]) -> list[str]:
    """Force settings that should not be exposed in the beginner form."""

    warnings: list[str] = []
    pose = config.setdefault("pose", {})
    pose["output_format"] = "openpose"

    for key in ("handle_LR_swap", "undistort_points"):
        if pose.get(key):
            warnings.append(f"已关闭 pose.{key}；该功能在当前 Pose2Sim 中尚不适合新手安全启用。")
        pose[key] = False

    if pose.get("display_detection", True) and pose.get("parallel_workers_pose") not in (False, 0, 1):
        pose["parallel_workers_pose"] = False
        warnings.append("因为 display_detection=true，已将 pose.parallel_workers_pose 设为 false。")

    extrinsics = (
        config.setdefault("calibration", {})
        .setdefault("calculate", {})
        .setdefault("extrinsics", {})
    )
    if extrinsics.get("moving_cameras"):
        warnings.append("已关闭 moving_cameras；当前 Pose2Sim 尚未实现移动相机校准。")
    extrinsics["moving_cameras"] = False

    if extrinsics.get("extrinsics_method") == "keypoints":
        extrinsics["extrinsics_method"] = "scene"
        warnings.append("已把 extrinsics_method 从 keypoints 改为 scene；keypoints 外参校准仍未完成。")

    mode = pose.get("mode", "balanced")
    if isinstance(mode, str) and mode.strip().startswith("{"):
        pose["mode"] = "balanced"
        warnings.append("新手模式不开放自定义 pose.mode 字典，已重置为 balanced。")

    return warnings


def selected_stages_to_runall_kwargs(stages: Iterable[str]) -> dict[str, bool]:
    selected = set(stages)
    unknown = selected.difference(STAGES)
    if unknown:
        raise ValueError(f"未知流程步骤：{', '.join(sorted(unknown))}")
    return {flag: stage in selected for stage, flag in RUNALL_FLAGS.items()}
