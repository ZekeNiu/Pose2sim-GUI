from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.offline import plot


VIDEO_EXTENSIONS = {".mp4", ".m4v", ".webm", ".ogg", ".ogv"}


def read_mot(mot_path: Path) -> tuple[pd.DataFrame, list[str]]:
    mot_path = Path(mot_path)
    lines = mot_path.read_text(encoding="utf-8", errors="replace").splitlines()
    header_end = None
    for index, line in enumerate(lines):
        if line.strip().lower() == "endheader":
            header_end = index
            break
    if header_end is None:
        for index, line in enumerate(lines):
            first = line.strip().split()
            if first and first[0].lower() == "time":
                header_end = index - 1
                break
    if header_end is None:
        raise ValueError(f"无法在 {mot_path} 中找到 .mot 数据表头")

    header_lines = lines[: header_end + 1]
    data = pd.read_csv(mot_path, sep=r"\s+", skiprows=header_end + 1, engine="python")
    if "time" not in [str(col).lower() for col in data.columns]:
        raise ValueError(f"{mot_path} 不包含 time 时间列")
    return data, header_lines


def split_motion_columns(data: pd.DataFrame) -> tuple[list[str], list[str]]:
    time_name = data.columns[0]
    angle_cols: list[str] = []
    translation_cols: list[str] = []
    for column in data.columns:
        if column == time_name:
            continue
        name = str(column).lower()
        if name.endswith(("_tx", "_ty", "_tz")):
            translation_cols.append(str(column))
        else:
            angle_cols.append(str(column))
    return angle_cols, translation_cols


def default_report_dir(project_dir: Path) -> Path:
    output_dir = Path(project_dir) / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def find_mot_files(project_dir: Path) -> list[Path]:
    return sorted(Path(project_dir).resolve().rglob("kinematics/*.mot"))


def find_video_files(project_dir: Path) -> list[Path]:
    extensions = {".mp4", ".m4v", ".mov", ".avi", ".webm", ".ogg", ".ogv", ".mkv"}
    return sorted(
        file
        for file in Path(project_dir).resolve().rglob("*")
        if file.is_file() and file.suffix.lower() in extensions
    )


def export_excel(mot_path: Path, output_path: Path | None = None) -> Path:
    mot_path = Path(mot_path).resolve()
    data, _ = read_mot(mot_path)
    angle_cols, translation_cols = split_motion_columns(data)
    if output_path is None:
        output_path = mot_path.with_name(f"{mot_path.stem}_joint_angles.xlsx")
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    time_col = data.columns[0]
    angles = data[[time_col] + angle_cols].copy()
    translations = data[[time_col] + translation_cols].copy() if translation_cols else pd.DataFrame({time_col: data[time_col]})
    summary = pd.DataFrame(
        [
            {
                "joint": col,
                "min": data[col].min(),
                "max": data[col].max(),
                "mean": data[col].mean(),
                "range_of_motion": data[col].max() - data[col].min(),
            }
            for col in angle_cols
        ]
    )

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        angles.to_excel(writer, sheet_name="joint_angles", index=False)
        translations.to_excel(writer, sheet_name="translations", index=False)
        summary.to_excel(writer, sheet_name="summary", index=False)

    return output_path


def ffmpeg_executable() -> str | None:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def maybe_transcode_video(video_path: Path | None, output_dir: Path) -> tuple[Path | None, list[str]]:
    if video_path is None:
        return None, []
    video_path = Path(video_path).resolve()
    warnings: list[str] = []
    if video_path.suffix.lower() in VIDEO_EXTENSIONS:
        return video_path, warnings

    ffmpeg = ffmpeg_executable()
    if not ffmpeg:
        warnings.append(
            f"视频格式 {video_path.suffix} 可能无法在浏览器中播放，并且未找到 ffmpeg，无法自动转换。"
        )
        return video_path, warnings

    output_dir.mkdir(parents=True, exist_ok=True)
    converted = output_dir / f"{video_path.stem}_browser.mp4"
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(video_path),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-c:a",
        "aac",
        str(converted),
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        warnings.append(f"已转换为浏览器兼容视频：{converted}")
        return converted, warnings
    except Exception as exc:
        warnings.append(f"无法转换视频为 MP4：{exc}")
        return video_path, warnings


def _figure_html(data: pd.DataFrame, angle_cols: list[str]) -> str:
    time_col = data.columns[0]
    fig = go.Figure()
    for column in angle_cols:
        fig.add_trace(
            go.Scattergl(
                x=data[time_col],
                y=data[column],
                mode="lines",
                name=str(column),
                hovertemplate="%{fullData.name}: %{y:.2f}<extra>%{x:.3f}s</extra>",
            )
        )
    fig.update_layout(
        title="OpenSim 关节角",
        xaxis_title="时间（秒）",
        yaxis_title="角度（度）",
        hovermode="x",
        template="plotly_white",
        margin=dict(l=56, r=24, t=52, b=48),
        legend=dict(orientation="h", yanchor="bottom", y=-0.32, xanchor="left", x=0),
    )
    return plot(fig, include_plotlyjs=True, output_type="div")


def export_html(
    mot_path: Path,
    video_path: Path | None = None,
    output_path: Path | None = None,
    transcode_video: bool = True,
) -> tuple[Path, list[str]]:
    mot_path = Path(mot_path).resolve()
    data, _ = read_mot(mot_path)
    angle_cols, translation_cols = split_motion_columns(data)
    if not angle_cols:
        raise ValueError(f"未在 {mot_path} 中找到关节角列")

    if output_path is None:
        output_path = mot_path.with_name(f"{mot_path.stem}_joint_angles.html")
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    if transcode_video:
        video_path, video_warnings = maybe_transcode_video(video_path, output_path.parent)
        warnings.extend(video_warnings)

    time_col = data.columns[0]
    times = [float(value) for value in data[time_col].tolist()]
    rounded_rows: list[dict[str, Any]] = []
    for _, row in data[[time_col] + angle_cols].iterrows():
        rounded_rows.append({str(col): (None if pd.isna(row[col]) else float(row[col])) for col in [time_col] + angle_cols})

    video_tag = ""
    if video_path is not None:
        video_uri = Path(video_path).resolve().as_uri()
        video_tag = (
            f'<video id="motionVideo" controls preload="metadata" src="{html.escape(video_uri)}">'
            "你的浏览器无法播放该视频。"
            "</video>"
        )

    warning_html = "".join(f"<li>{html.escape(message)}</li>" for message in warnings)
    if warning_html:
        warning_html = f"<ul class=\"warnings\">{warning_html}</ul>"

    fig_div = _figure_html(data, angle_cols)
    payload = {
        "times": times,
        "rows": rounded_rows,
        "timeColumn": str(time_col),
        "angleColumns": angle_cols,
        "translationColumns": translation_cols,
    }

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(mot_path.stem)} 关节角</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: #1f2933; background: #f7f8fa; }}
    header {{ padding: 16px 24px; background: #ffffff; border-bottom: 1px solid #d9dee7; }}
    main {{ display: grid; grid-template-columns: minmax(420px, 1fr) 380px; gap: 16px; padding: 16px; }}
    #plotPanel, #sidePanel {{ background: #ffffff; border: 1px solid #d9dee7; border-radius: 8px; min-width: 0; }}
    #plotPanel {{ padding: 8px; }}
    #sidePanel {{ padding: 14px; display: flex; flex-direction: column; gap: 12px; }}
    video {{ width: 100%; max-height: 280px; background: #111827; border-radius: 6px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
    th, td {{ border-bottom: 1px solid #e2e7ef; padding: 5px 6px; text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; }}
    .tableWrap {{ overflow: auto; max-height: 44vh; border: 1px solid #e2e7ef; border-radius: 6px; }}
    .meta {{ font-size: 13px; color: #52606d; }}
    .warnings {{ margin: 0; padding: 10px 24px; background: #fff8e5; border-bottom: 1px solid #f5d88f; }}
    @media (max-width: 980px) {{ main {{ grid-template-columns: 1fr; }} .tableWrap {{ max-height: 50vh; }} }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(mot_path.name)}</h1>
    <div class="meta">把鼠标放在曲线上，可查看最接近时刻的所有关节角，并同步视频时间。</div>
  </header>
  {warning_html}
  <main>
    <section id="plotPanel">{fig_div}</section>
    <aside id="sidePanel">
      {video_tag}
      <div class="meta" id="currentTime">时间：{times[0]:.3f} 秒</div>
      <div class="tableWrap">
        <table>
          <thead><tr><th>关节/坐标</th><th>角度</th></tr></thead>
          <tbody id="angleTable"></tbody>
        </table>
      </div>
    </aside>
  </main>
  <script id="motionData" type="application/json">{json.dumps(payload)}</script>
  <script>
    const payload = JSON.parse(document.getElementById('motionData').textContent);
    const tableBody = document.getElementById('angleTable');
    const currentTime = document.getElementById('currentTime');
    const video = document.getElementById('motionVideo');
    const plotNode = document.querySelector('.plotly-graph-div');

    function nearestIndex(t) {{
      let best = 0;
      let bestDistance = Infinity;
      for (let i = 0; i < payload.times.length; i++) {{
        const distance = Math.abs(payload.times[i] - t);
        if (distance < bestDistance) {{
          bestDistance = distance;
          best = i;
        }}
      }}
      return best;
    }}

    function updateTable(index) {{
      const row = payload.rows[index];
      const timeValue = row[payload.timeColumn];
      currentTime.textContent = `时间：${{timeValue.toFixed(3)}} 秒`;
      tableBody.innerHTML = payload.angleColumns.map((name) => {{
        const value = row[name];
        const text = value === null ? 'NaN' : value.toFixed(2);
        return `<tr><td>${{name}}</td><td>${{text}}</td></tr>`;
      }}).join('');
      if (video && Number.isFinite(timeValue)) {{
        const target = Math.max(0, timeValue - payload.times[0]);
        if (Math.abs(video.currentTime - target) > 0.06) {{
          video.currentTime = target;
        }}
      }}
    }}

    updateTable(0);
    if (plotNode) {{
      plotNode.on('plotly_hover', (event) => {{
        if (!event.points || !event.points.length) return;
        updateTable(nearestIndex(Number(event.points[0].x)));
      }});
      plotNode.on('plotly_click', (event) => {{
        if (!event.points || !event.points.length) return;
        updateTable(nearestIndex(Number(event.points[0].x)));
        if (video) video.play().catch(() => undefined);
      }});
    }}
  </script>
</body>
</html>
"""
    output_path.write_text(document, encoding="utf-8")
    return output_path, warnings


def export_project_reports(project_dir: Path, video_path: Path | None = None) -> list[Path]:
    project_dir = Path(project_dir).resolve()
    output_dir = default_report_dir(project_dir)
    outputs: list[Path] = []
    for mot_file in find_mot_files(project_dir):
        outputs.append(export_excel(mot_file, output_dir / f"{mot_file.stem}_joint_angles.xlsx"))
        html_path, _ = export_html(mot_file, video_path, output_dir / f"{mot_file.stem}_joint_angles.html")
        outputs.append(html_path)
    if not outputs:
        raise FileNotFoundError(f"未在 {project_dir} 中找到 kinematics/*.mot 文件")
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="从 Pose2Sim .mot 文件生成 HTML 和 Excel 报告。")
    parser.add_argument("--project", help="Pose2Sim 项目文件夹；会为所有 kinematics/*.mot 生成报告。")
    parser.add_argument("--mot", help="要导出的单个 .mot 文件。")
    parser.add_argument("--video", help="HTML 报告中用于同步显示的可选视频文件。")
    parser.add_argument("--html", help="--mot 模式下可选的 HTML 输出路径。")
    parser.add_argument("--excel", help="--mot 模式下可选的 Excel 输出路径。")
    parser.add_argument("--no-transcode", action="store_true", help="不尝试转换为浏览器兼容 MP4。")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        video = Path(args.video) if args.video else None
        if args.mot:
            mot = Path(args.mot)
            excel_path = export_excel(mot, Path(args.excel) if args.excel else None)
            html_path, warnings = export_html(
                mot,
                video,
                Path(args.html) if args.html else None,
                transcode_video=not args.no_transcode,
            )
            print(f"Excel 报告：{excel_path}")
            print(f"HTML 报告：{html_path}")
            for message in warnings:
                print(f"提示：{message}")
            return 0
        if args.project:
            outputs = export_project_reports(Path(args.project), video)
            for output in outputs:
                print(output)
            return 0
        parser.error("请提供 --project 或 --mot")
        return 2
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
