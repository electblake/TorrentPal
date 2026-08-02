import sys

from PySide6.QtWidgets import QApplication

from torrentpal.window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("TorrentPal")
    window = MainWindow()
    window.show()
    raise SystemExit(app.exec())
