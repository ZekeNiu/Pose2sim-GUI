# Pose2Sim GUI

Pose2Sim GUI is a Windows desktop front end for Pose2Sim. It lets a non-programmer open a Pose2Sim project, edit common parameters safely, run pipeline stages, and generate OpenSim joint-angle reports as HTML and Excel files.

## Quick Start

1. Double-click `launch_pose2sim_gui.bat`.
2. Choose a Pose2Sim project folder that contains `Config.toml`.
3. Use the beginner parameter page for common settings, or the advanced page to edit the full TOML file.
4. Select pipeline stages and click Run.
5. After OpenSim kinematics creates `kinematics/*.mot`, generate HTML and Excel reports from the Reports tab.

The launcher uses:

```bat
D:\Application\Anaconda\envs\sports3d\python.exe
```

That environment is expected to contain Pose2Sim, OpenSim, PySide6, pandas, plotly, and openpyxl.

## Command Line

Start the GUI:

```powershell
D:\Application\Anaconda\envs\sports3d\python.exe -m pose2sim_gui
```

Show environment information:

```powershell
D:\Application\Anaconda\envs\sports3d\python.exe -m pose2sim_gui --version
```

Run selected Pose2Sim stages:

```powershell
D:\Application\Anaconda\envs\sports3d\python.exe -m pose2sim_gui.runner --config C:\path\to\project --stages calibration poseEstimation kinematics
```

Generate reports:

```powershell
D:\Application\Anaconda\envs\sports3d\python.exe -m pose2sim_gui.reports --project C:\path\to\project
```

## Report Data Source

Reports use OpenSim inverse-kinematics `.mot` files created by Pose2Sim in each project's `kinematics` folder. Angle columns are exported to the main Excel sheet and plotted in the HTML report. Translation columns ending in `_tx`, `_ty`, or `_tz` are exported separately.

## Development Checks

Run tests with the same environment:

```powershell
D:\Application\Anaconda\envs\sports3d\python.exe -m unittest discover -s tests
```
