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

## 推荐项目结构

Pose2Sim 不使用统一的 `input/output` 源码目录作为标准输入输出。每次分析建议建立一个独立项目：

```text
我的项目/
  Config.toml
  videos/
    cam01.mp4
    cam02.mp4
  calibration/
    Calib.toml 或 intrinsics/、extrinsics/
  reports/
```

`videos/` 和 `calibration/` 是输入；Pose2Sim 会自动生成 `pose/`、`pose-sync/`、`pose-3d/`、`kinematics/` 等结果；本 GUI 生成的 HTML 和 Excel 默认放入 `reports/`。

## 主要功能

- 中文桌面 GUI。
- 每个常用参数右侧有“？”按钮，可弹出专业说明。
- 可复制 Pose2Sim 内置示例配置新建项目。
- 可创建标准项目文件夹：`videos/`、`calibration/`、`reports/`。
- 可把已经录制好的视频导入项目 `videos/`。
- 支持运行 Pose2Sim 八个主流程：相机校准、二维姿态识别、多相机同步、人物匹配、三维重建、轨迹滤波、虚拟标记点增强、OpenSim 运动学。
- 支持高级 `Config.toml` 直接编辑。
- 支持从 `kinematics/*.mot` 生成 Excel 与交互式 HTML 报告。

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
