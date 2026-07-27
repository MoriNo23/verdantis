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
│ ████████████░░░░░░░░░░░░░░░░░░░░░░░░░░ │  ← barra de tiempo
└─────────────────────────────────────────┘
"""

import sys
import os
import time
from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QProgressBar
)
from PyQt6.QtGui import QPixmap, QFont, QColor, QPainter, QIcon
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal


class NotificacionPersonalizada(QWidget):
    clicked = pyqtSignal()

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
        self.setWindowTitle("NotifyApp")
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
        elif icon_path:
            icon = QIcon.fromTheme(icon_path)
            if not icon.isNull():
                self.icon_label.setPixmap(icon.pixmap(32, 32))
        top_row.addWidget(self.icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        self.title_label = QLabel(titulo)
        self.title_label.setStyleSheet("""
            color: #cdd6f4;
            font-size: 13px;
            font-weight: bold;
        """)
        self.title_label.setWordWrap(True)

        self.body_label = QLabel(cuerpo)
        self.body_label.setStyleSheet("""
            color: #a6adc8;
            font-size: 11px;
        """)
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
                background: #45475a;
                border-radius: 4px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {self.accent};
                border-radius: 4px;
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
        self.clicked.emit()
        if self._on_click or self.clicked.receivers(self.clicked) > 1:
            self.close()
            QApplication.instance().quit()

    def update_progress(self):
        elapsed = (time.time() - self.start_time) * 1000
        remaining = max(0, self.duration - elapsed)
        pct = (remaining / self.duration) * 100
        self.progress.setValue(int(pct))

        if remaining <= 0:
            self.timer.stop()
            self.close()
            QApplication.instance().quit()

    def show(self):
        self._apply_kwin_rule()
        self._apply_geometry()
        super().show()

    def _apply_geometry(self):
        try:
            screen = QApplication.primaryScreen().availableGeometry()
            w = self.width() or self.sizeHint().width() or 320
            h = self.height() or self.sizeHint().height() or 200
            m = self.margin
            x, y = m, m
            if "right" in self.corner:
                x = screen.right() - w - m
            if "bottom" in self.corner:
                y = screen.bottom() - h - m
            self.move(x, y)
        except Exception:
            pass

    def _apply_kwin_rule(self):
        try:
            screen = QApplication.primaryScreen().availableGeometry()
            w = self.width() or self.sizeHint().width() or 320
            h = self.height() or self.sizeHint().height() or 200
            m = self.margin
            x, y = m, m
            if "right" in self.corner:
                x = screen.right() - w - m
            if "bottom" in self.corner:
                y = screen.bottom() - h - m
            # KWin exige mayusculas exactas en las claves de kwinrulesrc
            path = os.path.expanduser("~/.config/kwinrulesrc")
            content = (
                "[General]\n"
                "count=1\n"
                "rulecount=1\n"
                "\n"
                "[1]\n"
                "Description=Posicion fija NotifyApp\n"
                "Title=NotifyApp\n"
                "Titleop=2\n"
                f"Position={x},{y}\n"
                "Positionop=2\n"
            )
            with open(path, "w") as f:
                f.write(content)
            # Forzar recarga de reglas en KWin
            import subprocess, time
            subprocess.run(["dbus-send", "--session", "--dest=org.kde.KWin",
                            "/KWin", "org.kde.KWin.reconfigure"],
                           capture_output=True, timeout=2)
            time.sleep(0.15)
        except Exception:
            pass


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Notificación personalizada")
    parser.add_argument("--title", default="Notificación")
    parser.add_argument("--body", default="")
    parser.add_argument("--icon", default=None)
    parser.add_argument("--image", default=None)
    parser.add_argument("--duration", type=int, default=8000)
    parser.add_argument("--margin", type=int, default=16)
    parser.add_argument("--corner", default="top-right",
                        choices=["top-right", "top-left", "bottom-right", "bottom-left"])
    parser.add_argument("--accent", default="#89b4fa",
                        help="Color de acento (hex)")
    args = parser.parse_args()

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("notify-app")
    app.setDesktopFileName("notify-app")
    notif = NotificacionPersonalizada(
        titulo=args.title,
        cuerpo=args.body,
        icon_path=args.icon,
        image_path=args.image,
        duration=args.duration,
        margin=args.margin,
        corner=args.corner,
        accent=args.accent
    )
    notif.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
