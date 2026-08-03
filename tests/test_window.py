import json
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QPointF, QSettings, Qt, QUrl
from PySide6.QtGui import QDropEvent, QMovie, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QLabel,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QWidget,
)

import torrentpal.torrent_loader
import torrentpal.window
from torrentpal.domain import Tag
from torrentpal.metadata_cache import load_cached_metadata, metadata_cache_path
from torrentpal.widgets import (
    ImageGallery,
    TagGrid,
    TorrentFileList,
    TorrentFileListItem,
    TorrentFileListItemWidget,
)
from torrentpal.window import MainWindow

FIXTURE = Path(__file__).parent / "fixtures" / "known.torrent"


@pytest.fixture(autouse=True)
def isolate_torrent_data(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(torrentpal.window, "DATA_DIR", tmp_path / "app-data")
    settings = QSettings(
        str(tmp_path / "default-settings.ini"), QSettings.Format.IniFormat
    )
    monkeypatch.setattr(torrentpal.window, "SETTINGS", settings)


def write_torrent(path: Path, name: str) -> Path:
    encoded_name = name.encode()
    contents = FIXTURE.read_bytes().replace(
        b"4:name9:known.bin",
        b"4:name" + str(len(encoded_name)).encode() + b":" + encoded_name,
    )
    path.write_bytes(contents)
    return path


def wait_for_torrent_scan(qtbot, window: MainWindow) -> None:
    qtbot.waitUntil(lambda: not window.torrents.is_loading, timeout=10_000)


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
    assert window.findChild(TagGrid, "tagGrid") is not None
    assert window.findChild(QPushButton, "fetchTagsButton").text() == "Fetch Tags"
    assert window.findChild(QPushButton, "fetchImageButton").text() == "Fetch Image"
    assert window.statusBar().currentMessage() == "Ready"


def test_home_uses_fluid_splitter_and_compact_import_group(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    splitter = window.findChild(QSplitter, "homeSplitter")

    assert splitter.orientation() == Qt.Orientation.Vertical
    assert splitter.widget(0) is window.drop_zone
    assert splitter.widget(1) is window.torrents
    assert window.drop_zone.minimumHeight() == 0
    assert window.drop_zone.maximumHeight() == 16777215
    assert window.torrents.minimumHeight() == 0
    assert window.torrents.maximumHeight() == 16777215
    assert window.drop_zone.layout().count() == 3
    assert window.drop_zone.status_label.isHidden()
    assert not any(
        label.text().startswith("or") for label in window.drop_zone.findChildren(QLabel)
    )

    available_height = sum(splitter.sizes())
    splitter.setSizes(
        [available_height // 2, available_height - available_height // 2]
    )
    QApplication.processEvents()
    top_height, bottom_height = splitter.sizes()
    assert top_height / (top_height + bottom_height) == pytest.approx(0.5, abs=0.02)


def test_results_use_resizable_image_and_details_split(
    qtbot, tmp_path, monkeypatch
) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    metadata = torrentpal.window.parse_torrent(FIXTURE)
    image_path = tmp_path / f"{metadata.info_hash_v1}_1600x900_0"
    pixmap = QPixmap(1600, 900)
    pixmap.fill(Qt.GlobalColor.red)
    pixmap.save(str(image_path), "PNG")
    monkeypatch.setattr(torrentpal.window, "DATA_DIR", tmp_path)
    monkeypatch.setattr(torrentpal.window, "SETTINGS", settings)
    window = MainWindow()
    qtbot.addWidget(window)
    window.open_torrent(FIXTURE)
    window.show()
    qtbot.waitExposed(window)

    splitter = window.findChild(QSplitter, "resultsSplitter")
    gallery = window.findChild(ImageGallery, "imageGallery")
    details = window.findChild(QWidget, "resultsDetails")
    back = window.findChild(QPushButton, "resultsBackButton")
    title = window.findChild(QLabel, "torrentTitle")

    assert splitter.orientation() == Qt.Orientation.Horizontal
    assert not splitter.childrenCollapsible()
    assert splitter.widget(0) is gallery
    assert splitter.widget(1).isAncestorOf(details)
    assert not splitter.isAncestorOf(back)
    assert not splitter.isAncestorOf(title)
    assert details.isAncestorOf(window.findChild(TagGrid, "tagGrid"))
    metadata_group = next(
        group for group in details.findChildren(QGroupBox) if group.title() == "Metadata"
    )
    assert details.isAncestorOf(metadata_group)
    left_width, right_width = splitter.sizes()
    assert left_width / (left_width + right_width) == pytest.approx(0.6, abs=0.02)
    available_width = left_width + right_width
    splitter.setSizes([available_width // 2, available_width - available_width // 2])
    QApplication.processEvents()
    resized_left_width, resized_right_width = splitter.sizes()
    assert resized_left_width / (
        resized_left_width + resized_right_width
    ) == pytest.approx(0.5, abs=0.02)
    image = gallery.pages.currentWidget()
    assert image.pixmap().width() <= gallery.pages.contentsRect().width()
    assert image.pixmap().height() <= gallery.pages.contentsRect().height()


def test_home_downloads_torrent_url_and_opens_file(
    qtbot, tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(torrentpal.window, "DATA_DIR", tmp_path)
    window = MainWindow()
    qtbot.addWidget(window)
    requested_url = (
        "https://tracker.example/download.php?id=42&authkey=secret&torrent_pass=pass"
    )
    downloaded_paths = []

    def fetch_torrent(url, destination_directory):
        assert url == requested_url
        downloaded_path = destination_directory / "downloaded.torrent"
        downloaded_path.write_bytes(FIXTURE.read_bytes())
        downloaded_paths.append(downloaded_path)
        return downloaded_path

    monkeypatch.setattr(torrentpal.window, "download_torrent", fetch_torrent)
    window.drop_zone.url_input.setText(requested_url)

    assert window.drop_zone.download_button.isEnabled()
    qtbot.mouseClick(window.drop_zone.download_button, Qt.MouseButton.LeftButton)
    wait_for_torrent_scan(qtbot, window)

    assert window.stack.currentWidget() is not window.input_page
    assert window.statusBar().currentMessage() == "Torrent downloaded and loaded"
    assert window.drop_zone.url_status.text() == "Torrent downloaded and loaded"
    assert window.drop_zone.url_input.text() == ""
    assert not window.drop_zone.download_button.isEnabled()
    assert not downloaded_paths[0].exists()
    stored_paths = tuple((tmp_path / "torrents").glob("*.torrent"))
    assert len(stored_paths) == 1
    assert stored_paths[0].read_bytes() == FIXTURE.read_bytes()
    assert window.torrents.list.count() == 1


def test_home_lists_torrents_and_click_loads_them(
    qtbot, tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(torrentpal.window, "DATA_DIR", tmp_path)
    torrent_directory = tmp_path / "torrents"
    torrent_directory.mkdir()
    saved_torrent = torrent_directory / "saved.torrent"
    saved_torrent.write_bytes(FIXTURE.read_bytes())
    metadata = torrentpal.window.parse_torrent(FIXTURE)
    (tmp_path / f"{metadata.info_hash_v1}_20x20_0").write_bytes(b"image")
    (tmp_path / f"{metadata.info_hash_v1}_30x30_1").write_bytes(b"image")

    window = MainWindow()
    qtbot.addWidget(window)
    wait_for_torrent_scan(qtbot, window)
    item = window.torrents.list.item(0)
    item_widget = window.torrents.list.itemWidget(item)

    assert window.torrents.title() == "Torrents"
    assert isinstance(window.torrents.list, TorrentFileList)
    assert isinstance(item, TorrentFileListItem)
    assert isinstance(item_widget, TorrentFileListItemWidget)
    assert window.torrents.list.count() == 1
    assert item.entry.display_name == metadata.name
    assert item.entry.cached_image_count == 2
    assert item.toolTip() == str(saved_torrent)
    assert item_widget.cached_images_label.text() == "2 cached images"
    assert item_widget.metadata_cache_label.text() == "Metadata cached"
    assert "1 file" in item_widget.details_label.text()

    window.show()
    qtbot.waitExposed(window)
    qtbot.mouseClick(
        window.torrents.list.viewport(),
        Qt.MouseButton.LeftButton,
        pos=window.torrents.list.visualItemRect(item).center(),
    )

    assert window.stack.currentWidget() is not window.input_page
    assert window.findChild(QTextBrowser, "commentBrowser") is not None


def test_home_refreshes_torrents_when_returning(
    qtbot, tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(torrentpal.window, "DATA_DIR", tmp_path)
    window = MainWindow()
    qtbot.addWidget(window)
    wait_for_torrent_scan(qtbot, window)
    assert window.torrents.list.count() == 0

    torrent_directory = tmp_path / "torrents"
    torrent_directory.mkdir()
    (torrent_directory / "new.torrent").write_bytes(FIXTURE.read_bytes())

    window._show_input_page()
    wait_for_torrent_scan(qtbot, window)

    assert window.torrents.list.count() == 1


def test_home_streams_torrents_from_worker_thread(
    qtbot, tmp_path, monkeypatch
) -> None:
    torrent_directory = tmp_path / "torrents"
    torrent_directory.mkdir()
    for index in range(3):
        write_torrent(
            torrent_directory / f"torrent-{index}.torrent",
            f"torrent-{index}.bin",
        )
    original_parse_torrent = torrentpal.torrent_loader.parse_torrent

    def slow_parse_torrent(path):
        time.sleep(0.08)
        return original_parse_torrent(path)

    monkeypatch.setattr(
        torrentpal.torrent_loader, "parse_torrent", slow_parse_torrent
    )
    monkeypatch.setattr(torrentpal.window, "DATA_DIR", tmp_path)

    window = MainWindow()
    qtbot.addWidget(window)
    loader = next(iter(window._torrent_loaders.values()))

    assert loader.thread() is not window.thread()
    assert window.torrents.list.thread() is window.thread()
    assert window.torrents.is_loading
    assert not window.torrents.progress_bar.isHidden()
    qtbot.waitUntil(
        lambda: window.torrents.list.count() >= 1,
        timeout=10_000,
    )
    assert window.torrents.is_loading
    assert window.torrents.list.count() < 3
    assert "torrent-" in window.torrents.progress_bar.format()

    wait_for_torrent_scan(qtbot, window)

    assert window.torrents.list.count() == 3
    assert window.torrents.progress_bar.isHidden()


def test_metadata_scan_setting_can_list_without_parsing(
    qtbot, tmp_path, monkeypatch
) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("scan_torrent_metadata", False)
    torrent_directory = tmp_path / "torrents"
    torrent_directory.mkdir()
    invalid_torrent = torrent_directory / "unparsed.torrent"
    invalid_torrent.write_text("not bencoded torrent data", encoding="utf-8")
    monkeypatch.setattr(torrentpal.window, "DATA_DIR", tmp_path)
    monkeypatch.setattr(torrentpal.window, "SETTINGS", settings)

    window = MainWindow()
    qtbot.addWidget(window)
    wait_for_torrent_scan(qtbot, window)
    item = window.torrents.list.item(0)
    item_widget = window.torrents.list.itemWidget(item)

    assert window.torrents.list.count() == 1
    assert item.entry.display_name == "unparsed.torrent"
    assert item.entry.total_size is None
    assert item_widget.details_label.text() == "Metadata scan disabled"
    assert not metadata_cache_path(tmp_path, invalid_torrent).exists()


def test_open_torrent_prefers_cached_metadata(qtbot, tmp_path, monkeypatch) -> None:
    torrent_directory = tmp_path / "torrents"
    torrent_directory.mkdir()
    saved_torrent = torrent_directory / "saved.torrent"
    saved_torrent.write_bytes(FIXTURE.read_bytes())
    monkeypatch.setattr(torrentpal.window, "DATA_DIR", tmp_path)
    window = MainWindow()
    qtbot.addWidget(window)
    wait_for_torrent_scan(qtbot, window)
    saved_torrent.write_text("now unreadable", encoding="utf-8")

    window.open_torrent(saved_torrent)

    assert window.stack.currentWidget() is not window.input_page
    assert (
        window.stack.currentWidget().findChild(QLabel, "torrentTitle").text()
        == "known.bin"
    )
    assert window.statusBar().currentMessage() == "Loaded cached torrent metadata"


def test_reload_metadata_updates_json_cache_in_worker_thread(
    qtbot, tmp_path, monkeypatch
) -> None:
    torrent_directory = tmp_path / "torrents"
    torrent_directory.mkdir()
    saved_torrent = torrent_directory / "saved.torrent"
    saved_torrent.write_bytes(FIXTURE.read_bytes())
    monkeypatch.setattr(torrentpal.window, "DATA_DIR", tmp_path)
    window = MainWindow()
    qtbot.addWidget(window)
    wait_for_torrent_scan(qtbot, window)
    window.open_torrent(saved_torrent)
    write_torrent(saved_torrent, "updated.bin")
    reload_button = window.stack.currentWidget().findChild(
        QPushButton, "reloadMetadataButton"
    )

    qtbot.mouseClick(reload_button, Qt.MouseButton.LeftButton)
    reload_worker = next(iter(window._metadata_reload_workers.values()))

    assert reload_worker.thread() is not window.thread()
    qtbot.waitUntil(
        lambda: window.statusBar().currentMessage()
        == "Metadata reloaded and cache updated",
        timeout=10_000,
    )
    assert (
        window.stack.currentWidget().findChild(QLabel, "torrentTitle").text()
        == "updated.bin"
    )
    assert load_cached_metadata(tmp_path, saved_torrent).name == "updated.bin"


def test_home_imports_multiple_selected_torrents_without_removing_sources(
    qtbot, tmp_path, monkeypatch
) -> None:
    data_directory = tmp_path / "app-data"
    source_directory = tmp_path / "selected"
    source_directory.mkdir()
    first = write_torrent(source_directory / "first.torrent", "first.bin")
    second = write_torrent(source_directory / "second.torrent", "second.bin")
    monkeypatch.setattr(torrentpal.window, "DATA_DIR", data_directory)
    monkeypatch.setattr(
        torrentpal.window.QFileDialog,
        "getOpenFileNames",
        lambda *arguments: ([str(first), str(second)], "Torrent files (*.torrent)"),
    )
    window = MainWindow()
    qtbot.addWidget(window)

    qtbot.mouseClick(window.drop_zone.browse_button, Qt.MouseButton.LeftButton)
    wait_for_torrent_scan(qtbot, window)

    assert window.stack.currentWidget() is window.input_page
    assert first.exists()
    assert second.exists()
    assert len(tuple((data_directory / "torrents").glob("*.torrent"))) == 2
    assert window.torrents.list.count() == 2
    assert window.drop_zone.import_status.text() == "Imported 2 torrents"
    assert window.statusBar().currentMessage() == "Imported 2 torrents"


def test_home_imports_folder_torrents_and_reports_invalid_files(
    qtbot, tmp_path, monkeypatch
) -> None:
    data_directory = tmp_path / "app-data"
    source_directory = tmp_path / "folder"
    source_directory.mkdir()
    first = write_torrent(source_directory / "first.torrent", "first.bin")
    second = write_torrent(source_directory / "second.TORRENT", "second.bin")
    invalid = source_directory / "invalid.torrent"
    invalid.write_text("not a torrent", encoding="utf-8")
    (source_directory / "notes.txt").write_text("ignore me", encoding="utf-8")
    monkeypatch.setattr(torrentpal.window, "DATA_DIR", data_directory)
    monkeypatch.setattr(
        torrentpal.window.QFileDialog,
        "getExistingDirectory",
        lambda *arguments: str(source_directory),
    )
    window = MainWindow()
    qtbot.addWidget(window)

    qtbot.mouseClick(window.drop_zone.folder_button, Qt.MouseButton.LeftButton)
    wait_for_torrent_scan(qtbot, window)

    assert window.stack.currentWidget() is window.input_page
    assert first.exists()
    assert second.exists()
    assert invalid.exists()
    assert len(tuple((data_directory / "torrents").glob("*.torrent"))) == 2
    assert window.torrents.list.count() == 2
    assert window.drop_zone.import_status.text().startswith(
        "Imported 2 torrents; 1 failed: invalid.torrent:"
    )


def test_home_drag_drop_imports_multiple_torrents(qtbot, tmp_path, monkeypatch) -> None:
    data_directory = tmp_path / "app-data"
    source_directory = tmp_path / "dropped"
    source_directory.mkdir()
    first = write_torrent(source_directory / "first.torrent", "first.bin")
    second = write_torrent(source_directory / "second.torrent", "second.bin")
    monkeypatch.setattr(torrentpal.window, "DATA_DIR", data_directory)
    window = MainWindow()
    qtbot.addWidget(window)
    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(first), QUrl.fromLocalFile(second)])
    event = QDropEvent(
        QPointF(10, 10),
        Qt.DropAction.CopyAction,
        mime_data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    window.drop_zone.dropEvent(event)
    wait_for_torrent_scan(qtbot, window)

    assert event.isAccepted()
    assert first.exists()
    assert second.exists()
    assert len(tuple((data_directory / "torrents").glob("*.torrent"))) == 2
    assert window.torrents.list.count() == 2
    assert window.drop_zone.import_status.text() == "Imported 2 torrents"


def test_home_reimport_keeps_one_managed_torrent(qtbot, tmp_path, monkeypatch) -> None:
    data_directory = tmp_path / "app-data"
    source_directory = tmp_path / "duplicates"
    source_directory.mkdir()
    first = source_directory / "first.torrent"
    second = source_directory / "second.torrent"
    first.write_bytes(FIXTURE.read_bytes())
    second.write_bytes(FIXTURE.read_bytes())
    monkeypatch.setattr(torrentpal.window, "DATA_DIR", data_directory)
    window = MainWindow()
    qtbot.addWidget(window)

    window._import_torrent_paths((first, second))
    wait_for_torrent_scan(qtbot, window)

    assert first.exists()
    assert second.exists()
    assert len(tuple((data_directory / "torrents").glob("*.torrent"))) == 1
    assert window.torrents.list.count() == 1
    assert window.drop_zone.import_status.text() == (
        "Imported 1 torrent; 1 torrent already in Torrents"
    )


def test_home_reports_torrent_url_download_error(qtbot, monkeypatch) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    def fail_download(url, destination_directory):
        raise RuntimeError("Server returned HTTP 403: Forbidden")

    monkeypatch.setattr(torrentpal.window, "download_torrent", fail_download)
    window.drop_zone.url_input.setText(
        "https://tracker.example/download.php?authkey=secret"
    )

    qtbot.mouseClick(window.drop_zone.download_button, Qt.MouseButton.LeftButton)

    expected_status = (
        "Could not download and load torrent: Server returned HTTP 403: Forbidden"
    )
    assert window.stack.currentWidget() is window.input_page
    assert window.statusBar().currentMessage() == expected_status
    assert window.drop_zone.url_status.text() == expected_status
    assert window.drop_zone.url_input.isEnabled()
    assert window.drop_zone.download_button.isEnabled()


def test_home_pastes_valid_torrent_url_from_clipboard(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    clipboard_url = (
        "https://tracker.example/download.php?id=42&authkey=secret&torrent_pass=pass"
    )
    QApplication.clipboard().setText(f"  {clipboard_url}  ")

    qtbot.mouseClick(window.drop_zone.paste_button, Qt.MouseButton.LeftButton)

    assert window.drop_zone.url_input.text() == clipboard_url
    assert window.drop_zone.download_button.isEnabled()
    assert window.drop_zone.url_status.text() == "Torrent URL pasted from clipboard"


def test_home_rejects_invalid_clipboard_text_without_replacing_url(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    existing_url = "https://tracker.example/original.torrent?authkey=secret"
    window.drop_zone.url_input.setText(existing_url)
    QApplication.clipboard().setText("not a URL")

    qtbot.mouseClick(window.drop_zone.paste_button, Qt.MouseButton.LeftButton)

    assert window.drop_zone.url_input.text() == existing_url
    assert window.drop_zone.url_status.text() == (
        "Clipboard does not contain a valid HTTP or HTTPS URL"
    )


def test_window_loads_cached_image(qtbot, tmp_path, monkeypatch) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(torrentpal.window, "DATA_DIR", tmp_path)
    monkeypatch.setattr(torrentpal.window, "SETTINGS", settings)
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
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(torrentpal.window, "DATA_DIR", tmp_path)
    monkeypatch.setattr(torrentpal.window, "SETTINGS", settings)
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


def test_image_fetch_rejects_empty_results(qtbot, tmp_path, monkeypatch) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(torrentpal.window, "SETTINGS", settings)
    window = MainWindow()
    qtbot.addWidget(window)
    window.open_torrent(FIXTURE)
    gallery = window.findChild(ImageGallery, "imageGallery")

    def fetch_images(*arguments):
        report_status = arguments[-1]
        assert arguments[-2] == 120
        assert gallery.load_button.text() == "Fetching.."
        assert not gallery.load_button.isEnabled()
        report_status("Selecting qualifying images")
        return ()

    monkeypatch.setattr(torrentpal.window, "download_images", fetch_images)
    qtbot.mouseClick(gallery.load_button, Qt.MouseButton.LeftButton)

    assert gallery.load_button.text() == "Fetch Image"
    assert gallery.load_button.isEnabled()
    assert window.statusBar().currentMessage() == (
        "Image fetch failed: No qualifying images were returned"
    )


def test_image_fetch_reports_errors(qtbot, monkeypatch) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.open_torrent(FIXTURE)
    gallery = window.findChild(ImageGallery, "imageGallery")

    def fail_fetch(*arguments):
        raise RuntimeError("browser stopped")

    monkeypatch.setattr(torrentpal.window, "download_images", fail_fetch)

    window._load_images(torrentpal.window.parse_torrent(FIXTURE), gallery)

    assert gallery.load_button.text() == "Fetch Image"
    assert gallery.load_button.isEnabled()
    assert window.statusBar().currentMessage() == "Image fetch failed: browser stopped"


def test_window_plays_cached_animated_image(qtbot, tmp_path, monkeypatch) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(torrentpal.window, "DATA_DIR", tmp_path)
    monkeypatch.setattr(torrentpal.window, "SETTINGS", settings)
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
    assert window.tracker_page_timeout.value() == 120
    assert window.click_all_hidden_contents.isChecked()
    assert window.scan_torrent_metadata.isChecked()
    assert window.tag_selectors.toPlainText() == "#torrent_tags_list"
    assert window.tag_minimum_link_text_length.value() == 3
    assert window.tag_name_excludes.toPlainText() == "\\[-\\]\n\\[N\\]"
    assert window.cookies_path.text() == str(
        torrentpal.window.DATA_DIR / "cookies.json"
    )
    window.cookies_path.setText("C:/cookies.txt")
    window.image_minimum_width.setValue(320)
    window.image_minimum_height.setValue(180)
    window.torrent_images_maximum.setValue(6)
    window.tracker_page_timeout.setValue(240)
    window.click_all_hidden_contents.setChecked(False)
    window.scan_torrent_metadata.setChecked(False)
    window.tag_selectors.setPlainText("#torrent_tags_list\n.tags")
    window.tag_minimum_link_text_length.setValue(4)
    window.tag_name_excludes.setPlainText("\\[-\\]\nignore")
    qtbot.mouseClick(window.save_settings_button, Qt.MouseButton.LeftButton)

    assert settings.value("cookies_file", type=str) == "C:/cookies.txt"
    assert settings.value("image_minimum_width", type=int) == 320
    assert settings.value("image_minimum_height", type=int) == 180
    assert settings.value("torrent_images_maximum", type=int) == 6
    assert settings.value("tracker_page_timeout_seconds", type=int) == 240
    assert not settings.value("click_all_hidden_contents", type=bool)
    assert not settings.value("scan_torrent_metadata", type=bool)
    assert settings.value("tag_selectors", type=str) == "#torrent_tags_list\n.tags"
    assert settings.value("tag_minimum_link_text_length", type=int) == 4
    assert settings.value("tag_name_excludes", type=str) == "\\[-\\]\nignore"
    assert window.stack.currentWidget() is window.input_page

    qtbot.mouseClick(settings_button, Qt.MouseButton.LeftButton)
    assert window.cookies_path.text() == "C:/cookies.txt"
    assert window.image_minimum_width.value() == 320
    assert window.image_minimum_height.value() == 180
    assert window.torrent_images_maximum.value() == 6
    assert window.tracker_page_timeout.value() == 240
    assert not window.click_all_hidden_contents.isChecked()
    assert not window.scan_torrent_metadata.isChecked()
    assert window.tag_selectors.toPlainText() == "#torrent_tags_list\n.tags"
    assert window.tag_minimum_link_text_length.value() == 4
    assert window.tag_name_excludes.toPlainText() == "\\[-\\]\nignore"
    qtbot.mouseClick(window.reset_settings_button, Qt.MouseButton.LeftButton)
    assert window.cookies_path.text() == ""
    assert window.image_minimum_width.value() == 10
    assert window.image_minimum_height.value() == 10
    assert window.torrent_images_maximum.value() == 10
    assert window.tracker_page_timeout.value() == 120
    assert window.click_all_hidden_contents.isChecked()
    assert window.scan_torrent_metadata.isChecked()
    assert window.tag_selectors.toPlainText() == "#torrent_tags_list"
    assert window.tag_minimum_link_text_length.value() == 3
    assert window.tag_name_excludes.toPlainText() == "\\[-\\]\n\\[N\\]"
    assert not settings.contains("cookies_file")
    assert not settings.contains("tracker_page_timeout_seconds")
    assert not settings.contains("scan_torrent_metadata")
    qtbot.mouseClick(window.cancel_settings_button, Qt.MouseButton.LeftButton)
    assert window.stack.currentWidget() is window.input_page


def test_tag_fetch_populates_grid_and_status(qtbot, tmp_path, monkeypatch) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(torrentpal.window, "SETTINGS", settings)
    window = MainWindow()
    qtbot.addWidget(window)
    window.open_torrent(FIXTURE)
    grid = window.findChild(TagGrid, "tagGrid")

    def fetch_tags(*arguments):
        assert arguments[-2] == 120
        assert grid.load_button.text() == "Fetching.."
        assert not grid.load_button.isEnabled()
        return (
            Tag("fake.tits", "https://example.com/torrents.php?taglist=fake.tits"),
            Tag("amateur", "https://example.com/torrents.php?taglist=amateur"),
        )

    monkeypatch.setattr(torrentpal.window, "download_tags", fetch_tags)
    qtbot.mouseClick(grid.load_button, Qt.MouseButton.LeftButton)

    labels = window.findChildren(QLabel, "torrentTag")
    assert [label.text() for label in labels] == [
        '<a href="https://example.com/torrents.php?taglist=fake.tits">fake.tits</a>',
        '<a href="https://example.com/torrents.php?taglist=amateur">amateur</a>',
    ]
    assert grid.tags_layout.itemAtPosition(0, 0).widget() is labels[0]
    assert grid.tags_layout.itemAtPosition(0, 1).widget() is labels[1]
    assert grid.load_button.text() == "Fetch Tags"
    assert grid.load_button.isEnabled()
    assert window.statusBar().currentMessage() == "Fetched 2 tags"


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
    contents = (
        '[{"name": "sid", "value": "value", "domain": "example.com", "path": "/"}]'
    )
    window.cookies_text.setPlainText(contents)

    qtbot.mouseClick(window.save_cookies_button, Qt.MouseButton.LeftButton)

    saved_contents = (tmp_path / "cookies.json").read_text(encoding="utf-8")
    assert json.loads(saved_contents) == json.loads(contents)
    assert settings.value("cookies_file", type=str) == str(tmp_path / "cookies.json")


def test_save_cookies_writes_valid_empty_export(qtbot, tmp_path, monkeypatch) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(torrentpal.window, "SETTINGS", settings)
    monkeypatch.setattr(torrentpal.window, "DATA_DIR", tmp_path)
    window = MainWindow()
    qtbot.addWidget(window)

    qtbot.mouseClick(window.save_cookies_button, Qt.MouseButton.LeftButton)

    assert (tmp_path / "cookies.json").read_text(encoding="utf-8") == "[]"
    assert window.statusBar().currentMessage() == "Browser cookies saved"


def test_save_cookies_honors_configured_path_and_json_format(
    qtbot, tmp_path, monkeypatch
) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(torrentpal.window, "SETTINGS", settings)
    window = MainWindow()
    qtbot.addWidget(window)
    cookies_file = tmp_path / "exports" / "cookies.json"
    contents = (
        '[{"name":"session","value":"secret","domain":".example.com",'
        '"path":"/","secure":true}]'
    )
    window.cookies_path.setText(str(cookies_file))
    window.cookies_text.setPlainText(contents)

    qtbot.mouseClick(window.save_cookies_button, Qt.MouseButton.LeftButton)

    assert json.loads(cookies_file.read_text(encoding="utf-8")) == json.loads(contents)
    assert settings.value("cookies_file", type=str) == str(cookies_file)
    assert window.statusBar().currentMessage() == "Browser cookies saved"


def test_save_cookies_rejects_malformed_content_without_overwriting(
    qtbot, tmp_path, monkeypatch
) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(torrentpal.window, "SETTINGS", settings)
    window = MainWindow()
    qtbot.addWidget(window)
    cookies_file = tmp_path / "cookies.json"
    cookies_file.write_text("[]", encoding="utf-8")
    window.cookies_path.setText(str(cookies_file))
    window.cookies_text.setPlainText("# Netscape HTTP Cookie File\n")

    qtbot.mouseClick(window.save_cookies_button, Qt.MouseButton.LeftButton)

    assert cookies_file.read_text(encoding="utf-8") == "[]"
    assert not settings.contains("cookies_file")
    assert window.statusBar().currentMessage().startswith("Cookies not saved:")
