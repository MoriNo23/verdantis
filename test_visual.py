#!/usr/bin/env python3
"""Test visual de NotifyApp: genera icono + imagen de muestra y lanza la notif."""

import os
import sys
import tempfile

from PyQt6.QtGui import QPixmap, QColor, QPainter, QFont, QGuiApplication
from PyQt6.QtCore import Qt

import notify_app


def _make_square_icon(path, size=40, color="#89b4fa"):
    px = QPixmap(size, size)
    px.fill(QColor("transparent"))
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(2, 2, size - 4, size - 4, 8, 8)
    p.setPen(QColor("#1e1e2e"))
    f = QFont()
    f.setBold(True)
    f.setPointSize(20)
    p.setFont(f)
    p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "N")
    p.end()
    px.save(path)


def _make_banner(path, w=300, h=160):
    px = QPixmap(w, h)
    px.fill(QColor("#313244"))
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # franja decorativa
    p.setBrush(QColor("#89b4fa"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, w, 28, 0, 0)
    p.setPen(QColor("#cdd6f4"))
    f = QFont()
    f.setPointSize(14)
    p.setFont(f)
    p.drawText(px.rect().adjusted(0, 34, 0, 0),
               Qt.AlignmentFlag.AlignCenter, "IMAGEN DE PRUEBA")
    p.setPen(QColor("#a6adc8"))
    f.setPointSize(10)
    p.setFont(f)
    p.drawText(px.rect().adjusted(0, 60, 0, 0),
               Qt.AlignmentFlag.AlignCenter, "300 x 160 px")
    p.end()
    px.save(path)


def main():
    app = notify_app.QApplication(sys.argv)

    tmp = tempfile.mkdtemp(prefix="notify_test_")
    icon = os.path.join(tmp, "icon.png")
    banner = os.path.join(tmp, "banner.png")
    _make_square_icon(icon)
    _make_banner(banner)

    notif = notify_app.NotificacionPersonalizada(
        titulo="Notificación de prueba",
        cuerpo="Esta es una notificación con layout libre:\nicono + texto + imagen + barra animada.",
        icon_path=icon,
        image_path=banner,
        duration=8000,
    )
    notif.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
