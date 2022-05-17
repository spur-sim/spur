"""Custom canvas class"""

from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QApplication
from PyQt6.QtGui import QMouseEvent, QKeyEvent, QCursor, QPainter, QPen, QColor
from PyQt6.QtCore import Qt, QPointF, QRectF, QSizeF


class Canvas(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Control:
            print("CTRL+")
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        return super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        return super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            modifierPressed = QApplication.keyboardModifiers()
            if modifierPressed == Qt.KeyboardModifier.ControlModifier:
                print(event.scenePosition())
                r = QRectF(event.scenePosition(), QSizeF(10, 10))
                pen = QPen(QColor(168, 34, 3))
                self.scene.addRect(r, pen)

        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        print("Mouse release event y'all")
        return super().mouseReleaseEvent(event)
