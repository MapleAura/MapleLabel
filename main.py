import sys
from PySide6.QtWidgets import QApplication
from src.app import MapleLabelWindow
from src.config.styles import get_dark_palette

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # 设置深色主题
    app.setPalette(get_dark_palette())
    
    window = MapleLabelWindow()
    window.show()
    sys.exit(app.exec())