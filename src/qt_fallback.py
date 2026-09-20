"""Fallback PyQt6 para la notificación one-shot de verdantis.

Se carga SOLO cuando se necesita (import perezoso desde verdantis.main):
el daemon GTK y el entry-point no deben pagar el import de Qt (auditoría:
era top-level y el daemon arrancaba cargando PyQt6 igual).

Equivalente funcional del WaylandPopup para sesiones sin layer-shell.
"""
import sys
import os
import time
from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QProgressBar
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QTimer


class NotificacionPersonalizada(QWidget):
    def __init__(self, titulo="", cuerpo="", icon_path=None, image_path=None,
                 duration=8000, margin=16, corner="top-right", accent="#89b4fa",
                 on_click=None, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.SplashScreen
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.duration = duration
        self.margin = margin
        self.corner = corner
        self.accent = accent
        self._on_click = on_click

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.card = QWidget()
        self.card.setObjectName("card")
        self.card.setStyleSheet(f"""
            #card {{
                background-color: #1e1e2e;
                border: 1px solid #585b70;
                border-radius: 14px;
            }}
            #card:hover {{
                border: 1px solid {accent};
            }}
        """)
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(32, 32)
        self.icon_label.setStyleSheet("background: #313244; border-radius: 6px;")
        if icon_path and os.path.exists(icon_path):
            pixmap = QPixmap(icon_path).scaled(
                32, 32, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.icon_label.setPixmap(pixmap)
        top_row.addWidget(self.icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        self.title_label = QLabel(titulo)
        self.title_label.setStyleSheet("color: #cdd6f4; font-size: 13px; font-weight: bold;")
        self.title_label.setWordWrap(True)
        self.body_label = QLabel(cuerpo)
        self.body_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        self.body_label.setWordWrap(True)
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.body_label)
        top_row.addLayout(text_layout)
        card_layout.addLayout(top_row)

        self.image_label = QLabel()
        self.image_label.setStyleSheet("border-radius: 8px;")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path).scaled(
                260, 140, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(pixmap)
            self.image_label.setFixedSize(pixmap.width(), pixmap.height())
            card_layout.addWidget(self.image_label)
        else:
            self.image_label.hide()

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background: #45475a; border-radius: 4px; border: none;
            }}
            QProgressBar::chunk {{
                background: {self.accent}; border-radius: 4px;
            }}
        """)
        card_layout.addWidget(self.progress)
        self.card.setLayout(card_layout)
        main_layout.addWidget(self.card)
        self.setLayout(main_layout)
        self.setFixedWidth(320)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(50)
        self.start_time = time.time()

    def mousePressEvent(self, event):
        if self._on_click:
            self._on_click()
        self.close()
        QApplication.instance().quit()

    def update_progress(self):
        elapsed = (time.time() - self.start_time) * 1000
        remaining = max(0, self.duration - elapsed)
        self.progress.setValue(int((remaining / self.duration) * 100))
        if remaining <= 0:
            self.timer.stop()
            self.close()
            QApplication.instance().quit()

    def show(self):
        screen = QApplication.primaryScreen().availableGeometry()
        w = self.width() or 320
        h = self.height() or 200
        m = self.margin
        x, y = m, m
        if "right" in self.corner:
            x = screen.right() - w - m
        if "bottom" in self.corner:
            y = screen.bottom() - h - m
        self.move(x, y)
        super().show()
