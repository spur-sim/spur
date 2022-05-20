"""Custom canvas class"""

from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QApplication
from PyQt6.QtGui import (
    QMouseEvent,
    QKeyEvent,
    QCursor,
    QPainter,
    QPen,
    QColor,
    QEnterEvent,
)
from PyQt6.QtCore import Qt, QPointF, QRectF, QSizeF


class Canvas(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(0, 0, 800, 800)
        self.setScene(self.scene)

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
        # if event.button() == Qt.MouseButton.LeftButton:
        #     modifierPressed = QApplication.keyboardModifiers()
        #     if modifierPressed == Qt.KeyboardModifier.ControlModifier:
        #         print(event.scenePosition())
        #         print(self.mapFromScene(event.scenePosition()))
        #         viewP = self.mapFromScene(event.scenePosition())
        #         pos = self.viewport().mapToGlobal(viewP)
        #         print(pos)
        #         r = QRectF(self.mapFromScene(event.scenePosition()), QSizeF(10, 10))
        #
        #         self.scene.addRect(r, pen)

        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        print("Mouse release event y'all")
        return super().mouseReleaseEvent(event)
