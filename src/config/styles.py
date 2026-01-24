from PySide6.QtGui import QColor, QPalette

def get_dark_palette():
    """获取深色主题调色板"""
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(37, 37, 38))
    palette.setColor(QPalette.WindowText, QColor(212, 212, 212))
    palette.setColor(QPalette.Base, QColor(45, 45, 48))
    palette.setColor(QPalette.AlternateBase, QColor(45, 45, 48))
    palette.setColor(QPalette.ToolTipBase, QColor(45, 45, 48))
    palette.setColor(QPalette.ToolTipText, QColor(212, 212, 212))
    palette.setColor(QPalette.Text, QColor(212, 212, 212))
    palette.setColor(QPalette.Button, QColor(45, 45, 48))
    palette.setColor(QPalette.ButtonText, QColor(212, 212, 212))
    palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.Highlight, QColor(0, 122, 204))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    return palette

def get_stylesheet():
    """获取应用程序样式表"""
    return """
    QMainWindow {
        background-color: #1E1E1E;
    }
    
    QStatusBar {
        background-color: #007ACC;
        color: white;
    }
    
    QToolButton {
        color: #D4D4D4;
        padding: 2px;
        margin: 0px;
        border-radius: 2px;
        text-align: center;
        min-width: 70px;
        font-size: 11px;
    }
    
    QToolButton:hover {
        background-color: #2A2D2E;
    }
    
    QToolButton:checked {
        background-color: #37373D;
        border: 1px solid #007ACC;
    }
    
    QListWidget {
        background-color: #252526;
        border: none;
        color: #D4D4D4;
    }
    
    QListWidget::item {
        padding: 0px;
        border: none;
    }
    
    QListWidget::item:hover {
        background-color: #2A2D2E;
    }
    
    QListWidget::item:selected {
        background-color: #37373D;
    }
    
    QLabel {
        color: #D4D4D4;
    }
    
    QCheckBox {
        spacing: 5px;
        color: #D4D4D4;
    }
    
    QCheckBox::indicator {
        width: 16px;
        height: 16px;
    }
    """