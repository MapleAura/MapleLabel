from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QCheckBox

class FileListWidgetItem(QWidget):
    def __init__(self, text, has_json, has_temp=False, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(1, 1, 1, 1)
        
        self.checkbox = QCheckBox()
        # 修复：复选框只反映JSON文件存在，不反映临时文件
        self.checkbox.setChecked(has_json)
        self.checkbox.setStyleSheet("""
            QCheckBox {
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
        """)
        
        self.label = QLabel(text)
        self.label.setStyleSheet("color: #D4D4D4;")
        
        # 添加临时保存标志
        self.temp_label = QLabel("●" if has_temp else "")
        self.temp_label.setStyleSheet("color: #FFA500; font-weight: bold;")
        self.temp_label.setVisible(has_temp)
        
        self.layout.addWidget(self.checkbox)
        self.layout.addWidget(self.label)
        self.layout.addStretch()
        self.layout.addWidget(self.temp_label)
    
    def set_temp_status(self, has_temp):
        """设置临时保存状态"""
        self.temp_label.setVisible(has_temp)
        # 复选框状态保持不变，只反映JSON文件存在