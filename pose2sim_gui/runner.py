from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import traceback

from .config import STAGES, selected_stages_to_runall_kwargs


def run_pose2sim(project_dir: Path, stages: list[str]) -> int:
    project_dir = Path(project_dir).resolve()
    config_path = project_dir / "Config.toml"
    if not config_path.exists():
        raise FileNotFoundError(f"No Config.toml found in {project_dir}")

    kwargs = selected_stages_to_runall_kwargs(stages)
    print(f"Pose2Sim project: {project_dir}", flush=True)
    print(f"Selected stages: {', '.join(stages)}", flush=True)

    # Pose2Sim resolves batch/session folders from the current working directory
    # when a path string is provided, so run from the selected project folder.
    os.chdir(project_dir)

    from Pose2Sim import Pose2Sim

    Pose2Sim.runAll(str(project_dir), **kwargs)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Pose2Sim pipeline stages.")
    parser.add_argument("--config", help="Pose2Sim project directory containing Config.toml.")
    parser.add_argument(
        "--stages",
        nargs="+",
        choices=STAGES,
        default=list(STAGES),
        help="Pipeline stages to run.",
    )
    parser.add_argument("--list-stages", action="store_true", help="Print available stage names and exit.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list_stages:
        print("\n".join(STAGES))
        return 0
    if not args.config:
        parser.error("--config is required unless --list-stages is used")

    try:
        return run_pose2sim(Path(args.config), list(args.stages))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
