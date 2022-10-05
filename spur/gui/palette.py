from __future__ import annotations
from sys import platlibdir
from PyQt6.QtCore import QAbstractItemModel, QModelIndex, Qt

import spur.core.component as c

COMPONENT_PALETTE = [
    {"name": "Track Components", "components": [c.TimedTrack, c.SimpleCrossover]},
    {"name": "Station Components", "components": [c.SimpleStation, c.TimedStation]},
]


class PaletteItem:
    def __init__(self, value="", parent=None) -> None:
        self._parent = parent
        self._value = value
        self._children = []

    def appendChild(self, item: PaletteItem):
        self._children.append(item)

    def child(self, row: int) -> PaletteItem:
        return self._children[row]

    def parent(self) -> PaletteItem:
        return self._parent

    def childCount(self) -> int:
        return len(self._children)

    def row(self) -> int:
        return self._parent._children.index(self) if self._parent else 0

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value: str):
        self._value = value


class ComponentPaletteModel(QAbstractItemModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._rootItem = PaletteItem()

        for category in COMPONENT_PALETTE:
            pi = PaletteItem(value=category["name"], parent=self._rootItem)
            print(category["name"])
            self._rootItem.appendChild(pi)
            for component in category["components"]:
                print(component.__name__)
                pi.appendChild(PaletteItem(value=component.__name__, parent=pi))

    def data(self, index: QModelIndex, role: Qt.ItemDataRole):
        """Override from QAbstractItemModel

        Return data from a json item according index and role

        """
        if not index.isValid():
            return None

        item = index.internalPointer()

        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() == 0:
                return item.value

    def index(self, row: int, column: int, parent=QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parentItem = self._rootItem
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        """Override from QAbstractItemModel

        Return parent index of index

        """

        if not index.isValid():
            return QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem == self._rootItem:
            return QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 1

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parentItem = self._rootItem
        else:
            parentItem = parent.internalPointer()

        return parentItem.childCount()
