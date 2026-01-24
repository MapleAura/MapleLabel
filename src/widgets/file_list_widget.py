"""文件列表项组件。

该组件在右侧文件列表中显示单个图片条目，包含：
- 勾选框（表示是否存在 JSON 标注文件）
- 文件名标签
- 临时保存状态指示（橙色圆点）
"""

from typing import Optional

from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QWidget


class FileListWidgetItem(QWidget):
    """表示文件列表中的一行条目。"""

    def __init__(self, text: str, has_json: bool, has_temp: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(1, 1, 1, 1)

        self.checkbox = QCheckBox()
        # 复选框仅反映 JSON 文件是否存在
        self.checkbox.setChecked(has_json)
        self.checkbox.setStyleSheet(
            """
            QCheckBox {
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
        """
        )

        self.label = QLabel(text)
        self.label.setStyleSheet("color: #D4D4D4;")

        # 临时保存指示
        self.temp_label = QLabel("●" if has_temp else "")
        self.temp_label.setStyleSheet("color: #FFA500; font-weight: bold;")
        self.temp_label.setVisible(has_temp)

        # 布局顺序：复选框 | 临时标记 | 文件名 | 弹性间隔
        self.layout.addWidget(self.checkbox)
        self.layout.addWidget(self.temp_label)
        self.layout.addWidget(self.label)
        self.layout.addStretch()

    def set_temp_status(self, has_temp: bool) -> None:
        """设置并显示临时保存状态指示。"""
        # 使用有/无文本的方式显示在文件名前的点
        if has_temp:
            self.temp_label.setText("●")
            self.temp_label.setVisible(True)
        else:
            self.temp_label.setText("")
            self.temp_label.setVisible(False)
        # 复选框状态保持不变，只反映 JSON 文件存在
