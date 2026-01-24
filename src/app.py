"""MapleLabel 主窗口模块。

该模块实现 `MapleLabelWindow`，负责应用主窗口布局、工具栏、右侧属性
面板与文件列表，以及与 `AnnotationView` 的交互。文档与类型注解使用中文，
以便静态检查与本地维护。
"""

import json
import os
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QSize, Qt, QFileSystemWatcher
from PySide6.QtGui import QAction, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .items import GroupItem, PointItem, PolygonItem, ResizableRectItem
from .utils import IconManager
from .utils.undo_manager import UndoRedoManager
from .widgets import AnnotationView, CollapsiblePanel, FileListWidgetItem


class MapleLabelWindow(QMainWindow):
    """主窗口类，封装 UI 布局与用户交互逻辑。"""

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("MapleLabel2.0")
        self.setGeometry(100, 100, 1200, 800)
        # 图标管理器
        self.icon_manager = IconManager()
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.main_layout = QHBoxLayout(main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 左侧面板
        self.create_left_panel()

        # 中心画布区域
        self.canvas = AnnotationView()
        self.canvas.setStyleSheet("background-color: #2D2D30;")
        # 撤销/重做管理器
        self.undo_manager = UndoRedoManager(self.canvas)
        # 使用 QSplitter 让右侧面板可调节宽度
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.canvas)

        # 右侧面板容器（使用不可折叠的容器，允许通过 splitter 自由调整宽度）
        self.right_panel = QFrame()
        self.right_panel.setFrameShape(QFrame.NoFrame)
        self.right_panel.setStyleSheet("background-color: #252526;")
        self.right_panel_layout = QVBoxLayout(self.right_panel)
        self.right_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.right_panel_layout.setSpacing(0)

        # 右上方面板 - 属性面板
        self.property_panel = QFrame()
        self.property_panel.setFrameShape(QFrame.StyledPanel)
        self.property_panel.setStyleSheet(
            """
            QFrame {
                background-color: #252526;
                border-bottom: 1px solid #1E1E1E;
            }
            QLabel {
                color: #D4D4D4;
                padding: 5px;
            }
        """
        )
        self.property_panel.setFixedHeight(200)
        self.property_layout = QVBoxLayout(self.property_panel)
        self.property_layout.addWidget(QLabel("属性面板"))
        # 表单布局用于展示选中项的属性
        self.property_form = QFormLayout()
        self.property_layout.addLayout(self.property_form)
        self.property_layout.addStretch()

        # 右下方面板 - 文件列表
        self.file_panel = QFrame()
        self.file_panel.setFrameShape(QFrame.StyledPanel)
        self.file_panel.setStyleSheet(
            """
            QFrame {
                background-color: #252526;
            }
        """
        )
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.SingleSelection)
        self.file_list.itemClicked.connect(self.on_file_selected)

        self.file_layout = QVBoxLayout(self.file_panel)
        self.file_layout.addWidget(QLabel("文件列表"))
        self.file_layout.addWidget(self.file_list)

        # 新增中间只读元素信息面板（展示当前图像所有元素信息）
        self.elements_panel = QFrame()
        self.elements_panel.setFrameShape(QFrame.StyledPanel)
        self.elements_panel.setStyleSheet(
            """
            QFrame { background-color: #252526; }
        """
        )
        self.elements_layout = QVBoxLayout(self.elements_panel)
        self.elements_layout.addWidget(QLabel("概览"))
        self.elements_table = QTableWidget()
        self.elements_table.setColumnCount(3)
        self.elements_table.setHorizontalHeaderLabels(["类型", "坐标", "属性"])
        self.elements_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.elements_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.elements_table.setStyleSheet("color: #D4D4D4;")
        self.elements_table.horizontalHeader().setStretchLastSection(True)
        self.elements_layout.addWidget(self.elements_table)

        # 将三个面板按顺序加入右侧容器：属性 / 元素列表 / 文件列表
        self.right_panel_layout.addWidget(self.property_panel)
        self.right_panel_layout.addWidget(self.elements_panel)
        self.right_panel_layout.addWidget(self.file_panel)

        # 将右侧面板加入 splitter，并把 splitter 放到主布局
        self.splitter.addWidget(self.right_panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        # 防止右侧被拖动到完全折叠，保证连贯的左右拖动
        try:
            self.right_panel.setMinimumWidth(20)
            # 阻止 splitter 将右侧（index 1）收缩为0
            self.splitter.setCollapsible(1, False)
        except Exception:
            pass
        self.main_layout.addWidget(self.splitter)

        # 绑定场景变化以更新元素列表（changed 会频繁触发）
        self.canvas.scene.changed.connect(self.update_elements_panel)
        # 场景变更时也更新属性面板中的坐标（实时响应拖动）
        self.canvas.scene.changed.connect(self.update_property_coords)

        # 存储当前 elements 表格行对应的 scene item 引用
        self.elements_row_items = []

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 | MapleLabel2.0 - 图像标注工具")

        self.selected_tool = None
        self.current_dir = ""
        self.current_image = None
        self.image_files = []
        self.current_image_index = -1
        # label.json 配置
        self.label_config = {}

        # 临时文件目录
        self.temp_dir = os.path.join(os.path.expanduser("~"), ".maplabel_temp")
        # 监视临时目录，若临时文件出现/删除则即时刷新文件列表
        self.temp_watcher = QFileSystemWatcher(self)
        # 仅在目录已存在时添加监视
        if os.path.exists(self.temp_dir):
            try:
                self.temp_watcher.addPath(self.temp_dir)
            except Exception:
                pass
        self.temp_watcher.directoryChanged.connect(self.on_temp_dir_changed)

        # 添加上下文菜单
        self.create_context_menu()

        # 添加快捷键
        self.create_shortcuts()

        # 绑定场景选择变化，用于更新属性面板
        self.canvas.scene.selectionChanged.connect(self.on_selection_changed)

    def closeEvent(self, event) -> None:
        """处理窗口关闭事件。"""
        if self.check_unsaved_changes():
            reply = QMessageBox.question(
                self,
                "保存更改",
                "您有未保存的更改。是否要在退出前保存？",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save,
            )

            if reply == QMessageBox.Save:
                # 保存所有未保存的更改
                self.save_all_unsaved()
                event.accept()
            elif reply == QMessageBox.Discard:
                # 不保存，直接退出
                self.canvas.clear_temp_files(self.temp_dir)
                event.accept()
            else:
                # 取消关闭
                event.ignore()
        else:
            # 没有未保存的更改，直接退出
            self.canvas.clear_temp_files(self.temp_dir)
            event.accept()

    def check_unsaved_changes(self) -> bool:
        """检查是否有未保存的更改，返回布尔值。"""
        # 检查当前图片是否有未保存的更改
        if self.canvas.has_unsaved_changes():
            return True

        # 检查临时目录中是否有未保存的临时文件
        if os.path.exists(self.temp_dir):
            temp_files = os.listdir(self.temp_dir)
            for temp_file in temp_files:
                if temp_file.startswith("temp_"):
                    # 提取原始图片名
                    image_name = temp_file[5:-5]  # 移除"temp_"和后缀".json"
                    # 查找对应的JSON文件
                    json_path = os.path.join(self.current_dir, f"{image_name}.json")
                    if not os.path.exists(json_path):
                        # 有临时文件但没有对应的JSON文件
                        return True
        return False

    def save_all_unsaved(self) -> None:
        """保存所有未保存的更改到工作目录或临时目录。"""
        if not self.current_dir:
            return

        # 保存当前图片
        if self.canvas.has_unsaved_changes() and self.current_image:
            self.save_annotations()

        # 保存临时目录中的其他文件
        if os.path.exists(self.temp_dir):
            temp_files = os.listdir(self.temp_dir)
            for temp_file in temp_files:
                if temp_file.startswith("temp_"):
                    # 提取原始图片名
                    image_name = temp_file[5:-5]  # 移除"temp_"和后缀".json"
                    file_name, extension = os.path.splitext(image_name)
                    # 查找对应的JSON文件路径
                    json_path = os.path.join(self.current_dir, f"{file_name}.json")

                    # 读取临时文件
                    temp_path = os.path.join(self.temp_dir, temp_file)
                    try:
                        with open(temp_path, "r", encoding="utf-8") as f:
                            temp_data = json.load(f)

                        # 保存到JSON文件
                        with open(json_path, "w", encoding="utf-8") as f:
                            json.dump(temp_data, f, indent=2, ensure_ascii=False)

                        # 删除临时文件
                        os.remove(temp_path)

                    except Exception as e:
                        print(f"保存临时文件时出错: {e}")

        # 更新文件列表状态
        self.update_file_list_status()

    def create_shortcuts(self) -> None:
        """创建并绑定应用快捷键。"""
        # 工具快捷键映射
        self.tool_shortcuts = {
            Qt.Key_S: "select",  # 选择工具
            Qt.Key_R: "rectangle",  # 矩形工具
            Qt.Key_P: "point",  # 点工具
            Qt.Key_O: "polygon",  # 多边形工具
            Qt.Key_E: "delete",  # 删除工具
            Qt.Key_G: "group",  # 分组工具
            Qt.Key_U: "ungroup",  # 取消分组工具
        }

        # 翻页快捷键
        self.prev_shortcut = QShortcut(QKeySequence("Alt+Left"), self)
        self.prev_shortcut.activated.connect(self.load_prev_image)

        self.next_shortcut = QShortcut(QKeySequence("Alt+Right"), self)
        self.next_shortcut.activated.connect(self.load_next_image)

        # 目录快捷键
        self.dir_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        self.dir_shortcut.activated.connect(self.open_directory)

        # 保存快捷键
        self.save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        self.save_shortcut.activated.connect(self.save_annotations)

        # 自动保存快捷键
        self.autosave_shortcut = QShortcut(QKeySequence("Ctrl+Shift+S"), self)
        self.autosave_shortcut.activated.connect(self.auto_save)

        self.fit_view_shortcut = QShortcut(Qt.Key_Z, self)  # 将 Qt.Key_Space 改为 Qt.Key_Z
        self.fit_view_shortcut.activated.connect(lambda: self.canvas.fit_to_view())

        # 撤销/重做快捷键
        self.undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.undo_shortcut.activated.connect(self.undo)

        self.redo_shortcut = QShortcut(QKeySequence("Ctrl+Y"), self)
        self.redo_shortcut.activated.connect(self.redo)

        # 为每个快捷键创建QShortcut
        for key, tool_name in self.tool_shortcuts.items():
            shortcut = QShortcut(key, self)
            shortcut.activated.connect(
                lambda t=tool_name: self.activate_tool_by_shortcut(t)
            )

    def undo(self) -> None:
        """执行撤销操作并显示状态。"""
        try:
            if hasattr(self, "undo_manager") and self.undo_manager:
                ok = self.undo_manager.undo()
                if ok:
                    self.status_bar.showMessage("已撤销 (Ctrl+Z)")
                    return
        except Exception:
            pass
        self.status_bar.showMessage("无可撤销操作")

    def redo(self) -> None:
        """执行重做操作并显示状态。"""
        try:
            if hasattr(self, "undo_manager") and self.undo_manager:
                ok = self.undo_manager.redo()
                if ok:
                    self.status_bar.showMessage("已恢复 (Ctrl+Y)")
                    return
        except Exception:
            pass
        self.status_bar.showMessage("无可恢复操作")

    def auto_save(self) -> None:
        """自动保存当前图片到临时文件（如果有修改）。"""
        if self.current_image and self.canvas.has_unsaved_changes():
            if self.canvas.save_annotations_to_temp(self.temp_dir):
                self.status_bar.showMessage(
                    f"已自动保存: {os.path.basename(self.current_image)}"
                )
                # 更新文件列表状态
                self.update_file_list_status(self.current_image_index)
                # 如果临时目录刚创建，确保被 QFileSystemWatcher 监视
                if os.path.exists(self.temp_dir):
                    try:
                        if self.temp_dir not in self.temp_watcher.directories():
                            self.temp_watcher.addPath(self.temp_dir)
                    except Exception:
                        pass
            else:
                self.status_bar.showMessage("自动保存失败")

    def activate_tool_by_shortcut(self, tool_name: str) -> None:
        """通过快捷键激活工具。"""
        if tool_name == "group":
            # 分组工具直接执行分组操作
            self.group_selected_items()
        elif tool_name == "ungroup":
            # 取消分组工具直接执行取消分组操作
            self.ungroup_selected_items()
        elif tool_name == "delete":
            # 删除工具直接执行删除操作
            self.delete_selected()
        else:
            # 其他工具找到对应的按钮
            for button in self.tool_button_group.buttons():
                if button.property("tool_name") == tool_name:
                    button.click()
                    break

    def group_selected_items(self) -> None:
        """分组选中的项并在状态栏显示提示。"""
        if self.canvas.group_selected_items():
            self.status_bar.showMessage("已创建分组 | 快捷键: G | MapleLabel2.0")
        else:
            self.status_bar.showMessage("请至少选择两个元素进行分组 | MapleLabel2.0")

    def ungroup_selected_items(self) -> None:
        """取消选中的分组并在状态栏显示提示。"""
        self.canvas.ungroup_selected_items()
        self.status_bar.showMessage("已取消选中分组 | 快捷键: U | MapleLabel2.0")

    def create_context_menu(self) -> None:
        """创建上下文菜单项并绑定命令。"""
        self.setContextMenuPolicy(Qt.ActionsContextMenu)

        # 删除选中项
        delete_action = QAction("删除选中项", self)
        delete_action.triggered.connect(self.delete_selected)
        self.addAction(delete_action)

        # 清除所有标注
        clear_action = QAction("清除所有标注", self)
        clear_action.triggered.connect(self.clear_annotations)
        self.addAction(clear_action)

        # 分组选中的项
        group_action = QAction("分组选中的项 (G)", self)
        group_action.triggered.connect(self.group_selected_items)
        self.addAction(group_action)

        # 取消分组
        ungroup_action = QAction("取消选中分组 (U)", self)
        ungroup_action.triggered.connect(self.ungroup_selected_items)
        self.addAction(ungroup_action)

        # 上一个图像
        prev_action = QAction("上一个图像 (Alt+左)", self)
        prev_action.triggered.connect(self.load_prev_image)
        self.addAction(prev_action)

        # 下一个图像
        next_action = QAction("下一个图像 (Alt+右)", self)
        next_action.triggered.connect(self.load_next_image)
        self.addAction(next_action)

        # 打开目录
        open_dir_action = QAction("打开目录 (Ctrl+O)", self)
        open_dir_action.triggered.connect(self.open_directory)
        self.addAction(open_dir_action)

        # 保存标注
        save_action = QAction("保存标注 (Ctrl+S)", self)
        save_action.triggered.connect(self.save_annotations)
        self.addAction(save_action)

        # 自动保存
        autosave_action = QAction("自动保存 (Ctrl+Shift+S)", self)
        autosave_action.triggered.connect(self.auto_save)
        self.addAction(autosave_action)

    def delete_selected(self) -> None:
        """删除当前选中的项。"""
        items = list(self.canvas.scene.selectedItems())
        if not items:
            return

        # 使用撤销管理器执行删除并记录操作
        try:
            if hasattr(self, "undo_manager") and self.undo_manager:
                self.undo_manager.push_and_execute_delete(items, name="delete")
            else:
                for item in items:
                    if isinstance(item, ResizableRectItem) and item in self.canvas.rect_items:
                        self.canvas.rect_items.remove(item)
                    elif isinstance(item, PointItem) and item in self.canvas.point_items:
                        self.canvas.point_items.remove(item)
                    elif isinstance(item, PolygonItem) and item in self.canvas.polygon_items:
                        self.canvas.polygon_items.remove(item)
                    elif isinstance(item, GroupItem):
                        self.canvas.remove_group(item)
                    self.canvas.scene.removeItem(item)
        except Exception:
            pass

        self.canvas.set_modified(True)
        self.status_bar.showMessage("已删除选中项 | 快捷键: Delete/E | MapleLabel2.0")

    def clear_annotations(self):
        """清除所有标注"""
        reply = QMessageBox.question(
            self, "确认", "确定要清除所有标注吗？", QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.canvas.clear_annotations()
            self.canvas.set_modified(True)

    def create_left_panel(self) -> None:
        """构建左侧工具面板。"""
        self.left_panel = CollapsiblePanel("工具", position="left")
        # self.left_panel.expanded_width = 100  # 增大左侧面板宽度以容纳更大的图标
        self.tool_button_group = QButtonGroup(self)
        self.tool_button_group.setExclusive(True)

        # 更新工具列表，文本中不包含快捷键
        tools = [
            {
                "name": "open_dir",
                "text": "打开目录",
                "icon": "open",
                "shortcut": "Ctrl+O",
                "checkable": True,
            },
            {
                "name": "save",
                "text": "保存",
                "icon": "save",
                "shortcut": "Ctrl+S",
                "checkable": False,
            },
            {
                "name": "undo",
                "text": "撤销",
                "icon": "undo",
                "shortcut": "Ctrl+Z",
                "checkable": False,
            },
            {
                "name": "redo",
                "text": "恢复",
                "icon": "redo",
                "shortcut": "Ctrl+Y",
                "checkable": False,
            },
            {
                "name": "select",
                "text": "选择",
                "icon": "select",
                "shortcut": "S",
                "checkable": True,
            },
            {
                "name": "rectangle",
                "text": "画框",
                "icon": "rectangle",
                "shortcut": "R",
                "checkable": True,
            },
            {
                "name": "point",
                "text": "画点",
                "icon": "point",
                "shortcut": "P",
                "checkable": True,
            },
            {
                "name": "polygon",
                "text": "多边形",
                "icon": "polygon",
                "shortcut": "O",
                "checkable": True,
            },
            {
                "name": "group",
                "text": "分组",
                "icon": "group",
                "shortcut": "G",
                "checkable": False,
            },
            {
                "name": "ungroup",
                "text": "取消分组",
                "icon": "ungroup",
                "shortcut": "U",
                "checkable": False,
            },
            {
                "name": "delete",
                "text": "删除",
                "icon": "delete",
                "shortcut": "E",
                "checkable": False,
            },
            {
                "name": "prev_image",
                "text": "上一个",
                "icon": "prev_image",
                "shortcut": "Alt+Left",
                "checkable": False,
            },
            {
                "name": "next_image",
                "text": "下一个",
                "icon": "next_image",
                "shortcut": "Alt+Right",
                "checkable": False,
            },
            {
                "name": "fit_view",
                "text": "适应画布",
                "icon": "fit_view",
                "shortcut": "Z",
                "checkable": False,
            },
        ]

        for tool in tools:
            btn = QToolButton()
            btn.setCheckable(tool["checkable"])
            btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            btn.setText(tool["text"])

            # 增大图标大小到24x24
            icon_size = 36
            if "icon" in tool:
                icon = self.icon_manager.get_icon(tool["icon"], icon_size)
                if not icon.isNull():
                    btn.setIcon(icon)
                else:
                    # 如果自定义图标不存在，使用系统图标
                    fallback_icons = {
                        "open": "document-open",
                        "save": "document-save",
                        "select": "cursor-arrow",
                        "rectangle": "rectangle",
                        "point": "circle",
                        "polygon": "pentagon",
                        "group": "object-group",
                        "ungroup": "object-ungroup",
                        "delete": "trash",
                        "prev_image": "arrow-left",
                        "next_image": "arrow-right",
                        "fit_view": "zoom-fit",
                    }
                    if tool["icon"] in fallback_icons:
                        btn.setIcon(QIcon.fromTheme(fallback_icons[tool["icon"]]))

            btn.setIconSize(QSize(icon_size, icon_size))

            # 设置工具提示，包含快捷键信息
            if tool["shortcut"]:
                tooltip = f"{tool['text']}\n快捷键: {tool['shortcut']}"
            else:
                tooltip = tool["text"]
            btn.setToolTip(tooltip)

            btn.setStyleSheet(
                """
                QToolButton {
                    color: #D4D4D4;
                    padding: 3px;  /* 增加内边距以适应更大的图标 */
                    margin: 0px;
                    border-radius: 2px;
                    text-align: center;
                    min-width: 50px;  /* 增加最小宽度 */
                    min-height: 50px; /* 增加最小高度 */
                    font-size: 11px;
                }
                QToolButton:hover {
                    background-color: #2A2D2E;
                }
                QToolButton:checked {
                    background-color: #37373D;
                    border: 0px solid #007ACC;
                }
                QToolButton::menu-indicator {
                    width: 0px;
                }
            """
            )

            btn.setProperty("tool_name", tool["name"])

            # 可checkable的工具添加到按钮组
            if tool["checkable"]:
                self.tool_button_group.addButton(btn)

            # 连接信号
            if tool["name"] == "group":
                btn.clicked.connect(self.group_selected_items)
            elif tool["name"] == "ungroup":
                btn.clicked.connect(self.ungroup_selected_items)
            elif tool["name"] == "delete":
                btn.clicked.connect(self.delete_selected)
            elif tool["name"] == "undo":
                btn.clicked.connect(self.undo)
            elif tool["name"] == "redo":
                btn.clicked.connect(self.redo)
            elif tool["name"] == "save":
                btn.clicked.connect(self.save_annotations)
            elif tool["name"] == "prev_image":
                btn.clicked.connect(self.load_prev_image)
            elif tool["name"] == "next_image":
                btn.clicked.connect(self.load_next_image)
            elif tool["name"] == "fit_view":
                btn.clicked.connect(lambda: self.canvas.fit_to_view())
            else:
                btn.clicked.connect(self.on_tool_selected)

            self.left_panel.content_layout.addWidget(btn)

        self.tool_button_group.setExclusive(False)
        for btn in self.tool_button_group.buttons():
            btn.setChecked(False)
        self.tool_button_group.setExclusive(True)

        self.left_panel.content_layout.addStretch()
        self.main_layout.addWidget(self.left_panel)

    def on_tool_selected(self) -> None:
        """处理工具按钮点击事件。"""
        sender = self.sender()
        tool_name = sender.property("tool_name")
        self.selected_tool = tool_name
        self.canvas.set_tool(tool_name)

        if tool_name == "open_dir":
            self.open_directory()
            self.tool_button_group.setExclusive(False)
            sender.setChecked(False)
            self.tool_button_group.setExclusive(True)
        elif tool_name == "fit_view":
            self.canvas.fit_to_view()
            self.tool_button_group.setExclusive(False)
            sender.setChecked(False)
            self.tool_button_group.setExclusive(True)
        elif tool_name == "delete":
            self.delete_selected()
            self.tool_button_group.setExclusive(False)
            sender.setChecked(False)
            self.tool_button_group.setExclusive(True)
        else:
            # 更新状态栏显示工具名称和快捷键
            shortcut = sender.property("shortcut")
            tool_text = sender.text()
            if shortcut:
                self.status_bar.showMessage(
                    f"当前工具: {tool_text} | 快捷键: {shortcut} | MapleLabel2.0"
                )
            else:
                self.status_bar.showMessage(f"当前工具: {tool_text} | MapleLabel2.0")

    def open_directory(self) -> None:
        """打开图片目录并加载文件列表与 `label.json` 配置。"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择图片目录")
        if not dir_path:
            return

        self.current_dir = dir_path
        self.image_files = []
        self.file_list.clear()

        for file in os.listdir(dir_path):
            if file.lower().endswith((".jpg", ".jpeg", ".png")):
                self.image_files.append(file)

        self.image_files.sort()

        # 尝试读取目录下的 label.json
        label_json_path = os.path.join(dir_path, "label.json")
        if os.path.exists(label_json_path):
            try:
                with open(label_json_path, "r", encoding="utf-8") as f:
                    self.label_config = json.load(f).get("shapes", {})
                self.status_bar.showMessage(f"已加载属性配置: {label_json_path}")
            except Exception as e:
                print(f"解析 label.json 时出错: {e}")
                self.label_config = {}
        else:
            self.label_config = {}

        for file in self.image_files:
            json_file = os.path.splitext(file)[0] + ".json"
            json_path = os.path.join(dir_path, json_file)
            has_json = os.path.exists(json_path) and os.path.isfile(json_path)

            # 检查是否有临时文件
            temp_name = f"temp_{file}.json"
            temp_path = os.path.join(self.temp_dir, temp_name)
            has_temp = os.path.exists(temp_path) and os.path.isfile(temp_path)

            item_widget = FileListWidgetItem(file, has_json, has_temp)
            item = QListWidgetItem(self.file_list)
            item.setSizeHint(item_widget.sizeHint())
            item.setData(Qt.UserRole, os.path.join(dir_path, file))
            self.file_list.addItem(item)
            self.file_list.setItemWidget(item, item_widget)

        self.status_bar.showMessage(f"已加载 {len(self.image_files)} 个图片文件 | {dir_path}")

        # 如果文件列表不为空，加载第一个图片
        if self.image_files:
            self.current_image_index = 0
            first_file = os.path.join(self.current_dir, self.image_files[0])
            self.load_image_by_path(first_file)
            self.select_current_file_in_list()

    def load_image_by_path(self, file_path: str) -> bool:
        """根据路径加载图片并加载对应的标注（临时优先）。"""
        # 在切换图片前，先保存当前图片的标注到临时文件（如果有修改）
        if self.current_image and self.canvas.has_unsaved_changes():
            self.auto_save()

        if self.canvas.set_image(file_path):
            self.current_image = file_path
            self.canvas.fit_to_view()
            self.status_bar.showMessage(
                f"已选择: {os.path.basename(file_path)} | {self.current_image_index + 1}/{len(self.image_files)}"
            )

            # 修复加载顺序：先尝试加载临时文件，如果没有再加载JSON文件
            if self.canvas.load_annotations_from_temp(self.temp_dir):
                self.status_bar.showMessage("已从临时文件加载标注")
            else:
                # 尝试加载对应的JSON标注文件
                json_path = os.path.splitext(file_path)[0] + ".json"
                if os.path.exists(json_path):
                    if self.canvas.load_annotations_from_json(json_path):
                        self.status_bar.showMessage(
                            f"已加载标注: {os.path.basename(json_path)}"
                        )

            # 更新右侧元素列表
            self.update_elements_panel()
            return True
        else:
            self.status_bar.showMessage(f"无法加载图像: {file_path}")
            return False

    def load_prev_image(self) -> None:
        """加载上一个图片。"""
        if not self.image_files or self.current_image_index < 0:
            return

        if self.current_image_index > 0:
            self.current_image_index -= 1
            prev_file = os.path.join(
                self.current_dir, self.image_files[self.current_image_index]
            )
            self.load_image_by_path(prev_file)
            self.select_current_file_in_list()
        else:
            self.status_bar.showMessage("已经是第一张图片 | MapleLabel2.0")

    def load_next_image(self) -> None:
        """加载下一个图片。"""
        if not self.image_files or self.current_image_index < 0:
            return

        if self.current_image_index < len(self.image_files) - 1:
            self.current_image_index += 1
            next_file = os.path.join(
                self.current_dir, self.image_files[self.current_image_index]
            )
            self.load_image_by_path(next_file)
            self.select_current_file_in_list()
        else:
            self.status_bar.showMessage("已经是最后一张图片 | MapleLabel2.0")

    def select_current_file_in_list(self) -> None:
        """在文件列表中选中当前图片对应的列表项。"""
        if self.current_image_index >= 0 and self.current_image_index < len(
            self.image_files
        ):
            file_name = self.image_files[self.current_image_index]
            file_path = os.path.join(self.current_dir, file_name)

            # 找到对应的列表项
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                if item.data(Qt.UserRole) == file_path:
                    self.file_list.setCurrentItem(item)
                    break

    def on_file_selected(self, item) -> None:
        """处理文件列表项被点击事件并加载所选图片。"""
        file_path = item.data(Qt.UserRole)

        # 查找文件在列表中的索引
        file_name = os.path.basename(file_path)
        if file_name in self.image_files:
            self.current_image_index = self.image_files.index(file_name)
            self.load_image_by_path(file_path)

    def save_annotations(self) -> None:
        """保存当前图片的标注到 JSON 文件（LabelMe 格式）。"""
        if not self.current_image:
            QMessageBox.warning(self, "警告", "没有打开的图像文件")
            return

        # 构建保存路径
        base_name = os.path.splitext(self.current_image)[0]
        json_path = base_name + ".json"

        # 默认在JSON中包含图片数据（base64），无需弹窗询问
        include_image_data = True

        if self.canvas.save_annotations_to_json(json_path, include_image_data):
            self.status_bar.showMessage(f"标注已保存到: {json_path} (LabelMe格式)")
            # 删除对应的临时文件（如果有），然后更新文件列表状态
            temp_name = f"temp_{os.path.basename(self.current_image)}.json"
            temp_path = os.path.join(self.temp_dir, temp_name)
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as e:
                    print(f"删除临时文件时出错: {e}")

            # 更新文件列表中的状态（传入当前索引以只刷新该项）
            self.update_file_list_status(self.current_image_index)
        else:
            QMessageBox.critical(self, "保存失败", "保存标注时出错")
            self.status_bar.showMessage("保存失败")

    def update_file_list_status(self, index: Optional[int] = None) -> None:
        """更新文件列表中每个文件是否存在 JSON 或临时标注的状态。"""
        if not self.current_dir or not self.image_files:
            return

        if index is not None:
            # 只更新指定索引的文件
            if 0 <= index < len(self.image_files):
                file_name = self.image_files[index]
                file_path = os.path.join(self.current_dir, file_name)

                json_file = os.path.splitext(file_name)[0] + ".json"
                json_path = os.path.join(self.current_dir, json_file)
                has_json = os.path.exists(json_path) and os.path.isfile(json_path)

                # 检查是否有临时文件
                temp_name = f"temp_{file_name}.json"
                temp_path = os.path.join(self.temp_dir, temp_name)
                has_temp = os.path.exists(temp_path) and os.path.isfile(temp_path)

                # 找到对应的列表项
                for i in range(self.file_list.count()):
                    item = self.file_list.item(i)
                    if item.data(Qt.UserRole) == file_path:
                        widget = self.file_list.itemWidget(item)
                        if widget and isinstance(widget, FileListWidgetItem):
                            widget.checkbox.setChecked(has_json or has_temp)
                            widget.set_temp_status(has_temp)
                        break
        else:
            # 更新所有文件的状态
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                file_path = item.data(Qt.UserRole)
                file_name = os.path.basename(file_path)

                json_file = os.path.splitext(file_name)[0] + ".json"
                json_path = os.path.join(self.current_dir, json_file)
                has_json = os.path.exists(json_path) and os.path.isfile(json_path)

                # 检查是否有临时文件
                temp_name = f"temp_{file_name}.json"
                temp_path = os.path.join(self.temp_dir, temp_name)
                has_temp = os.path.exists(temp_path) and os.path.isfile(temp_path)

                # 更新对应的widget
                widget = self.file_list.itemWidget(item)
                if widget and isinstance(widget, FileListWidgetItem):
                    widget.checkbox.setChecked(has_json or has_temp)
                    widget.set_temp_status(has_temp)

    def on_temp_dir_changed(self, path: str) -> None:
        """当临时目录内容变化时刷新文件列表中的临时标记。"""
        # 目录变化时可能包含新增或删除的 temp_*.json，直接刷新所有项状态
        self.update_file_list_status()

    def on_selection_changed(self) -> None:
        """场景选中项变化时更新属性面板。"""
        self.update_property_panel()

    def update_property_panel(self) -> None:
        """根据当前选中项在属性面板显示可编辑属性（下拉列表）。"""
        # 清除旧表单项
        while self.property_form.rowCount() > 0:
            # removeRow 会自动移除 widgets
            self.property_form.removeRow(0)

        selected = self.canvas.scene.selectedItems()
        if not selected:
            return

        # 仅显示第一个选中项的属性
        item = selected[0]

        # 基本信息：类型与坐标
        shape_type = getattr(item, "shape_type", None)
        # 兼容性：根据类判断类型
        if not shape_type:
            from .items import PointItem, ResizableRectItem

            if isinstance(item, ResizableRectItem):
                shape_type = "rectangle"
            elif isinstance(item, PointItem):
                shape_type = "point"
            else:
                shape_type = "polygon"

        # 坐标展示（只读）
        coords_label = QLabel(self._format_item_coords(item))
        coords_label.setStyleSheet("color: #D4D4D4;")
        self.property_form.addRow("坐标", coords_label)
        # 保存当前坐标标签引用，用于快速更新而不重建整个表单
        self._current_coords_label = coords_label

        # 从 label_config 中查找该类型的属性定义
        attrs_def = self.label_config.get(shape_type, {})
        # 属性定义示例: {"age": ["15","20"], "color": [..]}
        # 获取当前属性值字典
        cur_attrs = getattr(item, "attributes", None)
        if cur_attrs is None:
            # 对 polygon 兼容 flags
            cur_attrs = getattr(item, "flags", {})

        for attr_name, options in attrs_def.items():
            combo = QComboBox()
            combo.addItem("")
            for opt in options:
                combo.addItem(opt)

            # 设置当前值
            val = cur_attrs.get(attr_name, "") if isinstance(cur_attrs, dict) else ""
            if val is not None and val != "":
                idx = combo.findText(str(val))
                if idx >= 0:
                    combo.setCurrentIndex(idx + 1) if False else combo.setCurrentText(
                        str(val)
                    )

            def make_on_change(itm, name):
                def _on_change(text):
                    # 更新 item 属性字典
                    if hasattr(itm, "attributes"):
                        if not hasattr(itm, "attributes") or itm.attributes is None:
                            itm.attributes = {}
                        itm.attributes[name] = text
                    else:
                        # polygon 使用 flags
                        if hasattr(itm, "flags"):
                            itm.flags[name] = text
                        else:
                            setattr(itm, "attributes", {name: text})
                    self.canvas.set_modified(True)

                return _on_change

            combo.currentTextChanged.connect(make_on_change(item, attr_name))
            self.property_form.addRow(attr_name, combo)

    def update_property_coords(self, *args, **kwargs) -> None:
        """仅更新属性面板中坐标显示（在场景变更时调用，性能友好）。"""
        try:
            if not hasattr(self, "_current_coords_label"):
                return
            selected = self.canvas.scene.selectedItems()
            if not selected:
                return
            item = selected[0]
            self._current_coords_label.setText(self._format_item_coords(item))
        except Exception:
            pass

    def _format_item_coords(self, item) -> str:
        """返回一个简单文本表示坐标的字符串。"""
        from .items import PointItem, PolygonItem, ResizableRectItem

        if isinstance(item, ResizableRectItem):
            r = item.rect()
            return (
                f"({r.x():.1f}, {r.y():.1f}, {r.width():.1f}, {r.height():.1f})"
            )
        elif isinstance(item, PointItem):
            p = item.pos()
            return f"({p.x():.1f}, {p.y():.1f})"
        elif isinstance(item, PolygonItem):
            pts = getattr(item, "polygon_points", [])
            return f"points={len(pts)}"
        else:
            return ""

    def update_elements_panel(self, *args, **kwargs) -> None:
        """更新右侧只读元素表，展示当前图片所有元素的信息。"""
        # 清空表格
        self.elements_table.setRowCount(0)
        self.elements_row_items = []
        rows = []
        # 矩形
        for rect in getattr(self.canvas, "rect_items", []):
            rows.append(
                (
                    "rectangle",
                    self._format_item_coords(rect),
                    getattr(rect, "attributes", {}) or {},
                    rect,
                )
            )
        # 点
        for pt in getattr(self.canvas, "point_items", []):
            rows.append(
                (
                    "point",
                    self._format_item_coords(pt),
                    getattr(pt, "attributes", {}) or {},
                    pt,
                )
            )
        # 多边形
        for poly in getattr(self.canvas, "polygon_items", []):
            rows.append(
                (
                    "polygon",
                    self._format_item_coords(poly),
                    getattr(poly, "attributes", {}) or getattr(poly, "flags", {}) or {},
                    poly,
                )
            )

        self.elements_table.setRowCount(len(rows))
        for i, (t, coord, attrs, ref_item) in enumerate(rows):
            type_item = QTableWidgetItem(t)
            coord_item = QTableWidgetItem(coord)
            attrs_text = json.dumps(attrs, ensure_ascii=False)
            attrs_item = QTableWidgetItem(attrs_text)

            # 颜色调整
            type_item.setForeground(self.status_bar.palette().windowText())
            coord_item.setForeground(self.status_bar.palette().windowText())
            attrs_item.setForeground(self.status_bar.palette().windowText())

            self.elements_table.setItem(i, 0, type_item)
            self.elements_table.setItem(i, 1, coord_item)
            self.elements_table.setItem(i, 2, attrs_item)
            # 记录对应的 scene item
            self.elements_row_items.append(ref_item)

        pass
