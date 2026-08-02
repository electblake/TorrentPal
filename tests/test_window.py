from pathlib import Path

from PySide6.QtWidgets import QTextBrowser

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
