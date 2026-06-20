from __future__ import annotations

from pathlib import Path
import re


APP_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = APP_ROOT / "input"
OUTPUT_DIR = APP_ROOT / "output"
PROJECTS_DIR = INPUT_DIR / "projects"
RAW_VIDEO_DIR = INPUT_DIR / "videos"
RAW_CALIBRATION_DIR = INPUT_DIR / "calibration"
REPORTS_DIR = OUTPUT_DIR / "reports"


def ensure_app_workspace() -> dict[str, Path]:
    folders = {
        "app": APP_ROOT,
        "input": INPUT_DIR,
        "output": OUTPUT_DIR,
        "projects": PROJECTS_DIR,
        "raw_videos": RAW_VIDEO_DIR,
        "raw_calibration": RAW_CALIBRATION_DIR,
        "reports": REPORTS_DIR,
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
