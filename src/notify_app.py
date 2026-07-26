#!/usr/bin/env python3
"""
NotifyApp - Notificación personalizada con layout libre.

Layout:
┌─────────────────────────────────────────┐
│ [ICONO]  TÍTULO                        │
│         Cuerpo línea 1                  │
│         Cuerpo línea 2                  │
│                                         │
│ [IMAGEN GRANDE]                         │
│                                         │
│ ████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░ │  ← barra de tiempo
└─────────────────────────────────────────┘
"""

import sys
import os
import time
from PyQt5.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QProgressBar
)
from PyQt5.QtGui import QPixmap, QFont, QColor, QPainter
from PyQt5.QtCore import Qt, QTimer, QSize


class NotificacionPersonalizada(QWidget):
    def __init__(self, titulo="", cuerpo="", icon_path=None, image_path=None,
                 duration=8000, parent=None):
        super().__init__(parent)

        # Ventana sin bordes, siempre encima, fondo translúcido
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.duration = duration  # ms

        # === Layout principal ===
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === Card (fondo oscuro) ===
        self.card = QWidget()
        self.card.setObjectName("card")
        self.card.setStyleSheet("""
            #card {
                background-color: #1e1e2e;
                border: 1px solid #585b70;
                border-radius: 14px;
            }
        """)
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(10)

        # === Fila superior: icono + texto ===
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        # Icono pequeño
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(40, 40)
        self.icon_label.setStyleSheet("background: #313244; border-radius: 6px;")
        if icon_path and os.path.exists(icon_path):
            pixmap = QPixmap(icon_path).scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.icon_label.setPixmap(pixmap)
        top_row.addWidget(self.icon_label)

        # Texto (título + cuerpo)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        self.title_label = QLabel(titulo)
        self.title_label.setStyleSheet("""
            color: #cdd6f4;
            font-size: 14px;
            font-weight: bold;
        """)
        self.title_label.setWordWrap(True)

        self.body_label = QLabel(cuerpo)
        self.body_label.setStyleSheet("""
            color: #a6adc8;
            font-size: 12px;
            line-height: 1.4;
        """)
        self.body_label.setWordWrap(True)

        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.body_label)
        top_row.addLayout(text_layout)

        card_layout.addLayout(top_row)

        # === Imagen grande (opcional) ===
        self.image_label = QLabel()
        self.image_label.setStyleSheet("border-radius: 8px; overflow: hidden;")
        self.image_label.setAlignment(Qt.AlignCenter)
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path).scaled(
                300, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.image_label.setPixmap(pixmap)
            self.image_label.setFixedSize(pixmap.width(), pixmap.height())
            card_layout.addWidget(self.image_label)
        else:
            self.image_label.hide()

        # === Barra de tiempo animada ===
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.progress.setStyleSheet("""
            QProgressBar {
                background: #45475a;
                border-radius: 4px;
                border: none;
            }
            QProgressBar::chunk {
                background: #89b4fa;
                border-radius: 4px;
            }
        """)
        card_layout.addWidget(self.progress)

        self.card.setLayout(card_layout)
        main_layout.addWidget(self.card)
        self.setLayout(main_layout)

        # === Timer de cuenta regresiva ===
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(50)  # actualiza cada 50ms para animación fluida

        self.start_time = time.time()

    def update_progress(self):
        """Actualiza la barra de tiempo de forma fluida."""
        elapsed = (time.time() - self.start_time) * 1000  # ms
        remaining = max(0, self.duration - elapsed)
        pct = (remaining / self.duration) * 100
        self.progress.setValue(int(pct))

        if remaining <= 0:
            self.timer.stop()
            self.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Notificación personalizada")
    parser.add_argument("--title", default="Notificación", help="Título")
    parser.add_argument("--body", default="", help="Cuerpo")
    parser.add_argument("--icon", default=None, help="Ruta del icono")
    parser.add_argument("--image", default=None, help="Ruta de la imagen")
    parser.add_argument("--duration", type=int, default=8000, help="Duración en ms")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    notif = NotificacionPersonalizada(
        titulo=args.title,
        cuerpo=args.body,
        icon_path=args.icon,
        image_path=args.image,
        duration=args.duration
    )
    notif.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
