"""Светлый фон Liquid Glass без системных теней и артефактов Qt."""
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor, QPainter, QRadialGradient
from PyQt6.QtWidgets import QWidget


class GlassBackground(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#F3F6FB"))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = max(1, self.width()), max(1, self.height())
        blobs = [
            (QPointF(width * 0.06, height * 0.03), width * 0.58,
             QColor(158, 203, 255, 125)),
            (QPointF(width * 0.96, height * 0.08), width * 0.46,
             QColor(255, 194, 166, 105)),
            (QPointF(width * 0.55, height * 1.02), width * 0.65,
             QColor(210, 224, 255, 105)),
        ]
        for center, radius, color in blobs:
            gradient = QRadialGradient(center, radius)
            gradient.setColorAt(0, color)
            fade = QColor(color)
            fade.setAlpha(0)
            gradient.setColorAt(1, fade)
            painter.fillRect(self.rect(), gradient)
        painter.end()
