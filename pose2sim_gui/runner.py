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
        raise FileNotFoundError(f"未在 {project_dir} 中找到 Config.toml")

    kwargs = selected_stages_to_runall_kwargs(stages)
    print(f"Pose2Sim 项目：{project_dir}", flush=True)
    print(f"选中步骤：{', '.join(stages)}", flush=True)

    # Pose2Sim resolves batch/session folders from the current working directory
    # when a path string is provided, so run from the selected project folder.
    os.chdir(project_dir)

    from Pose2Sim import Pose2Sim

    Pose2Sim.runAll(str(project_dir), **kwargs)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行 Pose2Sim 处理流程。")
    parser.add_argument("--config", help="包含 Config.toml 的 Pose2Sim 项目文件夹。")
    parser.add_argument(
        "--stages",
        nargs="+",
        choices=STAGES,
        default=list(STAGES),
        help="要运行的流程步骤。",
    )
    parser.add_argument("--list-stages", action="store_true", help="列出可用流程步骤并退出。")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list_stages:
        print("\n".join(STAGES))
        return 0
    if not args.config:
        parser.error("除非使用 --list-stages，否则必须提供 --config")

    try:
        return run_pose2sim(Path(args.config), list(args.stages))
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr, flush=True)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
