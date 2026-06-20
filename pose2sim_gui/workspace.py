from __future__ import annotations

from pathlib import Path
import re
import shutil


APP_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = APP_ROOT / "input"
OUTPUT_DIR = APP_ROOT / "output"
PROJECTS_DIR = INPUT_DIR / "projects"
RAW_VIDEO_DIR = INPUT_DIR / "videos"
RAW_CALIBRATION_DIR = INPUT_DIR / "calibration"
REPORTS_DIR = OUTPUT_DIR / "reports"
RESULTS_DIR = OUTPUT_DIR / "pose2sim_results"
POSE2SIM_RESULT_DIR_NAMES = (
    "calibration",
    "pose",
    "pose-sync",
    "pose-associated",
    "pose-3d",
    "kinematics",
)
POSE2SIM_RESULT_FILE_NAMES = (
    "Config.toml",
    "logs.txt",
    "opensim_logs.txt",
)


def ensure_app_workspace() -> dict[str, Path]:
    folders = {
        "app": APP_ROOT,
        "input": INPUT_DIR,
        "output": OUTPUT_DIR,
        "projects": PROJECTS_DIR,
        "raw_videos": RAW_VIDEO_DIR,
        "raw_calibration": RAW_CALIBRATION_DIR,
        "reports": REPORTS_DIR,
        "results": RESULTS_DIR,
    }
    for folder in folders.values():
        folder.mkdir(parents=True, exist_ok=True)
    return folders


def safe_folder_name(value: str) -> str:
    cleaned = re.sub(r"[^\w\-.一-龥]+", "_", value.strip(), flags=re.UNICODE)
    return cleaned.strip("._") or "Pose2Sim_Project"


def project_report_dir(project_dir: Path) -> Path:
    ensure_app_workspace()
    project_dir = Path(project_dir).resolve()
    output_dir = REPORTS_DIR / safe_folder_name(project_dir.name)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def project_results_dir(project_dir: Path) -> Path:
    ensure_app_workspace()
    project_dir = Path(project_dir).resolve()
    output_dir = RESULTS_DIR / safe_folder_name(project_dir.name)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def mirror_pose2sim_outputs(project_dir: Path) -> list[Path]:
    """Copy Pose2Sim-generated outputs from the project folder into app output."""

    project_dir = Path(project_dir).resolve()
    output_dir = project_results_dir(project_dir)
    copied: list[Path] = []

    for name in POSE2SIM_RESULT_DIR_NAMES:
        source = project_dir / name
        if not source.exists():
            continue
        destination = output_dir / name
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)
        copied.append(destination)

    copied_files: set[Path] = set()
    for name in POSE2SIM_RESULT_FILE_NAMES:
        source = project_dir / name
        if source.is_file():
            destination = output_dir / source.name
            shutil.copy2(source, destination)
            copied.append(destination)
            copied_files.add(source.resolve())

    for source in sorted(project_dir.glob("*.toml")):
        if source.resolve() in copied_files:
            continue
        destination = output_dir / source.name
        shutil.copy2(source, destination)
        copied.append(destination)

    return copied
