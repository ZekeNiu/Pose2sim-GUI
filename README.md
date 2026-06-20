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

每次分析仍建议建立一个独立 Pose2Sim 项目：

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
- 可复制 Pose2Sim 内置示例配置新建项目。
- 可创建标准项目文件夹：`videos/`、`calibration/`、`reports/`。
- 可把已经录制好的视频导入项目 `videos/`。
- 支持运行 Pose2Sim 八个主流程：相机校准、二维姿态识别、多相机同步、人物匹配、三维重建、轨迹滤波、虚拟标记点增强、OpenSim 运动学。
- 支持高级 `Config.toml` 直接编辑。
- 流程成功结束后自动把 Pose2Sim 结果集中到 `output\pose2sim_results\<项目名>\`，包括 `kinematics/*.mot`、`*.osim` 和 `pose-3d/*.trc` 等。
- 流程成功结束后自动从 `kinematics/*.mot` 生成 Excel 与交互式 HTML 报告；报告放在 `output\pose2sim_results\<项目名>\reports\`，报告页也可手动重新生成。
- HTML 报告优先使用 Pose2Sim 生成的处理后视频 `pose/*_pose.mp4`，会把视频准备到报告目录的 `media/` 子文件夹并尽量转为浏览器兼容 MP4。

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
