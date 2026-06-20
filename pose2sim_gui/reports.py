from __future__ import annotations

import argparse
from dataclasses import dataclass
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any
from urllib.parse import quote

import pandas as pd
import plotly.graph_objects as go
from plotly.offline import plot

from .workspace import project_report_dir


VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".avi", ".webm", ".ogg", ".ogv", ".mkv"}
BROWSER_VIDEO_EXTENSIONS = {".mp4", ".m4v", ".webm", ".ogg", ".ogv"}


@dataclass(frozen=True)
class CoordinateInfo:
    label: str
    plane: str
    neutral: str
    direction: str
    definition: str
    boundary: str
    body_order: int
    motion_order: int


DEFAULT_BOUNDARY = (
    "该指标来自 OpenSim 逆运动学结果。数值依赖相机校准、同步、二维识别质量、三维重建质量、模型缩放和 IK 权重；"
    "不应单独作为临床诊断结论。跨被试或跨试次比较前，应确认采集设置、模型和滤波参数一致。"
)

COORDINATE_INFO: dict[str, CoordinateInfo] = {
    "pelvis_tilt": CoordinateInfo(
        "骨盆前后倾",
        "矢状面",
        "OpenSim 模型中骨盆相对实验室坐标系的中立姿态。",
        "正负方向遵循 OpenSim 模型坐标定义，通常用于描述骨盆前倾/后倾变化。",
        "由 OpenSim 逆运动学估计的骨盆绕横向轴旋转坐标。",
        DEFAULT_BOUNDARY,
        10,
        10,
    ),
    "pelvis_list": CoordinateInfo(
        "骨盆侧倾",
        "额状面",
        "骨盆左右髂嵴高度接近模型中立位。",
        "正负方向遵循 OpenSim 坐标定义，表示骨盆向左/右侧倾的相对变化。",
        "由 OpenSim 逆运动学估计的骨盆绕前后轴旋转坐标。",
        DEFAULT_BOUNDARY,
        10,
        20,
    ),
    "pelvis_rotation": CoordinateInfo(
        "骨盆水平旋转",
        "水平面",
        "骨盆朝向与模型中立朝向一致。",
        "正负方向遵循 OpenSim 坐标定义，表示骨盆左/右旋转的相对变化。",
        "由 OpenSim 逆运动学估计的骨盆绕垂直轴旋转坐标。",
        DEFAULT_BOUNDARY,
        10,
        30,
    ),
    "lumbar_extension": CoordinateInfo(
        "腰椎屈伸",
        "矢状面",
        "躯干相对骨盆处于模型中立姿态。",
        "正负方向遵循 OpenSim 模型定义，通常对应腰椎伸展/屈曲方向。",
        "由 OpenSim 逆运动学估计的躯干/腰椎相对骨盆矢状面角度。",
        DEFAULT_BOUNDARY,
        20,
        10,
    ),
    "lumbar_bending": CoordinateInfo(
        "腰椎侧屈",
        "额状面",
        "躯干相对骨盆无明显侧屈。",
        "正负方向表示左右侧屈方向，具体以 OpenSim 模型坐标定义为准。",
        "由 OpenSim 逆运动学估计的腰椎额状面角度。",
        DEFAULT_BOUNDARY,
        20,
        20,
    ),
    "lumbar_rotation": CoordinateInfo(
        "腰椎旋转",
        "水平面",
        "躯干相对骨盆无明显轴向旋转。",
        "正负方向表示左右旋转方向，具体以 OpenSim 模型坐标定义为准。",
        "由 OpenSim 逆运动学估计的腰椎水平面旋转角度。",
        DEFAULT_BOUNDARY,
        20,
        30,
    ),
    "arm_flex": CoordinateInfo(
        "肩关节屈伸",
        "矢状面",
        "上臂贴近躯干并接近模型解剖中立位。",
        "正负方向遵循 OpenSim 模型定义，通常对应肩屈曲/伸展方向。",
        "由 OpenSim 逆运动学估计的肩关节矢状面角度。",
        DEFAULT_BOUNDARY,
        30,
        10,
    ),
    "arm_add": CoordinateInfo(
        "肩关节内收外展",
        "额状面",
        "上臂接近躯干侧方中立位。",
        "正负方向表示内收/外展方向，具体以模型坐标定义为准。",
        "由 OpenSim 逆运动学估计的肩关节额状面角度。",
        DEFAULT_BOUNDARY,
        30,
        20,
    ),
    "arm_rot": CoordinateInfo(
        "肩关节内外旋",
        "水平面/长轴旋转",
        "上臂处于模型中立旋转位。",
        "正负方向表示内旋/外旋方向，具体以模型坐标定义为准。",
        "由 OpenSim 逆运动学估计的肩关节轴向旋转角度。",
        DEFAULT_BOUNDARY,
        30,
        30,
    ),
    "elbow_flex": CoordinateInfo(
        "肘关节屈伸",
        "矢状面",
        "肘关节接近伸直中立位。",
        "正负方向遵循 OpenSim 模型定义，通常用于描述肘屈曲/伸展。",
        "由 OpenSim 逆运动学估计的肘关节屈伸角。",
        DEFAULT_BOUNDARY,
        40,
        10,
    ),
    "pro_sup": CoordinateInfo(
        "前臂旋前旋后",
        "前臂长轴旋转",
        "前臂处于模型中立旋转位。",
        "正负方向表示旋前/旋后方向，具体以模型坐标定义为准。",
        "由 OpenSim 逆运动学估计的桡尺关节/前臂旋转角度。",
        DEFAULT_BOUNDARY,
        45,
        10,
    ),
    "wrist_flex": CoordinateInfo(
        "腕关节屈伸",
        "矢状面",
        "腕关节接近中立伸直位。",
        "正负方向表示腕屈曲/伸展方向，具体以模型坐标定义为准。",
        "由 OpenSim 逆运动学估计的腕关节屈伸角。",
        DEFAULT_BOUNDARY,
        50,
        10,
    ),
    "wrist_dev": CoordinateInfo(
        "腕关节尺偏桡偏",
        "额状面",
        "腕关节接近中立位。",
        "正负方向表示尺偏/桡偏方向，具体以模型坐标定义为准。",
        "由 OpenSim 逆运动学估计的腕关节额状面偏移角。",
        DEFAULT_BOUNDARY,
        50,
        20,
    ),
    "hip_flexion": CoordinateInfo(
        "髋关节屈伸",
        "矢状面",
        "大腿相对骨盆接近模型解剖中立位。",
        "正负方向遵循 OpenSim 模型定义，通常用于描述髋屈曲/伸展。",
        "由 OpenSim 逆运动学估计的股骨相对骨盆矢状面角度。",
        DEFAULT_BOUNDARY,
        60,
        10,
    ),
    "hip_adduction": CoordinateInfo(
        "髋关节内收外展",
        "额状面",
        "大腿相对骨盆接近中立内外展位。",
        "正负方向表示内收/外展方向，具体以模型坐标定义为准。",
        "由 OpenSim 逆运动学估计的髋关节额状面角度。",
        DEFAULT_BOUNDARY,
        60,
        20,
    ),
    "hip_rotation": CoordinateInfo(
        "髋关节内外旋",
        "水平面/长轴旋转",
        "大腿相对骨盆接近中立旋转位。",
        "正负方向表示内旋/外旋方向，具体以模型坐标定义为准。",
        "由 OpenSim 逆运动学估计的髋关节轴向旋转角度。",
        DEFAULT_BOUNDARY,
        60,
        30,
    ),
    "knee_angle": CoordinateInfo(
        "膝关节屈伸",
        "矢状面",
        "膝关节接近伸直中立位。",
        "正负方向遵循 OpenSim 模型定义，通常用于描述膝屈曲/伸展。",
        "由 OpenSim 逆运动学估计的胫骨相对股骨屈伸角。",
        DEFAULT_BOUNDARY,
        70,
        10,
    ),
    "ankle_angle": CoordinateInfo(
        "踝关节背屈跖屈",
        "矢状面",
        "足部相对小腿接近中立位。",
        "正负方向遵循 OpenSim 模型定义，通常用于描述背屈/跖屈。",
        "由 OpenSim 逆运动学估计的踝关节矢状面角度。",
        DEFAULT_BOUNDARY,
        80,
        10,
    ),
    "subtalar_angle": CoordinateInfo(
        "距下关节内翻外翻",
        "额状面",
        "后足接近中立内外翻位。",
        "正负方向表示内翻/外翻方向，具体以模型坐标定义为准。",
        "由 OpenSim 逆运动学估计的距下关节角度。",
        DEFAULT_BOUNDARY,
        90,
        10,
    ),
    "mtp_angle": CoordinateInfo(
        "跖趾关节屈伸",
        "矢状面",
        "跖趾关节接近中立位。",
        "正负方向表示跖趾屈伸方向，具体以模型坐标定义为准。",
        "由 OpenSim 逆运动学估计的跖趾关节角度。",
        DEFAULT_BOUNDARY,
        100,
        10,
    ),
}

TOKEN_LABELS: dict[str, str] = {
    "pelvis": "骨盆",
    "lumbar": "腰椎",
    "hip": "髋关节",
    "knee": "膝关节",
    "ankle": "踝关节",
    "subtalar": "距下关节",
    "mtp": "跖趾关节",
    "shoulder": "肩关节",
    "arm": "肩关节",
    "elbow": "肘关节",
    "forearm": "前臂",
    "wrist": "腕关节",
    "tilt": "前后倾",
    "list": "侧倾",
    "rotation": "旋转",
    "extension": "屈伸",
    "flexion": "屈伸",
    "adduction": "内收外展",
    "abduction": "外展内收",
    "angle": "屈伸",
    "rot": "内外旋",
    "add": "内收外展",
    "flex": "屈伸",
    "dev": "尺偏桡偏",
    "pro": "旋前",
    "sup": "旋后",
}

SIDE_LABELS = {"_l": "左", "_r": "右"}
SIDE_ORDER = {"": 0, "_l": 1, "_r": 2}


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
    return sort_angle_columns(angle_cols), translation_cols


def split_side(column: str) -> tuple[str, str]:
    raw = str(column)
    if raw.endswith("_r"):
        return raw[:-2], "_r"
    if raw.endswith("_l"):
        return raw[:-2], "_l"
    return raw, ""


def _fallback_chinese_label(base: str) -> str:
    translated = [TOKEN_LABELS[token] for token in re.split(r"[_\W]+", base.lower()) if token in TOKEN_LABELS]
    if translated:
        label = "".join(translated)
        return label if "关节" in label or "骨盆" in label or "腰椎" in label else f"{label}活动度"
    return "其他关节活动度"


def coordinate_info(column: str) -> dict[str, str]:
    base, side_suffix = split_side(column)
    info = COORDINATE_INFO.get(base)
    side = SIDE_LABELS.get(side_suffix, "")
    if info:
        label = f"{side}{info.label}" if side else info.label
        return {
            "label": label,
            "plane": info.plane,
            "neutral": info.neutral,
            "direction": info.direction,
            "definition": info.definition,
            "boundary": info.boundary,
            "raw": str(column),
        }
    fallback = _fallback_chinese_label(base)
    label = f"{side}{fallback}" if side else fallback
    return {
        "label": label,
        "plane": "取决于 OpenSim 模型坐标定义",
        "neutral": "以所用 OpenSim 模型的 0°/中立位为准。",
        "direction": "正负方向以 .osim 模型中该坐标的定义为准；建议结合模型文档和静态姿态核对。",
        "definition": "该列来自 OpenSim 逆运动学 .mot 结果，GUI 未从原始 2D/3D 坐标重新计算。",
        "boundary": DEFAULT_BOUNDARY,
        "raw": str(column),
    }


def coordinate_label(column: str) -> str:
    return coordinate_info(column)["label"]


def _coordinate_sort_key(column: str) -> tuple[int, int, int, str]:
    base, side_suffix = split_side(column)
    info = COORDINATE_INFO.get(base)
    body_order = info.body_order if info else 999
    motion_order = info.motion_order if info else 999
    return body_order, SIDE_ORDER.get(side_suffix, 9), motion_order, coordinate_label(column)


def sort_angle_columns(columns: list[str]) -> list[str]:
    return sorted(columns, key=_coordinate_sort_key)


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


@dataclass(frozen=True)
class PreparedVideo:
    title: str
    path: Path
    src: str


def safe_file_stem(value: str) -> str:
    cleaned = re.sub(r"[^\w\-.一-龥]+", "_", value.strip(), flags=re.UNICODE)
    return cleaned.strip("._") or "video"


def _relative_media_src(path: Path, html_dir: Path) -> str:
    path = path.resolve()
    html_dir = html_dir.resolve()
    try:
        rel = path.relative_to(html_dir).as_posix()
        return quote(rel, safe="/._-")
    except ValueError:
        return path.as_uri()


def _copy_video_to_media(video_path: Path, media_dir: Path, index: int) -> Path:
    media_dir.mkdir(parents=True, exist_ok=True)
    suffix = video_path.suffix.lower() if video_path.suffix else ".mp4"
    destination = media_dir / f"{index:02d}_{safe_file_stem(video_path.stem)}{suffix}"
    if video_path.resolve() != destination.resolve():
        shutil.copy2(video_path, destination)
    return destination


def _transcode_video_to_mp4(video_path: Path, media_dir: Path, index: int) -> tuple[Path | None, str | None]:
    ffmpeg = ffmpeg_executable()
    if not ffmpeg:
        return None, "未找到 ffmpeg，无法自动转码为浏览器兼容 MP4。"

    media_dir.mkdir(parents=True, exist_ok=True)
    converted = media_dir / f"{index:02d}_{safe_file_stem(video_path.stem)}_browser.mp4"
    if converted.exists() and converted.stat().st_mtime >= video_path.stat().st_mtime and converted.stat().st_size > 0:
        return converted, None

    command = [
        ffmpeg,
        "-y",
        "-i",
        str(video_path),
        "-map",
        "0:v:0",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-an",
        str(converted),
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return converted, None
    except Exception as exc:
        return None, f"无法把 {video_path.name} 转码为浏览器兼容 MP4：{exc}"


def _prepare_videos(video_paths: list[Path], output_dir: Path, transcode_video: bool) -> tuple[list[PreparedVideo], list[str]]:
    prepared: list[PreparedVideo] = []
    warnings: list[str] = []
    seen: set[Path] = set()
    media_dir = Path(output_dir).resolve() / "media"
    for index, video in enumerate(video_paths, start=1):
        resolved = Path(video).resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if not resolved.exists():
            warnings.append(f"未找到视频文件：{resolved}")
            continue
        ready: Path | None = None
        if transcode_video:
            ready, warning = _transcode_video_to_mp4(resolved, media_dir, index)
            if warning:
                warnings.append(warning)
        if ready is None:
            ready = _copy_video_to_media(resolved, media_dir, index)
            if resolved.suffix.lower() not in BROWSER_VIDEO_EXTENSIONS:
                warnings.append(f"已复制 {resolved.name}，但该格式可能无法在浏览器中直接播放。")
        prepared.append(PreparedVideo(title=resolved.stem, path=ready, src=_relative_media_src(ready, Path(output_dir))))
    return prepared, warnings


def default_visible_columns(angle_cols: list[str]) -> set[str]:
    preferred = [
        col
        for col in angle_cols
        if split_side(col)[0] in {"hip_flexion", "knee_angle", "ankle_angle", "pelvis_tilt"}
    ]
    return set(preferred[:8] or angle_cols[: min(8, len(angle_cols))])


def _figure_html(data: pd.DataFrame, angle_cols: list[str], visible_columns: set[str]) -> str:
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
                visible=True if column in visible_columns else "legendonly",
                hovertemplate=f"{label}: " + "%{y:.2f}°<extra>%{x:.3f} 秒</extra>",
            )
        )
    fig.update_layout(
        title=None,
        xaxis_title="时间（秒）",
        yaxis_title="关节活动度（度）",
        hovermode="x unified",
        template="plotly_white",
        showlegend=True,
        margin=dict(l=68, r=24, t=18, b=58),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(family="Microsoft YaHei, Segoe UI, Arial, sans-serif", size=13, color="#1f2937"),
        legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="left", x=0, font=dict(size=11)),
        xaxis=dict(showgrid=True, gridcolor="#e5e7eb", zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="#eef2f7", zeroline=False),
    )
    return plot(fig, include_plotlyjs=True, output_type="div", config={"displaylogo": False, "responsive": True})


def _video_cards(prepared_videos: list[PreparedVideo]) -> str:
    if not prepared_videos:
        return '<div class="empty-state">未找到处理后视频。运行“二维姿态识别”并保存叠加视频后，报告会自动显示所有 *_pose.mp4。</div>'
    return "\n".join(
        f"""
        <article class="video-card">
          <div class="video-title">{html.escape(video.title)}</div>
          <video class="sync-video" controls preload="metadata">
            <source src="{html.escape(video.src)}" type="video/mp4">
            浏览器无法播放该视频。请查看 media 文件夹中的转码文件，或用 Edge/Chrome 打开本报告。
          </video>
          <div class="video-status"></div>
        </article>
        """
        for video in prepared_videos
    )


def _metric_selector(angle_cols: list[str], visible_columns: set[str]) -> str:
    items = []
    for index, column in enumerate(angle_cols):
        checked = " checked" if column in visible_columns else ""
        info = coordinate_info(column)
        group = "lower" if info["label"].find("髋") >= 0 or info["label"].find("膝") >= 0 or info["label"].find("踝") >= 0 or info["label"].find("足") >= 0 else "upper"
        items.append(
            f"""
            <label class="metric-chip" title="{html.escape(info['definition'])}">
              <input type="checkbox" class="metric-toggle" data-trace-index="{index}" data-column="{html.escape(column)}" data-group="{group}"{checked}>
              <span>{html.escape(info['label'])}</span>
            </label>
            """
        )
    return "\n".join(items)


def _summary_records(data: pd.DataFrame, angle_cols: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for column in angle_cols:
        series = pd.to_numeric(data[column], errors="coerce")
        info = coordinate_info(column)
        minimum = float(series.min())
        maximum = float(series.max())
        mean = float(series.mean())
        records.append(
            {
                "column": column,
                "label": info["label"],
                "min": minimum,
                "max": maximum,
                "mean": mean,
                "rom": maximum - minimum,
                "plane": info["plane"],
                "neutral": info["neutral"],
                "direction": info["direction"],
                "definition": info["definition"],
                "boundary": info["boundary"],
                "raw": info["raw"],
            }
        )
    return records


def _stats_table(records: list[dict[str, Any]]) -> str:
    rows = []
    for index, record in enumerate(records):
        rows.append(
            f"""
            <tr>
              <td>
                <span>{html.escape(record['label'])}</span>
                <button class="info-icon" type="button" data-info-index="{index}" aria-label="查看 {html.escape(record['label'])} 的解释">i</button>
              </td>
              <td>{record['min']:.2f}</td>
              <td>{record['max']:.2f}</td>
              <td>{record['mean']:.2f}</td>
              <td>{record['rom']:.2f}</td>
              <td>{html.escape(record['plane'])}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def _quality_summary(data: pd.DataFrame, angle_cols: list[str], prepared_videos: list[PreparedVideo], translation_cols: list[str]) -> str:
    time_col = data.columns[0]
    frame_count = len(data)
    duration = float(data[time_col].iloc[-1] - data[time_col].iloc[0]) if frame_count > 1 else 0.0
    nan_values = int(data[[time_col] + angle_cols].isna().sum().sum())
    return (
        "质量诊断与解释边界：本报告基于 Pose2Sim/OpenSim 逆运动学 .mot 文件生成，只展示计算后的关节活动度。"
        f"当前报告包含 {frame_count} 个采样点、{duration:.2f} 秒、{len(angle_cols)} 个角度指标、{len(prepared_videos)} 个同步视频；"
        f"角度表中缺失值数量为 {nan_values}。平移坐标列 {len(translation_cols)} 个已从图表中排除。"
    )


def _quality_details(data: pd.DataFrame, angle_cols: list[str], prepared_videos: list[PreparedVideo], translation_cols: list[str]) -> str:
    time_col = data.columns[0]
    frame_count = len(data)
    duration = float(data[time_col].iloc[-1] - data[time_col].iloc[0]) if frame_count > 1 else 0.0
    nan_values = int(data[[time_col] + angle_cols].isna().sum().sum())
    return "\n".join(
        [
            "完整质量诊断与解释边界",
            "",
            f"1. 数据来源：本报告读取 OpenSim 逆运动学 .mot 文件，采样点 {frame_count} 个，时间范围 {duration:.2f} 秒。GUI 不从原始二维或三维坐标重新计算关节角。",
            f"2. 展示范围：图表和表格只展示非平移角度列；{len(translation_cols)} 个 *_tx/_ty/_tz 平移列已排除出关节活动度图表。",
            f"3. 缺失值：角度数据中检测到 {nan_values} 个缺失值。若缺失值较多，应回看二维识别、同步、三维重建和滤波结果。",
            f"4. 视频：报告中同步视频数量为 {len(prepared_videos)}。视频仅用于人工核对时间点和姿态，不参与本报告角度重新计算。",
            "5. 同步边界：若多机位视频没有硬件同步，动作中缺少明显同步事件，或者同步曲线不稳定，关节角时间对齐可能存在偏差。",
            "6. 校准边界：相机移动、内参/外参错误、棋盘格或场景点标定误差，会直接影响三维重建和 OpenSim IK 结果。",
            "7. 模型边界：0°/中立位、正负方向和关节自由度来自所用 .osim 模型坐标定义；不同 OpenSim 模型之间不应直接混用解释。",
            "8. 滤波边界：截止频率、异常值剔除和插值设置会改变峰值与活动度范围。快速动作应避免过低截止频率。",
            "9. 使用建议：正式分析前应检查处理后视频、同步诊断图、重投影误差、pose-3d .trc 连续性、kinematics 日志和异常峰值。",
            "10. 结论边界：本报告适合运动学趋势查看、质量核对和导出，不构成临床诊断或治疗建议。",
        ]
    )


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
    visible_columns = default_visible_columns(angle_cols)
    summary_records = _summary_records(data, angle_cols)
    rows: list[dict[str, Any]] = []
    for _, row in data[[time_col] + angle_cols].iterrows():
        values = {
            str(col): (None if pd.isna(row[col]) else float(row[col]))
            for col in [time_col] + angle_cols
        }
        rows.append(values)

    warning_html = "".join(f"<li>{html.escape(message)}</li>" for message in warnings)
    if warning_html:
        warning_html = f"<ul class=\"warnings\">{warning_html}</ul>"

    labels = {col: coordinate_label(col) for col in angle_cols}
    infos = {col: coordinate_info(col) for col in angle_cols}
    fig_div = _figure_html(data, angle_cols, visible_columns)
    duration = times[-1] - times[0] if len(times) > 1 else 0
    quality_summary = _quality_summary(data, angle_cols, prepared_videos, translation_cols)
    quality_details = _quality_details(data, angle_cols, prepared_videos, translation_cols)
    payload = {
        "times": times,
        "rows": rows,
        "timeColumn": str(time_col),
        "angleColumns": angle_cols,
        "labels": labels,
        "infos": infos,
        "summaryRecords": summary_records,
        "defaultVisible": sorted(visible_columns),
        "qualityDetails": quality_details,
        "translationColumns": translation_cols,
    }

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
      --danger: #b42318;
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
      padding: 18px 24px 16px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 24px;
      font-weight: 700;
      letter-spacing: 0;
    }}
    .meta {{ color: var(--muted); font-size: 14px; }}
    .quality-row {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      max-width: 1280px;
    }}
    .quality-summary {{ margin: 0; color: var(--muted); max-width: 980px; }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(120px, 1fr));
      gap: 10px;
      margin-top: 14px;
      max-width: 1280px;
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
      grid-template-columns: minmax(360px, 0.9fr) minmax(560px, 1.15fr);
      gap: 16px;
      padding: 16px;
      align-items: start;
      max-width: 1600px;
      margin: 0 auto;
    }}
    .panel {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      min-width: 0;
      overflow: hidden;
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
    .chart-stack {{ display: flex; flex-direction: column; gap: 12px; }}
    #plotPanel {{ padding: 0 8px 34px; min-height: 420px; }}
    .video-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 12px;
      padding: 14px;
      max-height: 70vh;
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
    .video-status {{ margin-top: 6px; font-size: 12px; color: var(--danger); min-height: 16px; }}
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
    button:hover, .metric-chip:hover {{ border-color: var(--primary); background: var(--primary-soft); }}
    button:focus-visible, input:focus-visible {{ outline: 3px solid #b9d7ff; outline-offset: 1px; }}
    input {{ padding: 6px 10px; min-width: 180px; }}
    .current-time {{
      color: var(--accent);
      font-weight: 700;
      white-space: nowrap;
    }}
    .chart-bottom {{
      display: grid;
      grid-template-columns: minmax(320px, 1.15fr) minmax(280px, 0.85fr);
      border-top: 1px solid var(--line-soft);
    }}
    .selector-panel {{ padding: 12px 14px; }}
    .selector-actions {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }}
    .metric-list {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 8px;
      max-height: 132px;
      overflow: auto;
    }}
    .metric-chip {{
      display: flex;
      align-items: center;
      gap: 7px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #ffffff;
      padding: 7px 8px;
      font-size: 13px;
      cursor: pointer;
      min-height: 36px;
    }}
    .metric-chip input {{ min-width: auto; min-height: auto; }}
    .value-panel {{ margin-top: 0; border-left: 1px solid var(--line-soft); }}
    .table-wrap {{
      overflow: auto;
      border-top: 1px solid var(--line-soft);
    }}
    .current-values {{ max-height: 210px; }}
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
    .stats-section {{
      max-width: 1600px;
      margin: 0 auto 24px;
      padding: 0 16px;
    }}
    .stats-table-wrap {{ max-height: 520px; overflow: auto; }}
    .info-icon {{
      min-height: 24px;
      width: 24px;
      height: 24px;
      border-radius: 50%;
      padding: 0;
      margin-left: 6px;
      color: var(--primary);
      font-weight: 700;
      line-height: 1;
    }}
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
    .modal-backdrop {{
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, 0.55);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
      z-index: 20;
    }}
    .modal-backdrop[hidden] {{ display: none; }}
    .modal {{
      width: min(760px, 100%);
      max-height: min(78vh, 720px);
      overflow: auto;
      background: #ffffff;
      border-radius: 8px;
      border: 1px solid var(--line);
    }}
    .modal-header {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line-soft);
    }}
    .modal-title {{ font-size: 18px; font-weight: 700; }}
    .modal-body {{ padding: 16px; white-space: pre-wrap; color: #26364d; }}
    @media (max-width: 1100px) {{
      main {{ grid-template-columns: 1fr; }}
      .summary {{ grid-template-columns: repeat(2, minmax(120px, 1fr)); }}
      .video-grid {{ max-height: none; }}
      #plotPanel {{ min-height: 360px; }}
      .chart-bottom {{ grid-template-columns: 1fr; }}
      .value-panel {{ border-left: none; border-top: 1px solid var(--line-soft); }}
    }}
    @media (max-width: 700px) {{
      header {{ padding: 16px; }}
      main {{ padding: 10px; }}
      .summary {{ grid-template-columns: 1fr 1fr; }}
      .quality-row {{ flex-direction: column; }}
      .panel-header {{ align-items: flex-start; flex-direction: column; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>关节活动度交互报告</h1>
    <div class="quality-row">
      <p class="quality-summary">{html.escape(quality_summary)}</p>
      <button id="qualityButton" type="button">查看完整诊断</button>
    </div>
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
          <div class="panel-title">同步视频</div>
          <div class="meta">视频文件已准备到报告目录的 media/，用于提高浏览器播放兼容性。</div>
        </div>
        <div class="toolbar">
          <button id="playAll" type="button">播放全部</button>
          <button id="pauseAll" type="button">暂停全部</button>
        </div>
      </div>
      <div class="video-grid">{_video_cards(prepared_videos)}</div>
    </section>
    <section class="panel chart-stack">
      <div class="panel-header">
        <div>
          <div class="panel-title">关节活动度曲线</div>
          <div class="meta">选择要显示的关节运动。图表只显示计算后的角度指标，不显示原始坐标和平移列。</div>
        </div>
        <div class="current-time" id="currentTime">时间：{times[0]:.3f} 秒</div>
      </div>
      <div id="plotPanel">{fig_div}</div>
      <div class="chart-bottom">
        <div class="selector-panel">
          <div class="selector-actions">
            <button class="select-action" type="button" data-action="all">全选</button>
            <button class="select-action" type="button" data-action="none">清空</button>
            <button class="select-action" type="button" data-action="lower">下肢</button>
            <button class="select-action" type="button" data-action="upper">上肢/躯干</button>
          </div>
          <div class="metric-list" aria-label="选择曲线指标">{_metric_selector(angle_cols, visible_columns)}</div>
        </div>
        <section class="value-panel">
          <div class="panel-header">
            <div><div class="panel-title">当前时刻关节活动度</div><div class="meta">单位：度</div></div>
            <input id="filterInput" type="search" placeholder="筛选当前表">
          </div>
          <div class="table-wrap current-values">
            <table>
              <thead><tr><th>指标</th><th>活动度</th></tr></thead>
              <tbody id="angleTable"></tbody>
            </table>
          </div>
        </section>
      </div>
    </section>
  </main>
  <section class="stats-section">
    <section class="panel">
      <div class="panel-header">
        <div>
          <div class="panel-title">完整统计表</div>
          <div class="meta">所有计算后关节活动度指标按从上到下、左到右排序。点击指标旁的 i 查看解释边界。</div>
        </div>
      </div>
      <div class="stats-table-wrap">
        <table>
          <thead><tr><th>指标</th><th>最小值</th><th>最大值</th><th>平均值</th><th>活动度范围</th><th>运动平面</th></tr></thead>
          <tbody>{_stats_table(summary_records)}</tbody>
        </table>
      </div>
    </section>
  </section>
  <div id="modalBackdrop" class="modal-backdrop" hidden>
    <section class="modal" role="dialog" aria-modal="true" aria-labelledby="modalTitle">
      <div class="modal-header">
        <div id="modalTitle" class="modal-title">说明</div>
        <button id="modalClose" type="button">关闭</button>
      </div>
      <div id="modalBody" class="modal-body"></div>
    </section>
  </div>
  <script id="motionData" type="application/json">{json.dumps(payload, ensure_ascii=False)}</script>
  <script>
    const payload = JSON.parse(document.getElementById('motionData').textContent);
    const tableBody = document.getElementById('angleTable');
    const currentTime = document.getElementById('currentTime');
    const videos = Array.from(document.querySelectorAll('.sync-video'));
    const plotNode = document.querySelector('.plotly-graph-div');
    const filterInput = document.getElementById('filterInput');
    const modalBackdrop = document.getElementById('modalBackdrop');
    const modalTitle = document.getElementById('modalTitle');
    const modalBody = document.getElementById('modalBody');
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

    function selectedColumns() {{
      return Array.from(document.querySelectorAll('.metric-toggle'))
        .filter((input) => input.checked)
        .map((input) => input.dataset.column);
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

    function applyMetricVisibility() {{
      if (!plotNode) return;
      document.querySelectorAll('.metric-toggle').forEach((input) => {{
        const visible = input.checked ? true : 'legendonly';
        Plotly.restyle(plotNode, {{ visible: [visible] }}, [Number(input.dataset.traceIndex)]);
      }});
    }}

    function setMetricGroup(mode) {{
      document.querySelectorAll('.metric-toggle').forEach((input) => {{
        if (mode === 'all') input.checked = true;
        if (mode === 'none') input.checked = false;
        if (mode === 'lower') input.checked = input.dataset.group === 'lower';
        if (mode === 'upper') input.checked = input.dataset.group === 'upper';
      }});
      applyMetricVisibility();
    }}

    function openModal(title, body) {{
      modalTitle.textContent = title;
      modalBody.textContent = body;
      modalBackdrop.hidden = false;
      document.getElementById('modalClose').focus();
    }}

    function closeModal() {{
      modalBackdrop.hidden = true;
    }}

    document.getElementById('playAll').addEventListener('click', () => {{
      videos.forEach((video) => video.play().catch(() => undefined));
    }});
    document.getElementById('pauseAll').addEventListener('click', () => {{
      videos.forEach((video) => video.pause());
    }});
    videos.forEach((video) => {{
      video.addEventListener('error', () => {{
        const status = video.closest('.video-card')?.querySelector('.video-status');
        if (status) status.textContent = '该视频仍无法播放。请检查 media 文件夹中的 MP4 是否可用，或安装/启用 ffmpeg 后重新生成报告。';
      }});
    }});
    document.querySelectorAll('.metric-toggle').forEach((input) => {{
      input.addEventListener('change', applyMetricVisibility);
    }});
    document.querySelectorAll('.select-action').forEach((button) => {{
      button.addEventListener('click', () => setMetricGroup(button.dataset.action));
    }});
    document.querySelectorAll('.info-icon').forEach((button) => {{
      button.addEventListener('click', () => {{
        const record = payload.summaryRecords[Number(button.dataset.infoIndex)];
        openModal(record.label, [
          `运动平面：${{record.plane}}`,
          `0°位/中立位：${{record.neutral}}`,
          `数值方向：${{record.direction}}`,
          `计算定义：${{record.definition}}`,
          `解释边界：${{record.boundary}}`,
          `原始列名：${{record.raw}}`
        ].join('\\n\\n'));
      }});
    }});
    document.getElementById('qualityButton').addEventListener('click', () => {{
      openModal('质量诊断与解释边界', payload.qualityDetails);
    }});
    document.getElementById('modalClose').addEventListener('click', closeModal);
    modalBackdrop.addEventListener('click', (event) => {{
      if (event.target === modalBackdrop) closeModal();
    }});
    document.addEventListener('keydown', (event) => {{
      if (event.key === 'Escape') closeModal();
    }});
    filterInput.addEventListener('input', renderTable);
    updateAt(0);
    applyMetricVisibility();
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
