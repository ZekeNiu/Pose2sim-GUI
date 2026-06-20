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

from .workspace import project_report_dir


VIDEO_EXTENSIONS = {".mp4", ".m4v", ".webm", ".ogg", ".ogv"}

COORDINATE_LABELS: dict[str, str] = {
    "pelvis_tilt": "骨盆前后倾",
    "pelvis_list": "骨盆侧倾",
    "pelvis_rotation": "骨盆旋转",
    "lumbar_extension": "腰椎伸展",
    "lumbar_bending": "腰椎侧屈",
    "lumbar_rotation": "腰椎旋转",
    "hip_flexion": "髋关节屈伸",
    "hip_adduction": "髋关节内收外展",
    "hip_rotation": "髋关节内外旋",
    "knee_angle": "膝关节屈伸",
    "ankle_angle": "踝关节背屈跖屈",
    "subtalar_angle": "距下关节内外翻",
    "mtp_angle": "跖趾关节屈伸",
    "arm_flex": "肩关节屈伸",
    "arm_add": "肩关节内收外展",
    "arm_rot": "肩关节内外旋",
    "elbow_flex": "肘关节屈伸",
    "pro_sup": "前臂旋前旋后",
    "wrist_flex": "腕关节屈伸",
    "wrist_dev": "腕关节尺偏桡偏",
}


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


def is_translation_column(column: str) -> bool:
    name = column.lower()
    return name.endswith(("_tx", "_ty", "_tz")) or name in {"time"}


def split_motion_columns(data: pd.DataFrame) -> tuple[list[str], list[str]]:
    time_name = data.columns[0]
    angle_cols: list[str] = []
    translation_cols: list[str] = []
    for column in data.columns:
        if column == time_name:
            continue
        name = str(column).lower()
        if is_translation_column(name):
            translation_cols.append(str(column))
        else:
            angle_cols.append(str(column))
    return angle_cols, translation_cols


def coordinate_label(column: str) -> str:
    raw = str(column)
    side = ""
    base = raw
    if raw.endswith("_r"):
        side = "右"
        base = raw[:-2]
    elif raw.endswith("_l"):
        side = "左"
        base = raw[:-2]
    label = COORDINATE_LABELS.get(base, raw.replace("_", " "))
    return f"{side}{label}" if side else label


def find_mot_files(project_dir: Path) -> list[Path]:
    return sorted(Path(project_dir).resolve().rglob("kinematics/*.mot"))


def find_processed_video_files(project_dir: Path) -> list[Path]:
    project_dir = Path(project_dir).resolve()
    pose_dir = project_dir / "pose"
    if not pose_dir.exists():
        return []
    return sorted(file for file in pose_dir.rglob("*_pose.mp4") if file.is_file())


def find_video_files(project_dir: Path) -> list[Path]:
    extensions = {".mp4", ".m4v", ".mov", ".avi", ".webm", ".ogg", ".ogv", ".mkv"}
    return sorted(
        file
        for file in Path(project_dir).resolve().rglob("*")
        if file.is_file() and file.suffix.lower() in extensions
    )


def find_report_video_files(project_dir: Path) -> list[Path]:
    processed = find_processed_video_files(project_dir)
    if processed:
        return processed
    videos_dir = Path(project_dir).resolve() / "videos"
    if not videos_dir.exists():
        return []
    extensions = {".mp4", ".m4v", ".mov", ".avi", ".webm", ".ogg", ".ogv", ".mkv"}
    return sorted(file for file in videos_dir.iterdir() if file.is_file() and file.suffix.lower() in extensions)


def default_report_dir(project_dir: Path) -> Path:
    return project_report_dir(project_dir)


def _renamed_angle_frame(data: pd.DataFrame, angle_cols: list[str]) -> pd.DataFrame:
    time_col = data.columns[0]
    output = data[[time_col] + angle_cols].copy()
    rename = {time_col: "时间（秒）", **{col: coordinate_label(col) for col in angle_cols}}
    return output.rename(columns=rename)


def export_excel(mot_path: Path, output_path: Path | None = None) -> Path:
    mot_path = Path(mot_path).resolve()
    data, _ = read_mot(mot_path)
    angle_cols, translation_cols = split_motion_columns(data)
    if output_path is None:
        output_path = mot_path.with_name(f"{mot_path.stem}_joint_angles.xlsx")
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    time_col = data.columns[0]
    angles = _renamed_angle_frame(data, angle_cols)
    translations = data[[time_col] + translation_cols].copy() if translation_cols else pd.DataFrame({time_col: data[time_col]})
    translations = translations.rename(columns={time_col: "时间（秒）"})
    summary = pd.DataFrame(
        [
            {
                "指标": coordinate_label(col),
                "原始列名": col,
                "最小值": data[col].min(),
                "最大值": data[col].max(),
                "平均值": data[col].mean(),
                "活动度（最大-最小）": data[col].max() - data[col].min(),
            }
            for col in angle_cols
        ]
    )

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        angles.to_excel(writer, sheet_name="关节活动度", index=False)
        summary.to_excel(writer, sheet_name="统计摘要", index=False)
        translations.to_excel(writer, sheet_name="平移坐标", index=False)

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


def maybe_transcode_video(video_path: Path, output_dir: Path) -> tuple[Path, list[str]]:
    video_path = Path(video_path).resolve()
    warnings: list[str] = []
    if video_path.suffix.lower() in VIDEO_EXTENSIONS:
        return video_path, warnings

    ffmpeg = ffmpeg_executable()
    if not ffmpeg:
        warnings.append(f"视频格式 {video_path.suffix} 可能无法在浏览器中播放，且未找到 ffmpeg，无法自动转换。")
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


def _prepare_videos(video_paths: list[Path], output_dir: Path, transcode_video: bool) -> tuple[list[Path], list[str]]:
    prepared: list[Path] = []
    warnings: list[str] = []
    seen: set[Path] = set()
    for video in video_paths:
        resolved = Path(video).resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if transcode_video:
            ready, video_warnings = maybe_transcode_video(resolved, output_dir)
            prepared.append(ready)
            warnings.extend(video_warnings)
        else:
            prepared.append(resolved)
    return prepared, warnings


def _figure_html(data: pd.DataFrame, angle_cols: list[str]) -> str:
    time_col = data.columns[0]
    fig = go.Figure()
    for column in angle_cols:
        label = coordinate_label(column)
        fig.add_trace(
            go.Scattergl(
                x=data[time_col],
                y=data[column],
                mode="lines",
                name=label,
                hovertemplate=f"{label}: " + "%{y:.2f}°<extra>%{x:.3f} 秒</extra>",
            )
        )
    fig.update_layout(
        title=None,
        xaxis_title="时间（秒）",
        yaxis_title="关节活动度（度）",
        hovermode="x unified",
        template="plotly_white",
        showlegend=False,
        margin=dict(l=68, r=24, t=18, b=58),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(family="Microsoft YaHei, Segoe UI, Arial, sans-serif", size=13, color="#1f2937"),
        xaxis=dict(showgrid=True, gridcolor="#e5e7eb", zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="#eef2f7", zeroline=False),
    )
    return plot(fig, include_plotlyjs=True, output_type="div", config={"displaylogo": False, "responsive": True})


def export_html(
    mot_path: Path,
    video_paths: list[Path] | Path | None = None,
    output_path: Path | None = None,
    transcode_video: bool = True,
) -> tuple[Path, list[str]]:
    mot_path = Path(mot_path).resolve()
    data, _ = read_mot(mot_path)
    angle_cols, translation_cols = split_motion_columns(data)
    if not angle_cols:
        raise ValueError(f"未在 {mot_path} 中找到关节活动度列")

    if output_path is None:
        output_path = mot_path.with_name(f"{mot_path.stem}_joint_angles.html")
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if video_paths is None:
        video_list: list[Path] = []
    elif isinstance(video_paths, (str, Path)):
        video_list = [Path(video_paths)]
    else:
        video_list = [Path(video) for video in video_paths]
    prepared_videos, warnings = _prepare_videos(video_list, output_path.parent, transcode_video)

    time_col = data.columns[0]
    times = [float(value) for value in data[time_col].tolist()]
    rows: list[dict[str, Any]] = []
    for _, row in data[[time_col] + angle_cols].iterrows():
        values = {
            str(col): (None if pd.isna(row[col]) else float(row[col]))
            for col in [time_col] + angle_cols
        }
        rows.append(values)

    video_cards = ""
    if prepared_videos:
        video_cards = "\n".join(
            f"""
            <article class="video-card">
              <div class="video-title">{html.escape(video.stem)}</div>
              <video class="sync-video" controls preload="metadata" src="{html.escape(video.as_uri())}">
                浏览器无法播放该视频。
              </video>
            </article>
            """
            for video in prepared_videos
        )
    else:
        video_cards = '<div class="empty-state">未找到处理后视频。运行“二维姿态识别”并保存叠加视频后，报告会自动显示所有 *_pose.mp4。</div>'

    warning_html = "".join(f"<li>{html.escape(message)}</li>" for message in warnings)
    if warning_html:
        warning_html = f"<ul class=\"warnings\">{warning_html}</ul>"

    labels = {col: coordinate_label(col) for col in angle_cols}
    fig_div = _figure_html(data, angle_cols)
    payload = {
        "times": times,
        "rows": rows,
        "timeColumn": str(time_col),
        "angleColumns": angle_cols,
        "labels": labels,
        "translationColumns": translation_cols,
    }
    duration = times[-1] - times[0] if len(times) > 1 else 0

    document = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(mot_path.stem)} 关节活动度报告</title>
  <style>
    :root {{
      --bg: #f4f7fb;
      --surface: #ffffff;
      --surface-soft: #f8fafc;
      --line: #d8e0ea;
      --line-soft: #e8edf4;
      --text: #172033;
      --muted: #5d6b82;
      --primary: #1f6feb;
      --primary-soft: #e8f1ff;
      --accent: #0f766e;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
      color: var(--text);
      background: var(--bg);
      line-height: 1.55;
    }}
    header {{
      background: var(--surface);
      border-bottom: 1px solid var(--line);
      padding: 20px 28px 18px;
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 24px;
      font-weight: 700;
      letter-spacing: 0;
    }}
    .meta {{ color: var(--muted); font-size: 14px; }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(120px, 1fr));
      gap: 10px;
      margin-top: 16px;
    }}
    .summary-card {{
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      padding: 10px 12px;
      background: var(--surface-soft);
    }}
    .summary-label {{ color: var(--muted); font-size: 12px; }}
    .summary-value {{ font-weight: 700; margin-top: 4px; }}
    main {{
      display: grid;
      grid-template-columns: minmax(560px, 1fr) minmax(360px, 440px);
      gap: 16px;
      padding: 16px;
      align-items: start;
    }}
    .panel {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      min-width: 0;
    }}
    .panel-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line-soft);
    }}
    .panel-title {{ font-weight: 700; }}
    #plotPanel {{ padding: 0 8px 10px; }}
    .side-stack {{ display: flex; flex-direction: column; gap: 16px; }}
    .video-grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 12px;
      padding: 14px;
      max-height: 48vh;
      overflow: auto;
    }}
    .video-card {{
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      padding: 10px;
      background: var(--surface-soft);
    }}
    .video-title {{
      font-size: 13px;
      color: var(--muted);
      margin-bottom: 8px;
      word-break: break-all;
    }}
    video {{
      width: 100%;
      max-height: 220px;
      background: #0f172a;
      border-radius: 6px;
      display: block;
    }}
    .toolbar {{
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }}
    button, input {{
      font: inherit;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #ffffff;
      color: var(--text);
      min-height: 34px;
    }}
    button {{
      padding: 6px 10px;
      cursor: pointer;
    }}
    button:hover {{ border-color: var(--primary); background: var(--primary-soft); }}
    input {{ padding: 6px 10px; min-width: 180px; }}
    .current-time {{
      color: var(--accent);
      font-weight: 700;
      white-space: nowrap;
    }}
    .table-wrap {{
      overflow: auto;
      max-height: 34vh;
      border-top: 1px solid var(--line-soft);
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line-soft);
      padding: 7px 10px;
      text-align: right;
      vertical-align: top;
    }}
    th {{
      position: sticky;
      top: 0;
      background: #f8fafc;
      z-index: 1;
      color: #334155;
      font-weight: 700;
    }}
    th:first-child, td:first-child {{ text-align: left; }}
    .warnings {{
      margin: 0;
      padding: 10px 28px;
      background: #fff8e5;
      border-bottom: 1px solid #f1d38b;
    }}
    .empty-state {{
      padding: 12px;
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: 8px;
      background: #ffffff;
    }}
    @media (max-width: 1100px) {{
      main {{ grid-template-columns: 1fr; }}
      .summary {{ grid-template-columns: repeat(2, minmax(120px, 1fr)); }}
      .video-grid {{ max-height: none; }}
      .table-wrap {{ max-height: 50vh; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>关节活动度交互报告</h1>
    <div class="meta">{html.escape(mot_path.name)}。鼠标悬停在曲线上会同步所有视频，并显示该时刻的计算后关节活动度。</div>
    <section class="summary">
      <div class="summary-card"><div class="summary-label">采样点</div><div class="summary-value">{len(times)}</div></div>
      <div class="summary-card"><div class="summary-label">时长</div><div class="summary-value">{duration:.2f} 秒</div></div>
      <div class="summary-card"><div class="summary-label">关节活动度指标</div><div class="summary-value">{len(angle_cols)}</div></div>
      <div class="summary-card"><div class="summary-label">同步视频</div><div class="summary-value">{len(prepared_videos)}</div></div>
    </section>
  </header>
  {warning_html}
  <main>
    <section class="panel">
      <div class="panel-header">
        <div>
          <div class="panel-title">关节活动度曲线</div>
          <div class="meta">仅显示 OpenSim .mot 中计算后的角度指标，不显示原始坐标。</div>
        </div>
        <div class="current-time" id="currentTime">时间：{times[0]:.3f} 秒</div>
      </div>
      <div id="plotPanel">{fig_div}</div>
    </section>
    <aside class="side-stack">
      <section class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">当前时刻关节活动度</div>
            <div class="meta">单位：度</div>
          </div>
          <input id="filterInput" type="search" placeholder="筛选指标">
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>指标</th><th>活动度</th></tr></thead>
            <tbody id="angleTable"></tbody>
          </table>
        </div>
      </section>
      <section class="panel">
        <div class="panel-header">
          <div class="panel-title">同步视频</div>
          <div class="toolbar">
            <button id="playAll" type="button">播放全部</button>
            <button id="pauseAll" type="button">暂停全部</button>
          </div>
        </div>
        <div class="video-grid">{video_cards}</div>
      </section>
    </aside>
  </main>
  <script id="motionData" type="application/json">{json.dumps(payload, ensure_ascii=False)}</script>
  <script>
    const payload = JSON.parse(document.getElementById('motionData').textContent);
    const tableBody = document.getElementById('angleTable');
    const currentTime = document.getElementById('currentTime');
    const videos = Array.from(document.querySelectorAll('.sync-video'));
    const plotNode = document.querySelector('.plotly-graph-div');
    const filterInput = document.getElementById('filterInput');
    let currentIndex = 0;

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

    function syncVideos(timeValue) {{
      const target = Math.max(0, timeValue - payload.times[0]);
      videos.forEach((video) => {{
        if (Number.isFinite(target) && Math.abs(video.currentTime - target) > 0.08) {{
          video.currentTime = target;
        }}
      }});
    }}

    function renderTable() {{
      const row = payload.rows[currentIndex];
      const query = filterInput.value.trim().toLowerCase();
      tableBody.innerHTML = payload.angleColumns
        .filter((name) => {{
          const label = payload.labels[name] || name;
          return !query || label.toLowerCase().includes(query) || name.toLowerCase().includes(query);
        }})
        .map((name) => {{
          const value = row[name];
          const text = value === null ? 'NaN' : value.toFixed(2);
          const label = payload.labels[name] || name;
          return `<tr><td>${{label}}</td><td>${{text}}</td></tr>`;
        }}).join('');
    }}

    function updateAt(index) {{
      currentIndex = index;
      const row = payload.rows[index];
      const timeValue = row[payload.timeColumn];
      currentTime.textContent = `时间：${{timeValue.toFixed(3)}} 秒`;
      renderTable();
      syncVideos(timeValue);
    }}

    document.getElementById('playAll').addEventListener('click', () => {{
      videos.forEach((video) => video.play().catch(() => undefined));
    }});
    document.getElementById('pauseAll').addEventListener('click', () => {{
      videos.forEach((video) => video.pause());
    }});
    filterInput.addEventListener('input', renderTable);
    updateAt(0);
    if (plotNode) {{
      plotNode.on('plotly_hover', (event) => {{
        if (!event.points || !event.points.length) return;
        updateAt(nearestIndex(Number(event.points[0].x)));
      }});
      plotNode.on('plotly_click', (event) => {{
        if (!event.points || !event.points.length) return;
        updateAt(nearestIndex(Number(event.points[0].x)));
        videos.forEach((video) => video.play().catch(() => undefined));
      }});
    }}
  </script>
</body>
</html>
"""
    output_path.write_text(document, encoding="utf-8")
    return output_path, warnings


def export_project_reports(project_dir: Path, video_paths: list[Path] | None = None) -> list[Path]:
    project_dir = Path(project_dir).resolve()
    output_dir = default_report_dir(project_dir)
    report_videos = video_paths if video_paths is not None else find_report_video_files(project_dir)
    outputs: list[Path] = []
    for mot_file in find_mot_files(project_dir):
        outputs.append(export_excel(mot_file, output_dir / f"{mot_file.stem}_关节活动度.xlsx"))
        html_path, _ = export_html(mot_file, report_videos, output_dir / f"{mot_file.stem}_关节活动度.html")
        outputs.append(html_path)
    if not outputs:
        raise FileNotFoundError(f"未在 {project_dir} 中找到 kinematics/*.mot 文件")
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="从 Pose2Sim .mot 文件生成 HTML 和 Excel 报告。")
    parser.add_argument("--project", help="Pose2Sim 项目文件夹；会为所有 kinematics/*.mot 生成报告。")
    parser.add_argument("--mot", help="要导出的单个 .mot 文件。")
    parser.add_argument("--video", action="append", help="HTML 报告中用于同步显示的视频文件；可重复提供。")
    parser.add_argument("--html", help="--mot 模式下可选的 HTML 输出路径。")
    parser.add_argument("--excel", help="--mot 模式下可选的 Excel 输出路径。")
    parser.add_argument("--no-transcode", action="store_true", help="不尝试转换为浏览器兼容 MP4。")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        videos = [Path(item) for item in args.video] if args.video else None
        if args.mot:
            mot = Path(args.mot)
            excel_path = export_excel(mot, Path(args.excel) if args.excel else None)
            html_path, warnings = export_html(
                mot,
                videos,
                Path(args.html) if args.html else None,
                transcode_video=not args.no_transcode,
            )
            print(f"Excel 报告：{excel_path}")
            print(f"HTML 报告：{html_path}")
            for message in warnings:
                print(f"提示：{message}")
            return 0
        if args.project:
            outputs = export_project_reports(Path(args.project), videos)
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
