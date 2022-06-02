"""Custom canvas class"""

import math

from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QApplication
from PyQt6.QtGui import (
    QMouseEvent,
    QKeyEvent,
    QCursor,
    QPainter,
    QPen,
    QColor,
    QEnterEvent,
    QBrush,
)
from PyQt6.QtCore import Qt, QPointF, QRectF, QSizeF, QLineF, pyqtSignal
from matplotlib.pyplot import grid


class Canvas(QGraphicsView):

    statusUpdate = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(0, 0, 1024, 768)
        self.setScene(self.scene)
        self.setAcceptDrops(True)  # Needed for drag and drop
        self.gridSize = 50

    def enterEvent(self, event: QEnterEvent) -> None:
        self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
        return super().enterEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Control:
            self.viewport().setCursor(QCursor(Qt.CursorShape.CrossCursor))
        return super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        self.viewport().setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        return super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            modifierPressed = QApplication.keyboardModifiers()
            if modifierPressed == Qt.KeyboardModifier.ControlModifier:
                r = QRectF(self.mapToScene(event.pos()), QSizeF(50, 20))
                pen = QPen(QColor(168, 34, 3))
                self.scene.addRect(r, pen)

        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        print("Mouse release event y'all")
        return super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self.statusUpdate.emit(
            f"{event.pos().x() // self.gridSize}, {event.pos().y() // self.gridSize}"
        )
        return super().mouseMoveEvent(event)

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        leftmost = math.floor(rect.left())
        rightmost = math.ceil(rect.right())
        topmost = math.floor(rect.top())
        bottommost = math.ceil(rect.bottom())

        lines = []

        firstLeftGridLine = leftmost - (leftmost % self.gridSize)
        firstTopGridLine = topmost - (topmost % self.gridSize)

        for x in range(firstLeftGridLine, rightmost, self.gridSize):
            lines.append(QLineF(x, topmost, x, bottommost))

        for y in range(firstTopGridLine, bottommost, self.gridSize):
            lines.append(QLineF(leftmost, y, rightmost, y))

        painter.setPen(QPen(QColor("#F58426"), 0.0))
        painter.drawLines(lines)

        # super().drawBackground(painter, rect)
