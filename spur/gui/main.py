import json

from PyQt6.QtWidgets import QMainWindow, QFileDialog

from spur.gui.table import ComponentTableModel
from spur.gui.palette import ComponentPaletteModel
from spur.gui.main_window_ui import Ui_MainWindow
from spur.core.model import Model


class SpurMainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.model = Model()
        self.project_name = "Untitled Project"
        self.saved = False

        self.actionOpen_Project.triggered.connect(self.open_project)
        self.canvas.statusUpdate.connect(self.statusbar.showMessage)

        self.treeComponentPalette.setModel(ComponentPaletteModel())
        self.treeComponentPalette.setHeaderHidden(True)
        self.treeComponentPalette.expandRecursively(
            self.treeComponentPalette.rootIndex()
        )

        self.update_ui()

        self.statusbar.showMessage("Welcome")

    def open_project(self):
        filepath = QFileDialog.getOpenFileName(
            self, "Open Project File", ".", "Spur Projects (*.spur)"
        )
        self.load_project_file(filepath[0])

    def load_project_file(self, filepath):
        with open(filepath, "r") as infile:
            project = json.load(infile)
        self.model = Model.from_project_dictionary(project)
        self.project_name = project["name"]
        self.update_ui()

    def update_ui(self):
        self.update_window_title()
        self.update_components_list()

    def update_components_list(self):
        table = []
        for c in self.model.components:
            table.append([c.uid, c.__name__])
            print(c.as_dict())
        if len(table) > 0:
            model = ComponentTableModel(table)
            self.tblComponents.setModel(model)

    def update_window_title(self):
        if self.saved:
            self.setWindowTitle(f"{self.project_name} - Spur")
        else:
            self.setWindowTitle(f"{self.project_name}* - Spur")
