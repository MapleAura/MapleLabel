import os

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon


class IconManager:
    """图标管理器"""

    def __init__(self, base_path=None):
        """
        初始化图标管理器

        Args:
            base_path: 图标基础路径，默认为项目根目录下的icons文件夹
        """
        if base_path is None:
            # 假设项目结构为 maplabel/icons/
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.base_path = os.path.join(current_dir, "..", "..", "icons")
        else:
            self.base_path = base_path

        # 确保图标目录存在
        if not os.path.exists(self.base_path):
            print(f"警告: 图标目录不存在: {self.base_path}")

        # 图标缓存
        self.icon_cache = {}

        # 图标名称到文件名的映射
        self.icon_mapping = {
            # 文件操作
            "open": "open.svg",
            "save": "save.svg",
            "autosave": "save.svg",  # 复用保存图标
            # 工具
            "select": "select.svg",
            "rectangle": "rect.svg",
            "point": "point.svg",
            "polygon": "polygon.svg",
            "delete": "delete.svg",
            "group": "group.svg",
            "ungroup": "ungroup.svg",
            # 导航
            "prev_image": "prev.svg",
            "next_image": "next.svg",
            "fit_view": "fit.svg",
            # 其他
            "logo": "logo.png",
        }

    def get_icon(self, icon_name, size=16):
        """
        获取图标

        Args:
            icon_name: 图标名称
            size: 图标大小

        Returns:
            QIcon对象
        """
        # 检查缓存
        cache_key = f"{icon_name}_{size}"
        if cache_key in self.icon_cache:
            return self.icon_cache[cache_key]

        # 获取图标文件路径
        if icon_name in self.icon_mapping:
            filename = self.icon_mapping[icon_name]
            icon_path = os.path.join(self.base_path, filename)

            if os.path.exists(icon_path):
                icon = QIcon(icon_path)
                self.icon_cache[cache_key] = icon
                return icon
            else:
                print(f"警告: 图标文件不存在: {icon_path}")

        # 如果找不到图标，返回空图标或系统图标
        return QIcon()

    def get_icon_path(self, icon_name):
        """
        获取图标文件路径

        Args:
            icon_name: 图标名称

        Returns:
            图标文件路径，如果不存在则返回None
        """
        if icon_name in self.icon_mapping:
            filename = self.icon_mapping[icon_name]
            icon_path = os.path.join(self.base_path, filename)

            if os.path.exists(icon_path):
                return icon_path

        return None

    def set_application_icon(self, app, icon_name="logo"):
        """设置应用程序图标"""
        icon_path = self.get_icon_path(icon_name)
        if icon_path and os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))

    def create_tool_button(self, icon_name, text="", tooltip="", size=16):
        """
        创建带有图标的工具按钮

        Args:
            icon_name: 图标名称
            text: 按钮文本
            tooltip: 工具提示
            size: 图标大小

        Returns:
            配置好的QToolButton
        """
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QToolButton

        button = QToolButton()
        icon = self.get_icon(icon_name, size)

        if not icon.isNull():
            button.setIcon(icon)
            button.setIconSize(QSize(size, size))

        if text:
            button.setText(text)
            button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

        if tooltip:
            button.setToolTip(tooltip)

        return button

    def list_available_icons(self):
        """列出所有可用的图标"""
        available = []
        missing = []

        for icon_name, filename in self.icon_mapping.items():
            icon_path = os.path.join(self.base_path, filename)
            if os.path.exists(icon_path):
                available.append(f"{icon_name}: {filename}")
            else:
                missing.append(f"{icon_name}: {filename} (未找到)")

        return {
            "available": available,
            "missing": missing,
            "total": len(self.icon_mapping),
            "found": len(available),
        }
