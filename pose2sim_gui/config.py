from __future__ import annotations

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
            f"calibration 文件夹：{'已找到' if self.has_calibration else '缺失'}",
            f"kinematics .mot 文件：{len(self.mot_files)} 个",
        ]


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
    return destination


def ensure_project_config(project_dir: Path) -> tuple[Path, bool]:
    project_dir = Path(project_dir).resolve()
    project_dir.mkdir(parents=True, exist_ok=True)
    ensure_standard_project_folders(project_dir)
    destination = project_dir / "Config.toml"
    if destination.exists():
        return destination, False
    shutil.copy2(demo_config_path(), destination)
    return destination, True


def ensure_standard_project_folders(project_dir: Path) -> list[Path]:
    project_dir = Path(project_dir).resolve()
    created_or_existing: list[Path] = []
    for name in ("videos", "calibration", "reports"):
        folder = project_dir / name
        folder.mkdir(parents=True, exist_ok=True)
        created_or_existing.append(folder)
    return created_or_existing


def calibration_toml_files(project_dir: Path) -> list[Path]:
    calibration_dir = Path(project_dir).resolve() / "calibration"
    if not calibration_dir.is_dir():
        return []
    return sorted(file for file in calibration_dir.glob("*.toml") if file.is_file())


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
        has_calibration=any(
            child.is_dir() and "calib" in child.name.lower()
            for child in project_dir.iterdir()
        )
        if project_dir.exists()
        else False,
        mot_files=mot_files,
    )


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
