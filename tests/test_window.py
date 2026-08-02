from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QPushButton, QTextBrowser

import torrentpal.window
from torrentpal.window import MainWindow

FIXTURE = Path(__file__).parent / "fixtures" / "known.torrent"


def test_window_opens_torrent(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.open_torrent(FIXTURE)
    assert window.stack.currentWidget() is not window.input_page
    comment = window.findChild(QTextBrowser, "commentBrowser")
    assert comment.toPlainText() == "See https://example.com"
    assert 'href="https://example.com"' in comment.document().toHtml()
    assert comment.openExternalLinks()


def test_settings_routes_and_persists(qtbot, tmp_path, monkeypatch) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(torrentpal.window, "SETTINGS", settings)
    window = MainWindow()
    qtbot.addWidget(window)

    settings_button = next(
        button
        for button in window.input_page.findChildren(QPushButton)
        if button.text() == "Settings"
    )
    qtbot.mouseClick(settings_button, Qt.MouseButton.LeftButton)
    window.cookies_path.setText("C:/cookies.txt")
    qtbot.mouseClick(window.save_settings_button, Qt.MouseButton.LeftButton)

    assert settings.value("cookies_file", type=str) == "C:/cookies.txt"
    assert window.stack.currentWidget() is window.input_page

    qtbot.mouseClick(settings_button, Qt.MouseButton.LeftButton)
    assert window.cookies_path.text() == "C:/cookies.txt"
    qtbot.mouseClick(window.reset_settings_button, Qt.MouseButton.LeftButton)
    assert window.cookies_path.text() == ""
    assert not settings.contains("cookies_file")
    qtbot.mouseClick(window.cancel_settings_button, Qt.MouseButton.LeftButton)
    assert window.stack.currentWidget() is window.input_page
