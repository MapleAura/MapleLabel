from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QWidget

class CollapsiblePanel(QFrame):
    def __init__(self, title="", parent=None, position="left"):
        super().__init__(parent)
        self.position = position
        self.expanded_width = 55 if position == "left" else 250
        self.collapsed_width = 20
        self.is_expanded = True
        
        self.setFixedWidth(self.expanded_width)
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet("""
            CollapsiblePanel {
                background-color: #252526;
                margin: 0px;
                padding: 0px;
                border: none;
            }
        """)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(48)
        self.title_bar.setStyleSheet("""
            background-color: #333337;
            margin: 0px;
            padding: 0px;
            border: none;
        """)
        self.title_bar_layout = QHBoxLayout(self.title_bar)
        self.title_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.title_bar_layout.setSpacing(0)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("""
            color: #D4D4D4;
            margin: 0px;
            padding-left: 4px;
            padding-right: 4px;
        """)
        
        self.toggle_button = QToolButton()
        self.toggle_button.setText("◀" if self.position == "left" else "▶")
        self.toggle_button.setFixedSize(20, 20)
        self.toggle_button.setStyleSheet("""
            QToolButton {
                color: #D4D4D4;
                background-color: transparent;
                border: none;
                margin: 0px;
                padding: 0px;
                qproperty-iconSize: 12px;
            }
        """)
        self.toggle_button.clicked.connect(self.toggle)
        
        if self.position == "left":
            self.title_bar_layout.addWidget(self.title_label)
            self.title_bar_layout.addStretch()
            self.title_bar_layout.addWidget(self.toggle_button)
        else:
            self.title_bar_layout.addWidget(self.toggle_button)
            self.title_bar_layout.addStretch()
            self.title_bar_layout.addWidget(self.title_label)
        
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        
        self.main_layout.addWidget(self.title_bar)
        self.main_layout.addWidget(self.content)
        
    def toggle(self):
        self.is_expanded = not self.is_expanded
        animation = QPropertyAnimation(self, b"minimumWidth")
        animation.setDuration(150)
        animation.setEasingCurve(QEasingCurve.OutQuad)
        
        if self.is_expanded:
            animation.setStartValue(self.collapsed_width)
            animation.setEndValue(self.expanded_width)
            self.toggle_button.setText("◀" if self.position == "left" else "▶")
            self.title_label.show()
            self.content.show()
        else:
            animation.setStartValue(self.expanded_width)
            animation.setEndValue(self.collapsed_width)
            self.toggle_button.setText("▶" if self.position == "left" else "◀")
            self.title_label.hide()
            self.content.hide()
        
        animation.start()
        self.setFixedWidth(self.expanded_width if self.is_expanded else self.collapsed_width)