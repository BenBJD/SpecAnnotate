from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
import sys
from pathlib import Path

from app.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("assets/spectrogram.svg"))

    win = MainWindow()
    win.setWindowIcon(app.windowIcon())
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
