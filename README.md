# Pose2Sim 图形界面

这是一个面向 Windows 的 Pose2Sim 桌面图形界面。目标用户是不熟悉代码的运动生物力学使用者：通过界面选择项目、导入录制好的多机位视频、调节常用参数、运行 Pose2Sim 主流程，并从 OpenSim `.mot` 文件生成中文 HTML 交互报告和 Excel 关节角表。

## 快速启动

双击：

```bat
D:\Application\Biomechanics\Pose2sim\launch_pose2sim_gui.bat
```

启动脚本会使用：

```bat
D:\Application\Anaconda\envs\sports3d\python.exe
```

该环境应包含 Pose2Sim、OpenSim、PySide6、pandas、plotly、openpyxl。

## 软件目录与项目结构

本 GUI 固定在软件目录下创建本地工作文件夹：

```text
D:\Application\Biomechanics\Pose2sim\
  input\
    videos\         # 原始录制视频暂存
    calibration\    # 校准素材暂存
  output\
    pose2sim_results\
      <项目名>\
        reports\    # HTML 与 Excel 报告
        kinematics\ # .mot、.osim 等
        pose-3d\    # .trc 等
```

`input/` 和 `output/` 已被 `.gitignore` 忽略，不会推送到 GitHub。

每次分析仍建议建立一个独立 Pose2Sim 项目。普通用户不需要手写 `Config.toml`：在 GUI 中选择或新建一个项目文件夹后，如果里面没有 `Config.toml`，GUI 会自动复制 Pose2Sim 内置默认配置，并创建 `videos/`、`calibration/`、`reports/`。

```text
我的项目/
  Config.toml
  videos/
    cam01.mp4
    cam02.mp4
  calibration/
    Calib.toml 或 intrinsics/、extrinsics/
```

`videos/` 和 `calibration/` 是 Pose2Sim 读取的输入；Pose2Sim 会先在项目目录内生成 `pose/`、`pose-sync/`、`pose-associated/`、`pose-3d/`、`kinematics/` 等结果。GUI 新建项目默认放在 `D:\Application\Biomechanics\Pose2sim\output\pose2sim_results\<项目名>\`，因此结果会直接生成在那里；HTML 和 Excel 报告放在同一项目结果文件夹的 `reports\` 子目录。若选择外部项目，GUI 会同步一份结果到该 results 目录，但不会默认删除外部项目里的原始结果。

## 主要功能

- 中文桌面 GUI。
- 每个常用参数右侧有“？”按钮，可弹出专业说明。
- 选择或新建项目文件夹时可自动复制 Pose2Sim 内置默认配置，无需用户手写 `Config.toml`。
- 可创建标准项目文件夹：`videos/`、`calibration/`、`reports/`。
- 可把已经录制好的视频导入项目 `videos/`。
- 支持运行 Pose2Sim 八个主流程：相机校准、二维姿态识别、多相机同步、人物匹配、三维重建、轨迹滤波、虚拟标记点增强、OpenSim 运动学。
- 支持高级 `Config.toml` 直接编辑。
- 流程成功结束后自动把 Pose2Sim 结果集中到 `output\pose2sim_results\<项目名>\`，包括 `kinematics/*.mot`、`*.osim` 和 `pose-3d/*.trc` 等。
- 流程成功结束后自动从 `kinematics/*.mot` 生成 Excel 与交互式 HTML 报告；报告放在 `output\pose2sim_results\<项目名>\reports\`，报告页也可手动重新生成。
- HTML 报告优先使用 Pose2Sim 生成的处理后视频 `pose/*_pose.mp4`，会把视频准备到报告目录的 `media/` 子文件夹并尽量转为浏览器兼容 MP4。

## 关于摄像头实时录制

Pose2Sim 的常规工作流是处理已经录制好的多机位视频，并通过校准、同步、三维重建和 OpenSim 运动学得到结果。本 GUI 当前也采用这一工作流：导入录制好的视频和校准素材后再分析。

当前版本不直接连接多台摄像头进行实时录制、实时同步或实时校准。若需要采集端一体化，建议使用相机厂商软件、OBS/ffmpeg、Qualisys/Vicon/OptiTrack、Caliscope、FreeMoCap、OpenCap 等工具完成采集和/或校准，再把视频与校准文件导入本 GUI。

## 命令行

启动 GUI：

```powershell
D:\Application\Anaconda\envs\sports3d\python.exe -m pose2sim_gui
```

查看版本：

```powershell
D:\Application\Anaconda\envs\sports3d\python.exe -m pose2sim_gui --version
```

运行测试：

```powershell
D:\Application\Anaconda\envs\sports3d\python.exe -m unittest discover -s tests
```

## 详细说明

见 [docs/中文使用说明.md](docs/中文使用说明.md)。

## 新手向导工作流

当前版本把普通用户流程调整为“向导优先”：

1. 在“向导”页选择或新建项目，GUI 会自动创建 `Config.toml` 和标准文件夹。
2. 导入正式动作视频到 `videos/`。
3. 点击“创建校准文件夹”，GUI 会根据视频名创建 `calibration/intrinsics/<相机名>/` 与 `calibration/extrinsics/<相机名>/`。
4. 普通手机项目先补拍/导入校准素材：每台相机的棋盘格内参素材，以及固定机位后的 scene 场景点外参素材。
5. 在校准向导中填写棋盘格参数、外参方法和 3D 场景点，保存到 `Config.toml`。
6. 先运行“校准”生成 `calibration/*.toml`，再运行“只检查 2D/同步”，最后运行“完整 3D + 报告”。

没有 `calibration/*.toml` 时，GUI 会禁用完整 3D/OpenSim 流程。此时只能做 2D 姿态识别和同步质量检查，不能生成可信的 3D 轨迹或关节活动度。

本 GUI 不连接手机或摄像头做实时录制、硬件同步或实时校准。它处理已经录制好的多机位视频，并通过 Pose2Sim 完成后处理分析。
