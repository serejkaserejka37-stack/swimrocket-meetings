"""Создаёт фирменные PNG/ICO из официального SVG SwimRocket."""
import copy
import os
import xml.etree.ElementTree as ET
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import (
    QGuiApplication, QImage, QPainter, QColor, QPainterPath, QLinearGradient,
)
from PyQt6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parent
SVG = ROOT / "swimrocket-logo.svg"
app = QGuiApplication([])


def render_logo(renderer, path):
    image = QImage(1400, 689, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    image.save(str(path))


renderer = QSvgRenderer(str(SVG))
if not renderer.isValid():
    raise RuntimeError("Не удалось прочитать официальный SVG-логотип")
render_logo(renderer, ROOT / "swimrocket-logo.png")

# На светлом стекле белая часть логотипа становится фирменной тёмно-синей.
light_svg = SVG.read_text(encoding="utf-8").replace('fill="white"', 'fill="#242841"')
light_path = ROOT / "swimrocket-logo-light.svg"
light_path.write_text(light_svg, encoding="utf-8")
render_logo(QSvgRenderer(str(light_path)), ROOT / "swimrocket-logo-light.png")

# Отдельный знак пловца без текста.
svg_root = ET.parse(SVG).getroot()
namespace = "http://www.w3.org/2000/svg"
first_path = svg_root.find(f".//{{{namespace}}}path")
mark_root = ET.Element(f"{{{namespace}}}svg", {
    "width": "580", "height": "689", "viewBox": "0 0 580 689",
})
mark_root.append(copy.deepcopy(first_path))
mark_renderer = QSvgRenderer(ET.tostring(mark_root))
mark = QImage(580, 689, QImage.Format.Format_ARGB32)
mark.fill(QColor(0, 0, 0, 0))
painter = QPainter(mark)
mark_renderer.render(painter)
painter.end()

# Современная iOS-подобная иконка: скруглённый квадрат и лёгкий глянец.
icon = QImage(512, 512, QImage.Format.Format_ARGB32)
icon.fill(QColor(0, 0, 0, 0))
painter = QPainter(icon)
painter.setRenderHint(QPainter.RenderHint.Antialiasing)
shape = QPainterPath()
shape.addRoundedRect(QRectF(8, 8, 496, 496), 112, 112)
gradient = QLinearGradient(0, 0, 512, 512)
gradient.setColorAt(0, QColor("#353A59"))
gradient.setColorAt(1, QColor("#1B1E33"))
painter.fillPath(shape, gradient)
painter.setPen(QColor(255, 255, 255, 45))
painter.drawPath(shape)
painter.drawImage(QRectF(66, 24, 380, 464), mark, QRectF(0, 0, 580, 689))
painter.end()
icon.save(str(ROOT / "swimrocket-icon.png"))

with Image.open(ROOT / "swimrocket-icon.png") as image:
    image.save(ROOT / "swimrocket.ico", sizes=[
        (16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256),
    ])

for name in ("swimrocket-logo-light.png", "swimrocket-icon.png", "swimrocket.ico"):
    print(ROOT / name)
