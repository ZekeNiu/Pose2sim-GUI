from __future__ import annotations

import argparse
import importlib.metadata
from pathlib import Path
import sys

from . import __version__
from .app import run_gui


def version_report() -> str:
    lines = [f"pose2sim-gui {__version__}", f"python {sys.version.split()[0]}", f"executable {Path(sys.executable)}"]
    for package in ("pose2sim", "opensim", "PySide6", "pandas", "plotly", "openpyxl"):
        try:
            lines.append(f"{package} {importlib.metadata.version(package)}")
        except importlib.metadata.PackageNotFoundError:
            lines.append(f"{package} not installed")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the Pose2Sim desktop GUI.")
    parser.add_argument("--version", action="store_true", help="Show installed package versions and exit.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.version:
        print(version_report())
        return 0
    return run_gui(argv)


if __name__ == "__main__":
    raise SystemExit(main())
