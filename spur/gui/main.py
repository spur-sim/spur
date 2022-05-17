from PyQt6.QtWidgets import QMainWindow

from spur.gui.main_window_ui import Ui_MainWindow


class SpurMainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)