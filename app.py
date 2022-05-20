import sys

from PyQt6.QtWidgets import QApplication

from spur.gui.main import SpurMainWindow

if __name__ == "__main__":
    spur_app = QApplication(sys.argv)
    window = SpurMainWindow()
    window.show()
    sys.exit(spur_app.exec())
