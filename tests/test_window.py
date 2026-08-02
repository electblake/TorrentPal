from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QMovie, QPixmap
from PySide6.QtWidgets import QGroupBox, QLabel, QPushButton, QTextBrowser

import torrentpal.window
from torrentpal.widgets import ImageGallery
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
    assert window.findChild(ImageGallery, "imageGallery") is not None
    assert window.findChild(QPushButton, "fetchImageButton").text() == "Fetch Image"
    assert window.statusBar().currentMessage() == "Ready"


def test_window_loads_cached_image(qtbot, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(torrentpal.window, "DATA_DIR", tmp_path)
    metadata = torrentpal.window.parse_torrent(FIXTURE)
    image_path = tmp_path / f"{metadata.info_hash_v1}_20x20_0"
    pixmap = QPixmap(20, 20)
    pixmap.fill(Qt.GlobalColor.red)
    pixmap.save(str(image_path), "PNG")
    window = MainWindow()
    qtbot.addWidget(window)

    window.open_torrent(FIXTURE)

    assert not window.findChild(QLabel, "mediaImage").pixmap().isNull()


def test_window_cycles_cached_images_largest_first(
    qtbot, tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(torrentpal.window, "DATA_DIR", tmp_path)
    metadata = torrentpal.window.parse_torrent(FIXTURE)
    large = tmp_path / f"{metadata.info_hash_v1}_20x20_0"
    small = tmp_path / f"{metadata.info_hash_v1}_10x10_1"
    for path, size in ((large, 20), (small, 10)):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.red)
        pixmap.save(str(path), "PNG")
    window = MainWindow()
    qtbot.addWidget(window)
    window.open_torrent(FIXTURE)
    gallery = window.findChild(ImageGallery, "imageGallery")

    assert gallery.pages.count() == 2
    assert gallery.pages.currentIndex() == 0
    assert gallery.page_label.text() == "1 / 2"
    qtbot.mouseClick(
        window.findChild(QPushButton, "nextImageButton"), Qt.MouseButton.LeftButton
    )
    assert gallery.pages.currentIndex() == 1
    assert gallery.page_label.text() == "2 / 2"
    qtbot.mouseClick(
        window.findChild(QPushButton, "previousImageButton"), Qt.MouseButton.LeftButton
    )
    assert gallery.pages.currentIndex() == 0


def test_image_fetch_updates_button_and_status(qtbot, monkeypatch) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.open_torrent(FIXTURE)
    gallery = window.findChild(ImageGallery, "imageGallery")

    def fetch_images(*arguments):
        report_status = arguments[-1]
        assert gallery.load_button.text() == "Fetching.."
        assert not gallery.load_button.isEnabled()
        report_status("Selecting qualifying images")
        return ()

    monkeypatch.setattr(torrentpal.window, "download_images", fetch_images)
    qtbot.mouseClick(gallery.load_button, Qt.MouseButton.LeftButton)

    assert gallery.load_button.text() == "Fetch Image"
    assert gallery.load_button.isEnabled()
    assert window.statusBar().currentMessage() == "Fetched and cached 0 images"


def test_image_fetch_reports_errors(qtbot, monkeypatch) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.open_torrent(FIXTURE)
    gallery = window.findChild(ImageGallery, "imageGallery")

    def fail_fetch(*arguments):
        raise RuntimeError("browser stopped")

    monkeypatch.setattr(torrentpal.window, "download_images", fail_fetch)

    with pytest.raises(RuntimeError, match="browser stopped"):
        window._load_images(torrentpal.window.parse_torrent(FIXTURE), gallery)

    assert gallery.load_button.text() == "Fetch Image"
    assert gallery.load_button.isEnabled()
    assert window.statusBar().currentMessage() == "Image fetch failed: browser stopped"


def test_window_plays_cached_animated_image(qtbot, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(torrentpal.window, "DATA_DIR", tmp_path)
    metadata = torrentpal.window.parse_torrent(FIXTURE)
    image_path = tmp_path / f"{metadata.info_hash_v1}_10x10_0"
    image_path.write_bytes(
        bytes.fromhex(
            "47494638396101000100800000000000ffffff"
            "21ff0b4e45545343415045322e300301000000"
            "21f904000a0000002c0000000001000100000202440100"
            "21f904000a0000002c0000000001000100000202440100"
            "3b"
        )
    )
    window = MainWindow()
    qtbot.addWidget(window)

    window.open_torrent(FIXTURE)

    movie = window.findChild(QLabel, "mediaImage").movie()
    assert movie is not None
    assert movie.state() == QMovie.MovieState.Running


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
    assert (
        window.findChild(QGroupBox, "imagesBrowserGroup").title() == "Images & Browser"
    )
    assert window.image_minimum_width.value() == 10
    assert window.image_minimum_height.value() == 10
    assert window.torrent_images_maximum.value() == 10
    assert window.cookies_path.text() == str(torrentpal.window.DATA_DIR / "cookies.txt")
    window.cookies_path.setText("C:/cookies.txt")
    window.image_minimum_width.setValue(320)
    window.image_minimum_height.setValue(180)
    window.torrent_images_maximum.setValue(6)
    qtbot.mouseClick(window.save_settings_button, Qt.MouseButton.LeftButton)

    assert settings.value("cookies_file", type=str) == "C:/cookies.txt"
    assert settings.value("image_minimum_width", type=int) == 320
    assert settings.value("image_minimum_height", type=int) == 180
    assert settings.value("torrent_images_maximum", type=int) == 6
    assert window.stack.currentWidget() is window.input_page

    qtbot.mouseClick(settings_button, Qt.MouseButton.LeftButton)
    assert window.cookies_path.text() == "C:/cookies.txt"
    assert window.image_minimum_width.value() == 320
    assert window.image_minimum_height.value() == 180
    assert window.torrent_images_maximum.value() == 6
    qtbot.mouseClick(window.reset_settings_button, Qt.MouseButton.LeftButton)
    assert window.cookies_path.text() == ""
    assert window.image_minimum_width.value() == 10
    assert window.image_minimum_height.value() == 10
    assert window.torrent_images_maximum.value() == 10
    assert not settings.contains("cookies_file")
    qtbot.mouseClick(window.cancel_settings_button, Qt.MouseButton.LeftButton)
    assert window.stack.currentWidget() is window.input_page


def test_settings_back_returns_to_input(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.stack.setCurrentWidget(window.settings_page)

    qtbot.mouseClick(
        window.findChild(QPushButton, "settingsBackButton"), Qt.MouseButton.LeftButton
    )

    assert window.stack.currentWidget() is window.input_page


def test_save_cookies_writes_default_data_file(qtbot, tmp_path, monkeypatch) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(torrentpal.window, "SETTINGS", settings)
    monkeypatch.setattr(torrentpal.window, "DATA_DIR", tmp_path)
    window = MainWindow()
    qtbot.addWidget(window)
    window.cookies_text.setPlainText('[{"name": "sid"}]')

    qtbot.mouseClick(window.save_cookies_button, Qt.MouseButton.LeftButton)

    assert (tmp_path / "cookies.txt").read_text(encoding="utf-8") == '[{"name": "sid"}]'
    assert settings.value("cookies_file", type=str) == str(tmp_path / "cookies.txt")
