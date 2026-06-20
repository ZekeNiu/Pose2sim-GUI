from __future__ import annotations


MANUAL_TEXT = """
# Pose2Sim-GUI 中文使用说明

## 1. 正确工作流

推荐始终从“向导”页开始：

1. 选择或新建项目。普通用户不需要手写 `Config.toml`，GUI 会自动复制 Pose2Sim 默认配置并创建 `videos/`、`calibration/`、`reports/`。
2. 导入正式动作视频。每台相机一个视频，建议用稳定名称，例如 `front.mp4`、`back.mp4` 或 `cam01.mp4`、`cam02.mp4`。
3. 创建校准文件夹。GUI 会按视频名自动创建 `calibration/intrinsics/<相机名>/` 和 `calibration/extrinsics/<相机名>/`。
4. 准备并导入校准素材。普通手机新项目通常需要“棋盘格内参 + scene 场景点外参”。
5. 保存校准设置到 `Config.toml`，然后先运行“校准”，生成 `calibration/*.toml`。
6. 有了标定文件后，先运行“只检查 2D/同步”，确认人体识别和同步质量。
7. 最后运行“完整 3D + 报告”。成功后 GUI 会自动生成 Pose2Sim 结果、OpenSim `.mot/.osim`、HTML 和 Excel 报告。

## 2. Redmi / 普通手机如何校准

普通手机没有硬件同步和内置相机标定时，建议重新录一组完整素材：

- 固定手机位置、分辨率、帧率、横竖屏和焦距/曝光；校准后不要移动手机。
- 内参：每台手机单独拍棋盘格或 Charuco 标定板，让标定板覆盖画面不同位置、距离和倾斜角度。把素材放入 `calibration/intrinsics/<相机名>/`。
- 外参：手机固定后，推荐 `scene` 方法。在场地准备至少 10 个分散的可测量 3D 点，记录每个点的 X/Y/Z 坐标，校准时按 Pose2Sim 提示在每台相机画面中点击对应点。素材放入 `calibration/extrinsics/<相机名>/`。
- 正式动作：校准后不要移动手机，直接录正式动作。没有硬件同步时，在动作开头加入清晰同步事件，例如跳一下、快速抬手、拍手或闪光。
- 相机一旦移动，外参必须重做；分辨率、焦距、镜头或拍摄模式变化时，内参也应重做。

## 3. 为什么没有 Calib.toml 不能做完整 3D

Pose2Sim 的三维重建需要知道每台相机的内参、外参和相机之间的几何关系。没有 `calibration/*.toml` 时，软件最多只能做 2D 姿态识别和同步检查；人物匹配、三角化、滤波、虚拟标记点增强和 OpenSim 关节角都不应运行。

因此 GUI 会在没有标定文件时禁用“完整 3D + 报告”。这不是限制功能，而是防止生成没有几何依据的结果。

## 4. 是否支持实时连接多台手机录制

当前不支持。Pose2Sim 和本 GUI 的定位是处理已经录制好的多机位视频，不负责连接手机、实时录制、硬件触发、丢帧监控或实时相机校准。

如果需要采集端一体化，建议使用相机厂商软件、OBS/ffmpeg、Qualisys、Vicon、OptiTrack、Caliscope、FreeMoCap 或 OpenCap 等工具完成采集和/或校准，再把视频与标定文件导入本 GUI。

## 5. Pose2Sim 会输出什么

常见输出包括：

- `pose/`：每个视频的 2D 姿态 JSON，可能包含叠加人体关键点的视频。
- `pose-sync/`：同步后的 2D 姿态结果。
- `pose-associated/`：多视角人物匹配结果。
- `pose-3d/`：三维轨迹，通常包含 `.trc`。
- `kinematics/`：OpenSim 结果，通常包含 `*_scaled.osim`、`.mot` 和日志。
- `reports/`：本 GUI 自动生成的 HTML 交互报告和 Excel 关节活动度表。

GUI 新建项目时默认放在：

`D:\\Application\\Biomechanics\\Pose2sim\\output\\pose2sim_results\\<项目名>\\`

报告会放在同一项目结果文件夹的 `reports/` 子目录中，便于一次性查看。

## 6. 高级模式

“参数”页保留常用安全参数和完整 TOML 编辑；“流程/高级”页保留八个 Pose2Sim 阶段的手动勾选。高级模式适合调试和复用中间结果，但如果没有 `calibration/*.toml`，不要手动运行人物匹配、三维重建、滤波、虚拟标记点增强或 OpenSim 运动学。
"""
