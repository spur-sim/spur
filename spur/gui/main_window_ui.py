# Form implementation generated from reading ui file 'spur/resources/ui/MainWindow.ui'
#
# Created by: PyQt6 UI code generator 6.3.0
#
# WARNING: Any manual changes made to this file will be lost when pyuic6 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt6 import QtCore, QtGui, QtWidgets


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1024, 768)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.canvas = Canvas(self.centralwidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.MinimumExpanding, QtWidgets.QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.canvas.sizePolicy().hasHeightForWidth())
        self.canvas.setSizePolicy(sizePolicy)
        self.canvas.viewport().setProperty("cursor", QtGui.QCursor(QtCore.Qt.CursorShape.ArrowCursor))
        self.canvas.setMouseTracking(True)
        self.canvas.setObjectName("canvas")
        self.horizontalLayout.addWidget(self.canvas)
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 1024, 21))
        self.menubar.setObjectName("menubar")
        self.menuActions = QtWidgets.QMenu(self.menubar)
        self.menuActions.setObjectName("menuActions")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.dockWidget = QtWidgets.QDockWidget(MainWindow)
        self.dockWidget.setObjectName("dockWidget")
        self.dockObjects = QtWidgets.QWidget()
        self.dockObjects.setObjectName("dockObjects")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.dockObjects)
        self.verticalLayout.setObjectName("verticalLayout")
        self.toolBox = QtWidgets.QToolBox(self.dockObjects)
        self.toolBox.setObjectName("toolBox")
        self.pgComponents = QtWidgets.QWidget()
        self.pgComponents.setGeometry(QtCore.QRect(0, 0, 306, 357))
        self.pgComponents.setObjectName("pgComponents")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout(self.pgComponents)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.tblComponents = QtWidgets.QTableView(self.pgComponents)
        self.tblComponents.setObjectName("tblComponents")
        self.verticalLayout_3.addWidget(self.tblComponents)
        self.toolBox.addItem(self.pgComponents, "")
        self.pgRoutes = QtWidgets.QWidget()
        self.pgRoutes.setGeometry(QtCore.QRect(0, 0, 267, 357))
        self.pgRoutes.setObjectName("pgRoutes")
        self.toolBox.addItem(self.pgRoutes, "")
        self.pgTrains = QtWidgets.QWidget()
        self.pgTrains.setObjectName("pgTrains")
        self.toolBox.addItem(self.pgTrains, "")
        self.verticalLayout.addWidget(self.toolBox)
        self.dockWidget.setWidget(self.dockObjects)
        MainWindow.addDockWidget(QtCore.Qt.DockWidgetArea(2), self.dockWidget)
        self.dwPropertyEditor = QtWidgets.QDockWidget(MainWindow)
        self.dwPropertyEditor.setObjectName("dwPropertyEditor")
        self.dockProperties = QtWidgets.QWidget()
        self.dockProperties.setObjectName("dockProperties")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.dockProperties)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.treeProperties = QtWidgets.QTreeView(self.dockProperties)
        self.treeProperties.setObjectName("treeProperties")
        self.verticalLayout_2.addWidget(self.treeProperties)
        self.dwPropertyEditor.setWidget(self.dockProperties)
        MainWindow.addDockWidget(QtCore.Qt.DockWidgetArea(2), self.dwPropertyEditor)
        self.dockComponents = QtWidgets.QDockWidget(MainWindow)
        self.dockComponents.setObjectName("dockComponents")
        self.dockWidgetContents = QtWidgets.QWidget()
        self.dockWidgetContents.setObjectName("dockWidgetContents")
        self.verticalLayout_4 = QtWidgets.QVBoxLayout(self.dockWidgetContents)
        self.verticalLayout_4.setObjectName("verticalLayout_4")
        self.treeComponentPalette = QtWidgets.QTreeView(self.dockWidgetContents)
        self.treeComponentPalette.setDragEnabled(False)
        self.treeComponentPalette.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.NoDragDrop)
        self.treeComponentPalette.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectItems)
        self.treeComponentPalette.setObjectName("treeComponentPalette")
        self.verticalLayout_4.addWidget(self.treeComponentPalette)
        self.dockComponents.setWidget(self.dockWidgetContents)
        MainWindow.addDockWidget(QtCore.Qt.DockWidgetArea(1), self.dockComponents)
        self.action_add_component = QtGui.QAction(MainWindow)
        self.action_add_component.setObjectName("action_add_component")
        self.action_delete_component = QtGui.QAction(MainWindow)
        self.action_delete_component.setObjectName("action_delete_component")
        self.action_clone_component = QtGui.QAction(MainWindow)
        self.action_clone_component.setObjectName("action_clone_component")
        self.actionMove_Component = QtGui.QAction(MainWindow)
        self.actionMove_Component.setObjectName("actionMove_Component")
        self.actionNew_Project = QtGui.QAction(MainWindow)
        self.actionNew_Project.setObjectName("actionNew_Project")
        self.actionOpen_Project = QtGui.QAction(MainWindow)
        self.actionOpen_Project.setObjectName("actionOpen_Project")
        self.actionQuit_Spur = QtGui.QAction(MainWindow)
        self.actionQuit_Spur.setObjectName("actionQuit_Spur")
        self.menuActions.addAction(self.actionNew_Project)
        self.menuActions.addAction(self.actionOpen_Project)
        self.menuActions.addSeparator()
        self.menuActions.addAction(self.actionQuit_Spur)
        self.menubar.addAction(self.menuActions.menuAction())

        self.retranslateUi(MainWindow)
        self.toolBox.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "Spur"))
        self.menuActions.setTitle(_translate("MainWindow", "File"))
        self.dockWidget.setWindowTitle(_translate("MainWindow", "Object Inspector"))
        self.toolBox.setItemText(self.toolBox.indexOf(self.pgComponents), _translate("MainWindow", "Components"))
        self.toolBox.setItemText(self.toolBox.indexOf(self.pgRoutes), _translate("MainWindow", "Routes"))
        self.toolBox.setItemText(self.toolBox.indexOf(self.pgTrains), _translate("MainWindow", "Trains"))
        self.dwPropertyEditor.setWindowTitle(_translate("MainWindow", "Property Editor"))
        self.dockComponents.setWindowTitle(_translate("MainWindow", "Component Pallette"))
        self.action_add_component.setText(_translate("MainWindow", "New Component"))
        self.action_add_component.setShortcut(_translate("MainWindow", "N"))
        self.action_delete_component.setText(_translate("MainWindow", "Delete Component"))
        self.action_delete_component.setShortcut(_translate("MainWindow", "D"))
        self.action_clone_component.setText(_translate("MainWindow", "Clone Component"))
        self.action_clone_component.setShortcut(_translate("MainWindow", "C"))
        self.actionMove_Component.setText(_translate("MainWindow", "Move Component"))
        self.actionNew_Project.setText(_translate("MainWindow", "New Project"))
        self.actionOpen_Project.setText(_translate("MainWindow", "Open Project"))
        self.actionOpen_Project.setShortcut(_translate("MainWindow", "Ctrl+O"))
        self.actionQuit_Spur.setText(_translate("MainWindow", "Quit Spur"))
        self.actionQuit_Spur.setShortcut(_translate("MainWindow", "Ctrl+Q"))
from spur.gui.canvas import Canvas
