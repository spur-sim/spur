from __future__ import annotations
from typing import Dict
from PyQt6.QtCore import QAbstractItemModel

from spur.gui.palette import COMPONENT_PALETTE


class DictItem:
    def __init__(self, parent: DictItem = None):
        self._parent = parent
        self._key = ""
        self._value = ""
        self._value_type = None
        self._children = []

    def appendChild(self, item: DictItem):
        self._children.append(item)

    def child(self, row: int) -> DictItem:
        return self._children[row]

    def parent(self) -> DictItem:
        return self._parent

    def childCount(self) -> int:
        return len(self._children)

    def row(self) -> int:
        return self._parent._children.index(self) if self._parent else 0

    @property
    def key(self):
        return self._key

    @key.setter
    def key(self, key: str):
        self._key = key

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value: str):
        self._value = value

    @property
    def value_type(self):
        """Return the python type of the item's value."""
        return self._value_type

    @value_type.setter
    def value_type(self, value):
        """Set the python type of the item's value."""
        self._value_type = value


class ComponentModel(QAbstractItemModel):
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self._rootItem = None

    def load(self, document: dict):
        assert isinstance(document, (dict, list, tuple))

        self.beginResetModel()

    