from __future__ import annotations


STAGE_LABELS: dict[str, str] = {
    "calibration": "相机校准",
    "poseEstimation": "二维姿态识别",
    "synchronization": "多相机同步",
    "personAssociation": "人物匹配",
    "triangulation": "三维重建",
    "filtering": "轨迹滤波",
    "markerAugmentation": "虚拟标记点增强",
    "kinematics": "OpenSim 运动学",
}


HELP_TEXTS: dict[str, str] = {
    "project_folder": (
        "Pose2Sim 的分析对象是一个项目文件夹。单次分析通常包含 Config.toml、videos/ 和 calibration/。"
        "videos/ 放多个相机录制的视频；calibration/ 放相机校准文件或用于计算校准的图像/视频。"
        "Pose2Sim 会在项目中生成 pose/、pose-sync/、pose-3d/、kinematics/ 等结果文件夹。"
    ),
    "create_folders": (
        "创建 Pose2Sim 推荐的标准项目文件夹：videos、calibration、reports。"
        "其中 videos 和 calibration 是 Pose2Sim 输入；reports 仅作为项目内备用记录目录。"
        "本 GUI 会另外在软件目录下创建 input/ 和 output/；新建项目默认建议放入 output/pose2sim_results。"
        "HTML 和 Excel 报告会保存在同一项目结果文件夹的 reports/ 子目录。"
    ),
    "import_videos": (
        "把已经录制好的多机位视频复制到当前项目的 videos/ 文件夹。Pose2Sim 支持处理录制好的视频，"
        "前提是每个相机的视频能对应到同一段动作，并且项目有可用的校准信息。建议把视频命名为 cam01.mp4、cam02.mp4 这类稳定名称。"
    ),
    "multi_person": "启用多人分析。若画面中有多名参与者，应启用；若只有一个主要被试，关闭会让流程更简单。多人分析会增加人物匹配和三维重建的复杂度。",
    "participant_height": "被试身高，单位米。可填 auto、单个数值如 1.72，或多人列表如 [1.72, 1.68]。主要用于虚拟标记点增强和 OpenSim 模型缩放；身高越准确，模型尺度越可靠。",
    "participant_mass": "被试体重，单位千克。逆运动学角度本身通常不依赖体重，但后续若做动力学、力、力矩或肌肉分析，体重会影响模型物理量。",
    "frame_rate": "视频帧率。推荐保留 auto，让 Pose2Sim 从视频读取；若读取失败，可手动填写实际帧率。多个相机最好使用相同帧率，快速运动建议至少 60 fps。",
    "frame_range": "分析帧范围。auto 会尝试保留有效动作段；all 分析全部帧；也可填 [起始帧, 结束帧]。长视频建议先截取关键段以提高速度并减少错误。",
    "pose_model": "二维姿态模型。Body_with_feet 是默认全身+足部模型，适合大多数人体动作；Whole_body 会包含手和脸但更慢；Body 更快但缺少足部点，可能影响标记点增强。",
    "pose_mode": "RTMPose 模型规模。lightweight 速度快但精度低；balanced 是默认折中；performance 更慢但通常更稳。初学者建议 balanced。",
    "device": "计算设备。auto 会自动选择；CPU 最稳定但较慢；CUDA 适合 NVIDIA GPU；MPS/ROCM 用于特定平台。设备选择不改变理论结果，只影响速度和兼容性。",
    "backend": "模型推理后端。auto 通常即可。openvino 常适合 CPU，onnxruntime 兼容性好，opencv 可作为备选。若某个后端报错，可切换后端。",
    "det_frequency": "人体检测间隔。每 N 帧重新检测一次人体，中间帧跟踪人体框。数值越大越快，但多人、遮挡或快速运动时更容易丢失目标。",
    "average_likelihood": "姿态置信度阈值。低于该平均置信度的人体检测会被丢弃。提高可减少误检，但可能丢掉遮挡严重的真实动作。",
    "display_detection": "实时显示姿态识别窗口。便于检查识别是否正常，但会降低速度；开启时本 GUI 会避免并行姿态估计冲突。",
    "overwrite_pose": "是否覆盖已有二维姿态结果。关闭可复用之前计算结果，节省时间；改变视频或姿态参数后应开启。",
    "save_video": "保存姿态叠加结果。to_video 保存叠加视频，便于人工检查；to_images 保存逐帧图片，占空间更大；none 不保存可节省空间。",
    "tracking_mode": "二维检测跟踪方式。sports2d 是默认且较快；none 不跟踪；deepsort 在拥挤场景更稳但更慢且依赖更多包。",
    "synchronization_gui": "多相机同步交互窗口。若相机不是硬件同步，建议开启，用明显的垂直动作辅助同步。若相机已硬件同步，可关闭或跳过同步阶段。",
    "display_sync_plots": "显示同步诊断图。用于判断各相机时间偏移估计是否合理，调试时建议开启。",
    "save_sync_plots": "保存同步诊断图。建议开启，便于以后检查同步质量或记录处理过程。",
    "calibration_type": "校准方式。convert 表示已有 Qualisys、OpenCap、EasyMocap 等校准文件并转换；calculate 表示用棋盘格/场景点从头计算相机内外参。",
    "convert_from": "已有校准文件来源。应与 calibration/ 中的文件格式一致。选错会导致校准转换失败或坐标系错误。",
    "intrinsics_extension": "内参校准文件扩展名，例如 jpg、png、mp4。用于从 calibration/intrinsics 中读取每个相机的棋盘格图像或视频。",
    "extrinsics_method": "外参校准方法。scene 通过已知三维场景点手动点击，通常精度高且可用于旧视频；board 用地面棋盘格；keypoints 在当前 Pose2Sim 文档中仍标为未完成，本 GUI 不在新手页开放。",
    "tracked_keypoint": "单人模式下跟踪目标的关键点。Neck 通常稳定；如果所选姿态模型没有 Neck，应改为肩、髋等稳定点名称。",
    "reproj_assoc": "人物匹配重投影误差阈值，单位像素。值越小越严格，能减少错误匹配但可能找不到人；值越大越宽松，但多人场景更容易串人。",
    "reproj_triangulation": "三维重建重投影误差阈值，单位像素。低阈值更严格，结果更干净但缺失更多；高阈值保留更多点但可能引入错误三维点。",
    "min_cameras": "参与三角化的最少相机数。最少为 2；相机越多且遮挡越少，三维结果越可靠。复杂动作建议 3 台以上。",
    "interpolation": "缺失点插值方式。linear 最稳健；高阶插值可能更平滑但对噪声敏感；none 不填补缺失点，后续 OpenSim 可能失败。",
    "reject_outliers": "Hampel 异常值剔除。用于先移除明显跳点，通常建议开启；长视频会稍慢。",
    "filter_enabled": "是否对三维轨迹继续滤波。通常建议开启；关闭会保留原始三维重建噪声。",
    "filter_type": "滤波方法。butterworth 是生物力学常用低通滤波；kalman/one_euro 适合实时或近实时；gcv_spline 自动性更强；median/gaussian/LOESS 可用于特定噪声。",
    "filter_cutoff": "Butterworth 截止频率，单位 Hz。越低越平滑但可能削弱真实快速动作；越高保留动作细节但噪声更多。人体常见动作可从 6 Hz 起试。",
    "filter_order": "Butterworth 滤波阶数。4 阶是常用默认值；阶数过高可能引入不必要的信号变化。",
    "display_figures": "显示滤波前后对比图。调参时建议开启，批量处理时可关闭。",
    "save_filt_plots": "保存滤波诊断图。建议保留，方便追踪每次处理质量。",
    "feet_on_floor": "虚拟标记点增强后是否把足部平移到地面。若需要地面反力或负载分析可能有用；普通关节角分析通常可保持默认。",
    "use_augmentation": "OpenSim 运动学是否使用 LSTM 估计的虚拟标记点。相机少时可能更稳定；若增强结果不理想，可关闭直接使用原三维关键点。",
    "use_simple_model": "是否使用简化 OpenSim 模型。速度可明显提升，但没有肌肉和部分复杂约束；只看基本关节角时可考虑开启。",
    "right_left_symmetry": "模型缩放时是否假设左右对称。大多数健康被试建议开启；若有假肢、明显畸形或单侧器械，应关闭。",
    "default_height": "自动估计身高失败时使用的默认身高，单位米。建议填真实身高或接近值，避免 OpenSim 模型缩放偏差。",
    "mot_file": "OpenSim 逆运动学输出的 .mot 文件，包含随时间变化的关节角和平移坐标。本 GUI 的 HTML 和 Excel 报告以它为数据源。",
    "report_video": "HTML 报告会自动使用全部报告视频，不需要逐个选择。优先使用 Pose2Sim 二维姿态阶段生成的 pose/*_pose.mp4；没有处理后视频时才回退到项目 videos/ 中的原始视频。报告会把视频复制/转码到报告目录 media/，以提高 Edge/Chrome 播放兼容性。",
    "stage_calibration": "读取或计算相机内参和外参，输出 calibration/Calib.toml。没有正确校准，三维重建和关节角都不可信。",
    "stage_poseEstimation": "对 videos/ 中每个相机视频运行二维姿态识别，输出逐帧关键点 JSON，并可保存叠加视频。",
    "stage_synchronization": "估计不同相机之间的时间偏移，并生成同步后的二维姿态文件。非硬件同步录制时非常关键。",
    "stage_personAssociation": "多相机、多人物情况下，把不同视角中的同一人关联起来。单人场景也可用于选择目标人物。",
    "stage_triangulation": "根据校准和二维关键点进行三角化，输出 pose-3d/*.trc 三维标记轨迹。",
    "stage_filtering": "对三维 .trc 轨迹或设置后对 IK .mot 角度结果滤波，降低噪声和异常跳点。",
    "stage_markerAugmentation": "用 LSTM 从关键点估计 OpenSim 更需要的虚拟标记点，输出增强后的三维标记轨迹。",
    "stage_kinematics": "自动缩放 OpenSim 模型并运行逆运动学，输出 kinematics/*_scaled.osim 和 *.mot 关节角文件。",
}


MANUAL_TEXT = """
# Pose2Sim 中文使用说明

## 1. 推荐项目结构

每个分析项目应是一个独立文件夹。单次分析推荐结构：

```
我的项目/
  Config.toml
  videos/
    cam01.mp4
    cam02.mp4
  calibration/
    Calib.toml 或 intrinsics/、extrinsics/
  reports/              # 项目内备用记录目录
```

本 GUI 会在软件目录 `D:\\Application\\Biomechanics\\Pose2sim` 下自动创建：

- `input/`：用户原始视频、校准素材等输入文件的暂存位置。
- `input/videos/`：导入视频时的默认选择位置，可作为原始视频暂存区。
- `input/calibration/`：校准素材暂存区。
- `output/pose2sim_results/`：GUI 新建项目和 Pose2Sim 结果的集中位置，包含 `pose/`、`pose-sync/`、`pose-associated/`、`pose-3d/`、`kinematics/` 和 `reports/`。

Pose2Sim 本身仍然读取每个项目内的 `videos/` 与 `calibration/`。GUI 新建项目默认就在 `output/pose2sim_results/<项目名>/`，因此 Pose2Sim 结果会直接生成在那里，报告放在同一项目的 `reports/` 子目录。若打开外部项目，GUI 会同步一份结果到 `output/pose2sim_results/<项目名>/`，但不会自动删除外部项目中的原始结果。

## 2. 录制好的视频是否支持

支持。Pose2Sim 的常规工作流就是处理已经录制好的多相机视频。把同一次动作的多个相机视频复制到项目 `videos/` 中，然后运行二维姿态识别、同步、人物匹配、三维重建和运动学。

关键前提：

- 多台相机拍到同一段动作，最好帧率一致，尽量不要自动变帧率。
- 若没有硬件同步，需要动作中有明显的快速垂直运动，例如跳一下、快速抬手，供同步算法估计时间偏移。
- 相机位置一旦移动，外参需要重新校准；相机镜头/焦距/分辨率变化时，内参也应重新校准。
- `calibration/` 中应有可转换的校准文件，或有用于计算内参/外参的棋盘格、场景点图像/视频。

## 3. 推荐操作流程

1. 在“项目”页选择或新建项目。
2. 点击“创建标准文件夹”，确保存在 `videos/`、`calibration/`、`reports/`。
3. 点击“导入录制视频”，把多机位视频复制到 `videos/`。
4. 在“参数”页先使用新手参数；只有明确知道含义时再改高级 TOML。
5. 在“流程”页按顺序运行：相机校准、二维姿态识别、多相机同步、人物匹配、三维重建、轨迹滤波、虚拟标记点增强、OpenSim 运动学。
6. 运行流程成功结束后，GUI 会自动同步 Pose2Sim 结果，并从 `kinematics/*.mot` 生成 Excel 与 HTML。也可以在“报告”页手动重新生成。

## 4. Pose2Sim 会输出什么

完成 OpenSim 运动学后，Pose2Sim 会在 `kinematics/` 中输出：

- `*_scaled.osim`：按被试尺度缩放后的 OpenSim 模型。
- `*.mot`：OpenSim 逆运动学得到的关节角/坐标时间序列。
- `opensim_logs.txt`：OpenSim 处理日志。

三维点轨迹通常在 `pose-3d/` 中以 `.trc` 保存。

## 5. 本 GUI 的覆盖范围

本 GUI 覆盖 Pose2Sim 主流程：项目管理、常用参数、完整 TOML 编辑、八个 pipeline 阶段、视频导入、日志查看、HTML/Excel 报告。高级页允许访问完整 `Config.toml`，所以没有被新手页表单覆盖的 Pose2Sim 参数仍然可以编辑。

当前不在新手页开放的内容：自定义 RTMlib 模型字典、未实现的左右交换/畸变处理/移动相机、keypoints 外参自动校准、手工编辑自定义骨架树。这些功能容易误设或在 Pose2Sim 文档中仍属实验/未完成，保留在高级 TOML 中由熟悉参数的人使用。
"""
