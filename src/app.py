import os
import json
import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QStatusBar, QWidget, 
                              QVBoxLayout, QHBoxLayout, QToolButton, QButtonGroup,
                              QFrame, QLabel, QFileDialog, QListWidget, QListWidgetItem,
                              QGraphicsView, QMenu, QMessageBox)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QAction, QKeySequence, QShortcut

from .widgets import CollapsiblePanel, AnnotationView, FileListWidgetItem
from .config.styles import get_dark_palette, get_stylesheet
from .items import ResizableRectItem, PointItem, PolygonItem, GroupItem
from .utils import IconManager

class MapleLabelWindow(QMainWindow):
    def __init__(self):
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
        self.main_layout.addWidget(self.canvas, stretch=1)
        
        # 右侧面板容器
        self.right_panel = CollapsiblePanel("属性", position="right")
        self.right_panel.setStyleSheet("background-color: #252526;")
        
        # 右上方面板 - 属性面板
        self.property_panel = QFrame()
        self.property_panel.setFrameShape(QFrame.StyledPanel)
        self.property_panel.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border-bottom: 1px solid #1E1E1E;
            }
            QLabel {
                color: #D4D4D4;
                padding: 5px;
            }
        """)
        self.property_panel.setFixedHeight(200)
        self.property_layout = QVBoxLayout(self.property_panel)
        self.property_layout.addWidget(QLabel("属性面板"))
        self.property_layout.addStretch()
        
        # 右下方面板 - 文件列表
        self.file_panel = QFrame()
        self.file_panel.setFrameShape(QFrame.StyledPanel)
        self.file_panel.setStyleSheet("""
            QFrame {
                background-color: #252526;
            }
        """)
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.SingleSelection)
        self.file_list.itemClicked.connect(self.on_file_selected)
        
        self.file_layout = QVBoxLayout(self.file_panel)
        self.file_layout.addWidget(QLabel("文件列表"))
        self.file_layout.addWidget(self.file_list)
        
        self.right_panel.content_layout.addWidget(self.property_panel)
        self.right_panel.content_layout.addWidget(self.file_panel)
        self.main_layout.addWidget(self.right_panel)
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 | MapleLabel2.0 - 图像标注工具")
        
        self.selected_tool = None
        self.current_dir = ""
        self.current_image = None
        self.image_files = []
        self.current_image_index = -1
        
        # 临时文件目录
        self.temp_dir = os.path.join(os.path.expanduser("~"), ".maplabel_temp")
        
        # 添加上下文菜单
        self.create_context_menu()
        
        # 添加快捷键
        self.create_shortcuts()
        
    def closeEvent(self, event):
        """处理窗口关闭事件"""
        if self.check_unsaved_changes():
            reply = QMessageBox.question(
                self, 
                "保存更改", 
                "您有未保存的更改。是否要在退出前保存？",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
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
    
    def check_unsaved_changes(self):
        """检查是否有未保存的更改"""
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
    
    def save_all_unsaved(self):
        """保存所有未保存的更改"""
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
                        with open(temp_path, 'r', encoding='utf-8') as f:
                            temp_data = json.load(f)
                        
                        # 保存到JSON文件
                        with open(json_path, 'w', encoding='utf-8') as f:
                            json.dump(temp_data, f, indent=2, ensure_ascii=False)
                        
                        # 删除临时文件
                        os.remove(temp_path)
                        
                    except Exception as e:
                        print(f"保存临时文件时出错: {e}")
        
        # 更新文件列表状态
        self.update_file_list_status()
    
    def create_shortcuts(self):
        """创建快捷键"""
        # 工具快捷键映射
        self.tool_shortcuts = {
            Qt.Key_S: "select",      # 选择工具
            Qt.Key_R: "rectangle",   # 矩形工具
            Qt.Key_P: "point",       # 点工具
            Qt.Key_O: "polygon",     # 多边形工具
            Qt.Key_E: "delete",      # 删除工具
            Qt.Key_G: "group",       # 分组工具
            Qt.Key_U: "ungroup",     # 取消分组工具
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

        self.fit_view_shortcut = QShortcut(Qt.Key_Z, self) # 将 Qt.Key_Space 改为 Qt.Key_Z
        self.fit_view_shortcut.activated.connect(lambda: self.canvas.fit_to_view())
        
        # 为每个快捷键创建QShortcut
        for key, tool_name in self.tool_shortcuts.items():
            shortcut = QShortcut(key, self)
            shortcut.activated.connect(lambda t=tool_name: self.activate_tool_by_shortcut(t))
    
    def auto_save(self):
        """自动保存当前图片到临时文件"""
        if self.current_image and self.canvas.has_unsaved_changes():
            if self.canvas.save_annotations_to_temp(self.temp_dir):
                self.status_bar.showMessage(f"已自动保存: {os.path.basename(self.current_image)}")
                # 更新文件列表状态
                self.update_file_list_status(self.current_image_index)
            else:
                self.status_bar.showMessage("自动保存失败")
    
    def activate_tool_by_shortcut(self, tool_name):
        """通过快捷键激活工具"""
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
    
    def group_selected_items(self):
        """分组选中的项"""
        if self.canvas.group_selected_items():
            self.status_bar.showMessage("已创建分组 | 快捷键: G | MapleLabel2.0")
        else:
            self.status_bar.showMessage("请至少选择两个元素进行分组 | MapleLabel2.0")
    
    def ungroup_selected_items(self):
        """取消选中的分组"""
        self.canvas.ungroup_selected_items()
        self.status_bar.showMessage("已取消选中分组 | 快捷键: U | MapleLabel2.0")
    
    def create_context_menu(self):
        """创建上下文菜单"""
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

    def delete_selected(self):
        """删除选中项"""
        for item in self.canvas.scene.selectedItems():
            if isinstance(item, ResizableRectItem) and item in self.canvas.rect_items:
                self.canvas.rect_items.remove(item)
            elif isinstance(item, PointItem) and item in self.canvas.point_items:
                self.canvas.point_items.remove(item)
            elif isinstance(item, PolygonItem) and item in self.canvas.polygon_items:
                self.canvas.polygon_items.remove(item)
            elif isinstance(item, GroupItem):
                # 删除分组
                self.canvas.remove_group(item)
            self.canvas.scene.removeItem(item)
        self.canvas.set_modified(True)
        self.status_bar.showMessage("已删除选中项 | 快捷键: Delete/E | MapleLabel2.0")

    def clear_annotations(self):
        """清除所有标注"""
        reply = QMessageBox.question(self, '确认', '确定要清除所有标注吗？', 
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.canvas.clear_annotations()
            self.canvas.set_modified(True)
    def create_left_panel(self):
        self.left_panel = CollapsiblePanel("工具", position="left")
        # self.left_panel.expanded_width = 100  # 增大左侧面板宽度以容纳更大的图标
        self.tool_button_group = QButtonGroup(self)
        self.tool_button_group.setExclusive(True)
        
        # 更新工具列表，文本中不包含快捷键
        tools = [
            {"name": "open_dir", "text": "打开目录", "icon": "open", "shortcut": "Ctrl+O", "checkable": True},
            {"name": "save", "text": "保存", "icon": "save", "shortcut": "Ctrl+S", "checkable": False},
            {"name": "select", "text": "选择", "icon": "select", "shortcut": "S", "checkable": True},
            {"name": "rectangle", "text": "画框", "icon": "rectangle", "shortcut": "R", "checkable": True},
            {"name": "point", "text": "画点", "icon": "point", "shortcut": "P", "checkable": True},
            {"name": "polygon", "text": "多边形", "icon": "polygon", "shortcut": "O", "checkable": True},
            {"name": "group", "text": "分组", "icon": "group", "shortcut": "G", "checkable": False},
            {"name": "ungroup", "text": "取消分组", "icon": "ungroup", "shortcut": "U", "checkable": False},
            {"name": "delete", "text": "删除", "icon": "delete", "shortcut": "E", "checkable": False},
            {"name": "prev_image", "text": "上一个", "icon": "prev_image", "shortcut": "Alt+Left", "checkable": False},
            {"name": "next_image", "text": "下一个", "icon": "next_image", "shortcut": "Alt+Right", "checkable": False},
            {"name": "fit_view", "text": "适应画布", "icon": "fit_view", "shortcut": "Z", "checkable": False}
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
                        "fit_view": "zoom-fit"
                    }
                    if tool["icon"] in fallback_icons:
                        btn.setIcon(QIcon.fromTheme(fallback_icons[tool["icon"]]))
            
            btn.setIconSize(QSize(icon_size, icon_size))
            
            # 设置工具提示，包含快捷键信息
            if tool["shortcut"]:
                tooltip = f"{tool['text']}\n快捷键: {tool['shortcut']}"
            else:
                tooltip = tool['text']
            btn.setToolTip(tooltip)
            
            btn.setStyleSheet("""
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
            """)
            
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

    def on_tool_selected(self):
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
                self.status_bar.showMessage(f"当前工具: {tool_text} | 快捷键: {shortcut} | MapleLabel2.0")
            else:
                self.status_bar.showMessage(f"当前工具: {tool_text} | MapleLabel2.0")

    def open_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择图片目录")
        if not dir_path:
            return
            
        self.current_dir = dir_path
        self.image_files = []
        self.file_list.clear()
        
        for file in os.listdir(dir_path):
            if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                self.image_files.append(file)
        
        self.image_files.sort()
        
        for file in self.image_files:
            json_file = os.path.splitext(file)[0] + '.json'
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

    def load_image_by_path(self, file_path):
        """根据路径加载图片"""
        # 在切换图片前，先保存当前图片的标注到临时文件（如果有修改）
        if self.current_image and self.canvas.has_unsaved_changes():
            self.auto_save()
        
        if self.canvas.set_image(file_path):
            self.current_image = file_path
            self.canvas.fit_to_view()
            self.status_bar.showMessage(f"已选择: {os.path.basename(file_path)} | {self.current_image_index + 1}/{len(self.image_files)}")
            
            # 修复加载顺序：先尝试加载临时文件，如果没有再加载JSON文件
            if self.canvas.load_annotations_from_temp(self.temp_dir):
                self.status_bar.showMessage(f"已从临时文件加载标注")
            else:
                # 尝试加载对应的JSON标注文件
                json_path = os.path.splitext(file_path)[0] + '.json'
                if os.path.exists(json_path):
                    if self.canvas.load_annotations_from_json(json_path):
                        self.status_bar.showMessage(f"已加载标注: {os.path.basename(json_path)}")
            
            return True
        else:
            self.status_bar.showMessage(f"无法加载图像: {file_path}")
            return False

    def load_prev_image(self):
        """加载上一个图片"""
        if not self.image_files or self.current_image_index < 0:
            return
        
        if self.current_image_index > 0:
            self.current_image_index -= 1
            prev_file = os.path.join(self.current_dir, self.image_files[self.current_image_index])
            self.load_image_by_path(prev_file)
            self.select_current_file_in_list()
        else:
            self.status_bar.showMessage("已经是第一张图片 | MapleLabel2.0")

    def load_next_image(self):
        """加载下一个图片"""
        if not self.image_files or self.current_image_index < 0:
            return
        
        if self.current_image_index < len(self.image_files) - 1:
            self.current_image_index += 1
            next_file = os.path.join(self.current_dir, self.image_files[self.current_image_index])
            self.load_image_by_path(next_file)
            self.select_current_file_in_list()
        else:
            self.status_bar.showMessage("已经是最后一张图片 | MapleLabel2.0")

    def select_current_file_in_list(self):
        """在文件列表中选择当前图片"""
        if self.current_image_index >= 0 and self.current_image_index < len(self.image_files):
            file_name = self.image_files[self.current_image_index]
            file_path = os.path.join(self.current_dir, file_name)
            
            # 找到对应的列表项
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                if item.data(Qt.UserRole) == file_path:
                    self.file_list.setCurrentItem(item)
                    break

    def on_file_selected(self, item):
        file_path = item.data(Qt.UserRole)
        
        # 查找文件在列表中的索引
        file_name = os.path.basename(file_path)
        if file_name in self.image_files:
            self.current_image_index = self.image_files.index(file_name)
            self.load_image_by_path(file_path)

    def save_annotations(self):
        """保存标注到JSON文件（LabelMe格式）"""
        if not self.current_image:
            QMessageBox.warning(self, "警告", "没有打开的图像文件")
            return
        
        # 构建保存路径
        base_name = os.path.splitext(self.current_image)[0]
        json_path = base_name + '.json'
        
        # 询问是否包含图片数据
        include_image_data = QMessageBox.question(
            self, 
            "保存选项", 
            "是否在JSON中包含图片数据？\n包含图片数据会使文件变大，但可以独立使用。\n不包含图片数据则需要保持图片文件与JSON文件在同一目录。",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.No
        )
        
        if include_image_data == QMessageBox.Cancel:
            return
        
        include_image_data = (include_image_data == QMessageBox.Yes)
        
        if self.canvas.save_annotations_to_json(json_path, include_image_data):
            self.status_bar.showMessage(f"标注已保存到: {json_path} (LabelMe格式)")
            
            # 更新文件列表中的状态
            self.update_file_list_status()
            
            # 删除对应的临时文件（如果有）
            temp_name = f"temp_{os.path.basename(self.current_image)}.json"
            temp_path = os.path.join(self.temp_dir, temp_name)
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as e:
                    print(f"删除临时文件时出错: {e}")
        else:
            QMessageBox.critical(self, "保存失败", "保存标注时出错")
            self.status_bar.showMessage("保存失败")

    def update_file_list_status(self, index=None):
        """更新文件列表中的JSON文件状态"""
        if not self.current_dir or not self.image_files:
            return
        
        if index is not None:
            # 只更新指定索引的文件
            if 0 <= index < len(self.image_files):
                file_name = self.image_files[index]
                file_path = os.path.join(self.current_dir, file_name)
                
                json_file = os.path.splitext(file_name)[0] + '.json'
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
                
                json_file = os.path.splitext(file_name)[0] + '.json'
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