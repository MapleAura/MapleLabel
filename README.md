# MapleLabel

一个轻量、直观的桌面图像标注工具（PySide6），支持矩形、点、多边形标注，分组与属性编辑，并内置可扩展的自动化标注（AI 预标注）面板。适配 LabelMe 风格 JSON 格式，开箱即用。

## 安装

- 环境要求：
  - Windows（推荐），Python 3.10+
  - 推荐使用虚拟环境隔离依赖

- 克隆或下载本项目后，在项目根目录执行：

```bash
# 1) 创建并激活虚拟环境（Windows PowerShell 示例）
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) 安装依赖
pip install -r requirements.txt

# 如需GPU推理（可选），请安装 onnxruntime-gpu 替代CPU版
# pip install onnxruntime-gpu
```

- 模型：
  - 人脸关键点/检测模型已预置于 `models/face_landmark.onnx`
  - 若需要自定义或更新模型，替换该文件并保持同名或在模块中调整路径。

## 运行

在项目根目录运行：

```bash
python main.py
```

应用将以深色主题启动，主界面包含：左侧工具栏、中间标注画布、右侧属性/元素概览/文件列表面板。

## 基本功能

- 矩形、点、多边形标注：在画布上直接绘制与编辑
- 分组与取消分组：对多个元素进行分组管理，显示分组边界框
- 属性面板：针对选中元素，展示坐标与属性（下拉框）
- 文件列表：显示目录中的图片，标注状态（JSON/临时文件）可视化
- 自动保存：修改后自动写入临时 JSON（用户目录 `~/.maplabel_temp`），列表以橙点指示
- 撤销/恢复：内置撤销栈（`Ctrl+Z` / `Ctrl+Y`）
- 适配视图：一键使图像适配画布（`F`）
- 导航：上一张/下一张（`Alt+Left` / `Alt+Right`）

## 工具与快捷键

- 选择：`S`
- 画框（矩形）：`R`
- 画点：`P`
- 多边形：`O`（左键添加顶点，双击闭合，`Esc` 取消）
- 分组：`G`（对当前选中多个元素进行分组）
- 取消分组：`U`
- 删除：`E` 或 `Delete`
- 撤销/恢复：`Ctrl+Z` / `Ctrl+Y`
- 打开目录：`Ctrl+O`
- 保存：`Ctrl+S`（写入 LabelMe 风格 JSON）
- 自动保存（临时）：`Ctrl+Shift+S`（通常无需手动执行，变更时会自动写临时）
- 适应画布：`F`
- 上一张/下一张：`Alt+Left` / `Alt+Right`
- AI 面板：左侧工具栏点击“AI”

## 如何使用

1. 准备图片目录（包含 `.jpg/.jpeg/.png`），可选：放置一个 `label.json` 用于配置属性选项；例如：

```json
{
  "version": "1.0",
  "shapes": {
    "rectangle": {
      "face": []
    },
    "point": {
      "point_type": [
        "left_eye",
        "right_eye",
        "nose",
        "left_mouth",
        "right_mouth"
      ]
    }
  }
}
```

2. 启动应用后，点击左侧“打开目录”或使用 `Ctrl+O` 选择该图片目录。
3. 选择图片，使用工具进行标注：
   - 矩形：左键拖拽绘制，拖动控制手柄调整
   - 点：左键单击添加
   - 多边形：左键逐点添加，双击闭合
4. 右侧“属性面板”中，针对当前选中元素使用下拉框修改属性值（取自 `label.json` 中该形状的配置）。
5. 保存标注：点击“保存”或 `Ctrl+S`，在图片同名路径生成 `*.json`（LabelMe 风格）。

- 临时文件与自动保存：
  - 变更后会自动保存到用户临时目录：`%USERPROFILE%\.maplabel_temp\temp_<文件名>.json`
  - 文件列表中橙色圆点表示存在临时标注；正式保存后会清除对应临时文件并更新状态

## JSON 格式（输出）

保存后的 JSON 结构遵循 LabelMe 风格（部分字段扩展）：

- 顶层：`version`, `flags`, `shapes`, `imagePath`, `imageData`, `imageHeight`, `imageWidth`
- `shapes` 列表中每个元素包含：
  - `label`: 文本标签（如 `face`、`point`）
  - `shape_type`: `rectangle` | `point` | `polygon`
  - `points`: 坐标数组
    - 矩形：两个点 `[x1,y1], [x2,y2]`
    - 点：一个点 `[[x,y]]`
    - 多边形：顶点序列 `[[x,y], ...]`
  - `group_id`: 分组编号（同一组的元素共享）
  - `description`: 预留文本描述
  - `flags`: 额外标志或属性（多边形兼容）
  - `attributes`: 结构化属性字典（若元素类支持）
  - `mask`: 预留字段，当前为 `null`
- `imageData`: 默认为 `null`（不嵌入 Base64，以便版本管理与体积控制）

## 自动化标注（AI 预标注）

MapleLabel 支持模块化的自动化标注，在 `src/autolabel` 目录下按模块文件实现并注册，当前内置示例：`FaceLandmark`。

- 打开 AI 面板：左侧“AI”按钮
- 刷新：点击“刷新”，扫描并载入可用模块
- 勾选模块：如 `FaceLandmark`（首次勾选会初始化模型与推理会话）
  - 依赖 `models/face_landmark.onnx`
  - 自动选择 `CUDAExecutionProvider`（若安装了 GPU 版 onnxruntime）或回退 `CPUExecutionProvider`
- 自动排队与执行：
  - 对“尚未存在正式标注”的图片，自动排队并执行预标注
  - 当前图片可点击“立即运行”强制执行（无论是否已有标注）
- 结果写入：
  - 预标注结果会写入临时 JSON：`%USERPROFILE%\.maplabel_temp\temp_<文件名>.json`
  - 当切换到该图片且不存在人工标注时，画布会自动加载临时结果进行编辑
  - 用户确认后点击“保存”写入正式 `*.json` 并清理临时文件

### FaceLandmark 模块说明

- 功能：人脸检测与五点关键点（双眼、鼻、左右嘴角）
- 依赖：`numpy`、`opencv-python`、`onnxruntime`（或 `onnxruntime-gpu`）
- 输出示例（简化）：
  - 一个 `rectangle` 表示人脸框（含 `score`）
  - 五个 `point` 表示关键点（`label` 为 `left_eye`/`right_eye`/`nose`/`left_mouth`/`right_mouth`）
- 可配置项（见模块源码 `src/autolabel/face_landmark.py`）：
  - `conf_thresh`, `iou_thresh`, `min_face_size`, `input_size`, `include_image_data`

## 进阶：属性配置（label.json）

- 放置于图片目录根的 `label.json` 可为不同形状类型设定属性选项。
- 结构：
  - 顶层 `shapes` 下，按 `rectangle`/`point`/`polygon` 分类，键为属性名，值为候选列表。
- 应用行为：
  - 选中元素时，右侧属性面板展示对应的下拉框；所选值写入元素的 `attributes` 或 `flags`（多边形兼容）。

## 常见问题

- 无法加载图像：确保所选目录存在图片（`.jpg/.jpeg/.png`）
- 图标缺失：`icons/` 目录需包含对应 SVG；缺失时会回退系统图标
- GPU 未生效：确认安装的是 `onnxruntime-gpu`，且设备/驱动支持；否则使用 CPU 推理
- 临时标注未显示：检查目录监视是否生效；重新打开目录或手动刷新（切图）

## 目录结构

```
MapleLabel/
  main.py
  requirements.txt
  pyproject.toml
  models/
    face_landmark.onnx
  src/
    app.py
    autolabel/
      face_landmark.py
    io/
      annotation_io.py
    widgets/
      annotation_view.py
      file_list_widget.py
    utils/
      registry.py
      icon_manager.py
  example/
    face/
      label.json
      face.json
```

## 快速体验

1) 打开应用并选择含图片的目录（可参考 `example/face` 放置自己的图片与 `label.json`）

2) 打开 AI 面板，勾选 `FaceLandmark`，切换图片观察自动预标注并编辑。

3) 点击保存，产出与图片同名的 `*.json` 标注文件。
