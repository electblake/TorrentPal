import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from torrentpal.config import (
    DATA_DIR,
    DEFAULT_TRACKER_PAGE_TIMEOUT_SECONDS,
    SETTINGS,
)
from torrentpal.domain import TorrentMetadata
from torrentpal.downloads import (
    TorrentDownloadError,
    download_torrent,
    validate_torrent_url,
)
from torrentpal.media import (
    CookieConfigurationError,
    cached_images,
    download_images,
    download_tags,
    first_url,
    format_browser_cookie_json,
)
from torrentpal.models import FileTreeModel, MetadataTableModel, TrackerModel
from torrentpal.parser import parse_torrent
from torrentpal.widgets import (
    CollapsiblePanel,
    DropZone,
    ImageGallery,
    TagGrid,
    TorrentList,
    comment_browser,
    file_tree,
    metadata_table,
    tracker_table,
)


class _ResultsSplitter(QSplitter):
    def __init__(self) -> None:
        super().__init__(Qt.Orientation.Horizontal)
        self._initial_sizes_applied = False

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._initial_sizes_applied:
            return
        available_width = sum(self.sizes())
        if available_width <= 0:
            available_width = self.width() - self.handleWidth()
        image_width = round(available_width * 0.6)
        self.setSizes([image_width, available_width - image_width])
        self._initial_sizes_applied = True


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Torrent Metadata")
        self.resize(860, 700)
        self.setMinimumSize(600, 480)
        self.statusBar().setObjectName("statusBar")
        self.statusBar().showMessage("Ready")
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.input_page = self._build_input_page()
        self.stack.addWidget(self.input_page)
        self.settings_page = self._build_settings_page()
        self.stack.addWidget(self.settings_page)

    def _page(self) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(0)
        return page, layout

    def _header(self, layout: QVBoxLayout) -> None:
        title = QLabel("Torrent Metadata")
        title_font = QFont(title.font())
        title_font.setPointSize(title_font.pointSize() + 8)
        title_font.setWeight(QFont.Weight.DemiBold)
        title.setFont(title_font)
        subtitle = QLabel("Extract metadata from a .torrent file.")
        layout.addWidget(title)
        layout.addSpacing(4)
        layout.addWidget(subtitle)

    def _build_input_page(self) -> QWidget:
        page, layout = self._page()
        self._header(layout)
        layout.addSpacing(24)
        self.drop_zone = DropZone()
        self.drop_zone.browse_button.clicked.connect(self._browse_torrents)
        self.drop_zone.folder_button.clicked.connect(self._browse_torrent_folder)
        self.drop_zone.paths_selected.connect(self._import_torrent_paths)
        self.drop_zone.paste_requested.connect(self._paste_torrent_url)
        self.drop_zone.url_requested.connect(self._download_and_open_torrent)
        layout.addWidget(self.drop_zone)
        layout.addSpacing(16)
        self.torrents = TorrentList()
        self.torrents.open_requested.connect(self.open_torrent)
        layout.addWidget(self.torrents, stretch=1)
        self._refresh_torrents()
        layout.addSpacing(16)
        settings_button = QPushButton("Settings")
        settings_button.clicked.connect(self._open_settings)
        layout.addWidget(settings_button, alignment=Qt.AlignmentFlag.AlignRight)
        return page

    def _build_settings_page(self) -> QWidget:
        page, layout = self._page()
        back = QPushButton("Back")
        back.setObjectName("settingsBackButton")
        back.clicked.connect(self._show_input_page)
        layout.addWidget(back, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addSpacing(16)
        title = QLabel("Settings")
        title_font = QFont(title.font())
        title_font.setPointSize(title_font.pointSize() + 4)
        title_font.setWeight(QFont.Weight.DemiBold)
        title.setFont(title_font)
        layout.addWidget(title)
        layout.addSpacing(16)

        images_browser_group = QGroupBox("Images & Browser")
        images_browser_group.setObjectName("imagesBrowserGroup")
        form = QFormLayout(images_browser_group)
        self.cookies_path = QLineEdit()
        self.cookies_path.setObjectName("cookiesFilePath")
        self.cookies_path.setPlaceholderText("Path to browser cookies JSON export")
        form.addRow("Cookies JSON file", self.cookies_path)
        self.cookies_text = QTextEdit()
        self.cookies_text.setObjectName("cookiesText")
        self.cookies_text.setPlaceholderText("Paste exported browser cookies JSON")
        form.addRow("Cookies", self.cookies_text)
        self.tracker_page_timeout = QSpinBox()
        self.tracker_page_timeout.setObjectName("trackerPageTimeout")
        self.tracker_page_timeout.setRange(5, 600)
        self.tracker_page_timeout.setSuffix(" seconds")
        self.tracker_page_timeout.setAccessibleDescription(
            "Maximum wait for tracker pages and delayed image or tag content"
        )
        self.tracker_page_timeout.setToolTip(
            "Maximum wait for tracker pages and delayed image or tag content"
        )
        form.addRow("Tracker Page Timeout", self.tracker_page_timeout)
        self.image_minimum_width = QSlider(Qt.Orientation.Horizontal)
        self.image_minimum_width.setObjectName("imageMinimumWidth")
        self.image_minimum_width.setRange(10, 1920)
        self.image_minimum_width.setAccessibleDescription(
            "Minimum decoded native image width; rendered CSS size is ignored"
        )
        self.image_minimum_width.setToolTip(
            "Uses the decoded native image width, not its rendered CSS width"
        )
        minimum_width_row = QWidget()
        minimum_width_layout = QHBoxLayout(minimum_width_row)
        minimum_width_layout.setContentsMargins(0, 0, 0, 0)
        self.image_minimum_width_value = QLabel("10 px")
        self.image_minimum_width.valueChanged.connect(
            lambda value: self.image_minimum_width_value.setText(f"{value} px")
        )
        minimum_width_layout.addWidget(self.image_minimum_width)
        minimum_width_layout.addWidget(self.image_minimum_width_value)
        form.addRow("Native Image Minimum Width", minimum_width_row)
        self.image_minimum_height = QSlider(Qt.Orientation.Horizontal)
        self.image_minimum_height.setObjectName("imageMinimumHeight")
        self.image_minimum_height.setRange(10, 1920)
        self.image_minimum_height.setAccessibleDescription(
            "Minimum decoded native image height; rendered CSS size is ignored"
        )
        self.image_minimum_height.setToolTip(
            "Uses the decoded native image height, not its rendered CSS height"
        )
        minimum_height_row = QWidget()
        minimum_height_layout = QHBoxLayout(minimum_height_row)
        minimum_height_layout.setContentsMargins(0, 0, 0, 0)
        self.image_minimum_height_value = QLabel("10 px")
        self.image_minimum_height.valueChanged.connect(
            lambda value: self.image_minimum_height_value.setText(f"{value} px")
        )
        minimum_height_layout.addWidget(self.image_minimum_height)
        minimum_height_layout.addWidget(self.image_minimum_height_value)
        form.addRow("Native Image Minimum Height", minimum_height_row)
        self.torrent_images_maximum = QSpinBox()
        self.torrent_images_maximum.setObjectName("torrentImagesMaximum")
        self.torrent_images_maximum.setRange(1, 100)
        form.addRow("Torrent Images Max", self.torrent_images_maximum)
        self.click_all_hidden_contents = QCheckBox()
        self.click_all_hidden_contents.setObjectName("clickAllHiddenContents")
        form.addRow("Click all hidden contents", self.click_all_hidden_contents)
        self.save_cookies_button = QPushButton("Save Cookies")
        self.save_cookies_button.clicked.connect(self._save_cookies)
        form.addRow("", self.save_cookies_button)
        layout.addWidget(images_browser_group)
        layout.addSpacing(16)

        tags_group = QGroupBox("Tags")
        tags_group.setObjectName("tagsSettingsGroup")
        tags_form = QFormLayout(tags_group)
        self.tag_selectors = QTextEdit()
        self.tag_selectors.setObjectName("tagSelectors")
        self.tag_selectors.setPlaceholderText("One CSS selector per line")
        tags_form.addRow("Selectors", self.tag_selectors)
        self.tag_minimum_link_text_length = QSpinBox()
        self.tag_minimum_link_text_length.setObjectName("tagMinimumLinkTextLength")
        self.tag_minimum_link_text_length.setRange(1, 100)
        tags_form.addRow("Min Tag Link Text Length", self.tag_minimum_link_text_length)
        self.tag_name_excludes = QTextEdit()
        self.tag_name_excludes.setObjectName("tagNameExcludes")
        self.tag_name_excludes.setPlaceholderText("One regular expression per line")
        tags_form.addRow("Tag Name Excludes", self.tag_name_excludes)
        layout.addWidget(tags_group)
        layout.addSpacing(16)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Reset
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.save_settings_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        self.reset_settings_button = buttons.button(
            QDialogButtonBox.StandardButton.Reset
        )
        self.cancel_settings_button = buttons.button(
            QDialogButtonBox.StandardButton.Cancel
        )
        self.save_settings_button.clicked.connect(self._save_settings)
        self.reset_settings_button.clicked.connect(self._reset_settings)
        self.cancel_settings_button.clicked.connect(self._show_input_page)
        layout.addWidget(buttons)
        layout.addStretch()
        return page

    def _open_settings(self) -> None:
        cookies_file = SETTINGS.value(
            "cookies_file", str(DATA_DIR / "cookies.json"), type=str
        )
        self.cookies_path.setText(cookies_file)
        self.image_minimum_width.setValue(
            SETTINGS.value("image_minimum_width", 10, type=int)
        )
        self.image_minimum_height.setValue(
            SETTINGS.value("image_minimum_height", 10, type=int)
        )
        self.torrent_images_maximum.setValue(
            SETTINGS.value("torrent_images_maximum", 10, type=int)
        )
        self.tracker_page_timeout.setValue(
            SETTINGS.value(
                "tracker_page_timeout_seconds",
                DEFAULT_TRACKER_PAGE_TIMEOUT_SECONDS,
                type=int,
            )
        )
        self.click_all_hidden_contents.setChecked(
            SETTINGS.value("click_all_hidden_contents", True, type=bool)
        )
        self.tag_selectors.setPlainText(
            SETTINGS.value("tag_selectors", "#torrent_tags_list", type=str)
        )
        self.tag_minimum_link_text_length.setValue(
            SETTINGS.value("tag_minimum_link_text_length", 3, type=int)
        )
        self.tag_name_excludes.setPlainText(
            SETTINGS.value("tag_name_excludes", "\\[-\\]\n\\[N\\]", type=str)
        )
        cookies_path = Path(cookies_file)
        if cookies_path.exists():
            self.cookies_text.setPlainText(cookies_path.read_text(encoding="utf-8"))
        self.stack.setCurrentWidget(self.settings_page)

    def _save_cookies(self) -> None:
        configured_path = self.cookies_path.text().strip()
        cookies_file = (
            Path(configured_path) if configured_path else DATA_DIR / "cookies.json"
        )
        contents = self.cookies_text.toPlainText()
        contents_to_save = contents if contents.strip() else "[]"
        try:
            formatted_json = format_browser_cookie_json(contents_to_save)
        except CookieConfigurationError as error:
            self._show_fetch_status(f"Cookies not saved: {error}")
            return
        cookies_file.parent.mkdir(parents=True, exist_ok=True)
        cookies_file.write_text(formatted_json, encoding="utf-8")
        self.cookies_text.setPlainText(formatted_json)
        self.cookies_path.setText(str(cookies_file))
        SETTINGS.setValue("cookies_file", str(cookies_file))
        SETTINGS.sync()
        self._show_fetch_status("Browser cookies saved")

    def _save_settings(self) -> None:
        SETTINGS.setValue("cookies_file", self.cookies_path.text())
        SETTINGS.setValue("image_minimum_width", self.image_minimum_width.value())
        SETTINGS.setValue("image_minimum_height", self.image_minimum_height.value())
        SETTINGS.setValue("torrent_images_maximum", self.torrent_images_maximum.value())
        SETTINGS.setValue(
            "tracker_page_timeout_seconds", self.tracker_page_timeout.value()
        )
        SETTINGS.setValue(
            "click_all_hidden_contents", self.click_all_hidden_contents.isChecked()
        )
        SETTINGS.setValue("tag_selectors", self.tag_selectors.toPlainText())
        SETTINGS.setValue(
            "tag_minimum_link_text_length",
            self.tag_minimum_link_text_length.value(),
        )
        SETTINGS.setValue("tag_name_excludes", self.tag_name_excludes.toPlainText())
        SETTINGS.sync()
        self._show_input_page()

    def _reset_settings(self) -> None:
        SETTINGS.remove("cookies_file")
        SETTINGS.remove("image_minimum_width")
        SETTINGS.remove("image_minimum_height")
        SETTINGS.remove("torrent_images_maximum")
        SETTINGS.remove("tracker_page_timeout_seconds")
        SETTINGS.remove("click_all_hidden_contents")
        SETTINGS.remove("tag_selectors")
        SETTINGS.remove("tag_minimum_link_text_length")
        SETTINGS.remove("tag_name_excludes")
        SETTINGS.sync()
        self.cookies_path.clear()
        self.cookies_text.clear()
        self.image_minimum_width.setValue(10)
        self.image_minimum_height.setValue(10)
        self.torrent_images_maximum.setValue(10)
        self.tracker_page_timeout.setValue(DEFAULT_TRACKER_PAGE_TIMEOUT_SECONDS)
        self.click_all_hidden_contents.setChecked(True)
        self.tag_selectors.setPlainText("#torrent_tags_list")
        self.tag_minimum_link_text_length.setValue(3)
        self.tag_name_excludes.setPlainText("\\[-\\]\n\\[N\\]")

    def _browse_torrents(self) -> None:
        filenames, _ = QFileDialog.getOpenFileNames(
            self, "Import torrents", "", "Torrent files (*.torrent)"
        )
        if filenames:
            self._import_torrent_paths(tuple(Path(filename) for filename in filenames))

    def _browse_torrent_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Import torrents from folder"
        )
        if directory:
            self._import_torrent_paths((Path(directory),))

    def open_torrent(self, path: Path) -> None:
        metadata = parse_torrent(path)
        self._show_metadata(metadata)

    def _show_metadata(self, metadata: TorrentMetadata) -> None:
        results = self._build_results_page(metadata)
        self.stack.addWidget(results)
        self.stack.setCurrentWidget(results)

    def _torrent_directory(self) -> Path:
        return DATA_DIR / "torrents"

    def _refresh_torrents(self) -> None:
        torrent_directory = self._torrent_directory()
        entries: list[tuple[Path, str]] = []
        torrent_hashes: set[str] = set()
        if torrent_directory.exists():
            paths = sorted(
                torrent_directory.glob("*.torrent"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            for path in paths:
                try:
                    metadata = parse_torrent(path)
                except Exception:
                    continue
                torrent_hash = metadata.info_hash_v1 or metadata.info_hash_v2
                if torrent_hash in torrent_hashes:
                    continue
                torrent_hashes.add(torrent_hash)
                entries.append((path, metadata.name))
        self.torrents.set_torrents(tuple(entries))

    def _show_input_page(self) -> None:
        self._refresh_torrents()
        self.stack.setCurrentWidget(self.input_page)

    def _import_torrent_paths(self, selected_paths: tuple[Path, ...]) -> None:
        torrent_paths: list[Path] = []
        failures: list[str] = []
        for selected_path in selected_paths:
            try:
                if selected_path.is_dir():
                    torrent_paths.extend(
                        sorted(
                            (
                                path
                                for path in selected_path.iterdir()
                                if path.is_file()
                                and path.suffix.lower() == ".torrent"
                            ),
                            key=lambda path: path.name.lower(),
                        )
                    )
                elif selected_path.suffix.lower() == ".torrent":
                    torrent_paths.append(selected_path)
                else:
                    failures.append(f"{selected_path.name}: not a .torrent file")
            except OSError as error:
                failures.append(f"{selected_path.name}: {error}")

        unique_paths: list[Path] = []
        resolved_paths: set[Path] = set()
        for torrent_path in torrent_paths:
            try:
                resolved_path = torrent_path.resolve()
            except OSError as error:
                failures.append(f"{torrent_path.name}: {error}")
                continue
            if resolved_path not in resolved_paths:
                resolved_paths.add(resolved_path)
                unique_paths.append(torrent_path)

        if not unique_paths and not failures:
            self._show_import_status("No .torrent files found to import")
            return

        imported_count = 0
        existing_count = 0
        if unique_paths:
            noun = "torrent" if len(unique_paths) == 1 else "torrents"
            self._show_import_status(f"Importing {len(unique_paths)} {noun}…")
        try:
            self._torrent_directory().mkdir(parents=True, exist_ok=True)
        except OSError as error:
            self._show_import_status(f"Could not prepare torrent storage: {error}")
            return

        for torrent_path in unique_paths:
            try:
                metadata = parse_torrent(torrent_path)
                torrent_hash = metadata.info_hash_v1 or metadata.info_hash_v2
                stored_path = self._torrent_directory() / f"{torrent_hash}.torrent"
                if stored_path.exists():
                    existing_count += 1
                    continue
                temporary_path = stored_path.with_name(f".{stored_path.name}.importing")
                try:
                    shutil.copyfile(torrent_path, temporary_path)
                    temporary_path.replace(stored_path)
                finally:
                    temporary_path.unlink(missing_ok=True)
                imported_count += 1
            except Exception as error:
                failures.append(f"{torrent_path.name}: {error}")

        self._refresh_torrents()
        status_parts = []
        if imported_count:
            noun = "torrent" if imported_count == 1 else "torrents"
            status_parts.append(f"Imported {imported_count} {noun}")
        if existing_count:
            noun = "torrent" if existing_count == 1 else "torrents"
            status_parts.append(f"{existing_count} {noun} already in Torrents")
        if failures:
            failure_details = failures[0]
            if len(failures) > 1:
                failure_details += f" (+{len(failures) - 1} more)"
            status_parts.append(f"{len(failures)} failed: {failure_details}")
        self._show_import_status("; ".join(status_parts))

    def _show_import_status(self, message: str) -> None:
        self.drop_zone.set_import_status(message)
        self.statusBar().showMessage(message)
        QApplication.processEvents()

    def _store_downloaded_torrent(
        self, downloaded_path: Path, metadata: TorrentMetadata
    ) -> Path:
        torrent_hash = metadata.info_hash_v1 or metadata.info_hash_v2
        stored_path = self._torrent_directory() / f"{torrent_hash}.torrent"
        if stored_path.exists():
            downloaded_path.unlink(missing_ok=True)
        else:
            downloaded_path.replace(stored_path)
        return stored_path

    def _paste_torrent_url(self) -> None:
        try:
            url = validate_torrent_url(QApplication.clipboard().text())
        except TorrentDownloadError:
            self._show_torrent_url_status(
                "Clipboard does not contain a valid HTTP or HTTPS URL"
            )
            return
        self.drop_zone.url_input.setText(url)
        self.drop_zone.url_input.setFocus()
        self._show_torrent_url_status("Torrent URL pasted from clipboard")

    def _download_and_open_torrent(self, url: str) -> None:
        self.drop_zone.set_downloading(True)
        self._show_torrent_url_status("Downloading torrent…")
        downloaded_path: Path | None = None
        try:
            torrent_directory = self._torrent_directory()
            torrent_directory.mkdir(parents=True, exist_ok=True)
            downloaded_path = download_torrent(url, torrent_directory)
            self._show_torrent_url_status("Download complete; loading torrent…")
            metadata = parse_torrent(downloaded_path)
            self._store_downloaded_torrent(downloaded_path, metadata)
            self._refresh_torrents()
            self._show_metadata(metadata)
        except Exception as error:
            if downloaded_path is not None:
                downloaded_path.unlink(missing_ok=True)
            self._show_torrent_url_status(
                f"Could not download and load torrent: {error}"
            )
        else:
            self.drop_zone.url_input.clear()
            self._show_torrent_url_status("Torrent downloaded and loaded")
        finally:
            self.drop_zone.set_downloading(False)

    def _show_torrent_url_status(self, message: str) -> None:
        self.drop_zone.set_url_status(message)
        self.statusBar().showMessage(message)
        QApplication.processEvents()

    def _build_results_page(self, metadata: TorrentMetadata) -> QWidget:
        page, outer = self._page()
        back = QPushButton("Back")
        back.setObjectName("resultsBackButton")
        back.clicked.connect(self._show_input_page)
        outer.addWidget(back, alignment=Qt.AlignmentFlag.AlignLeft)
        outer.addSpacing(16)
        heading = QLabel(metadata.name)
        heading.setObjectName("torrentTitle")
        heading_font = QFont(heading.font())
        heading_font.setPointSize(heading_font.pointSize() + 4)
        heading_font.setWeight(QFont.Weight.DemiBold)
        heading.setFont(heading_font)
        heading.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        outer.addWidget(heading)
        outer.addSpacing(16)

        splitter = _ResultsSplitter()
        splitter.setObjectName("resultsSplitter")
        splitter.setChildrenCollapsible(False)
        torrent_hash = metadata.info_hash_v1 or metadata.info_hash_v2
        image_paths = cached_images(
            DATA_DIR,
            torrent_hash,
            SETTINGS.value("image_minimum_width", 10, type=int),
            SETTINGS.value("image_minimum_height", 10, type=int),
            SETTINGS.value("torrent_images_maximum", 10, type=int),
        )
        image_gallery = ImageGallery(image_paths)
        image_gallery.load_requested.connect(
            lambda: self._load_images(metadata, image_gallery)
        )
        image_gallery.setMinimumWidth(240)
        image_gallery.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding
        )
        splitter.addWidget(image_gallery)

        details_scroll = QScrollArea()
        details_scroll.setObjectName("resultsDetailsScroll")
        details_scroll.setMinimumWidth(240)
        details_scroll.setWidgetResizable(True)
        details_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        details_content = QWidget()
        details_content.setObjectName("resultsDetails")
        layout = QVBoxLayout(details_content)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(16)
        tags_group = QGroupBox("Tags")
        tags_layout = QVBoxLayout(tags_group)
        tag_grid = TagGrid()
        tag_grid.load_requested.connect(lambda: self._load_tags(metadata, tag_grid))
        tags_layout.addWidget(tag_grid)
        layout.addWidget(tags_group)
        details_group = QGroupBox("Metadata")
        details_layout = QVBoxLayout(details_group)
        table = metadata_table()
        table.setModel(MetadataTableModel(metadata))
        table.horizontalHeader().setStretchLastSection(True)
        table.setColumnWidth(0, 170)
        table.setFixedHeight(
            table.verticalHeader().defaultSectionSize() * table.model().rowCount() + 2
        )
        details_layout.addWidget(table)
        layout.addWidget(details_group)
        comment_group = QGroupBox("Comment")
        comment_layout = QVBoxLayout(comment_group)
        comment_layout.addWidget(comment_browser(metadata.comment))
        layout.addWidget(comment_group)
        magnet_row = QHBoxLayout()
        magnet_label = QLabel("Magnet Link")
        copy_button = QPushButton("Copy")
        copy_button.setAccessibleDescription("Copy magnet URI to the clipboard")
        copy_button.clicked.connect(
            lambda: QApplication.clipboard().setText(metadata.magnet_uri)
        )
        magnet_row.addWidget(magnet_label)
        magnet_row.addStretch()
        magnet_row.addWidget(copy_button)
        layout.addLayout(magnet_row)
        trackers = tracker_table()
        trackers.setModel(TrackerModel(metadata.trackers))
        trackers.horizontalHeader().setStretchLastSection(True)
        trackers.setMinimumHeight(180)
        layout.addWidget(
            CollapsiblePanel(f"Tracker List ({len(metadata.trackers)})", trackers)
        )
        files = file_tree()
        files.setModel(FileTreeModel(metadata))
        files.header().setStretchLastSection(False)
        files.header().setSectionResizeMode(0, files.header().ResizeMode.Stretch)
        files.header().setSectionResizeMode(
            1, files.header().ResizeMode.ResizeToContents
        )
        files.setMinimumHeight(260)
        layout.addWidget(
            CollapsiblePanel(
                f"Files ({len(metadata.files)}) [{metadata.total_size:,} bytes]", files
            )
        )
        layout.addStretch()
        details_scroll.setWidget(details_content)
        splitter.addWidget(details_scroll)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        outer.addWidget(splitter, stretch=1)
        return page

    def _load_images(
        self,
        metadata: TorrentMetadata,
        image_gallery: ImageGallery,
    ) -> None:
        image_gallery.set_fetching(True)
        self._show_fetch_status("Preparing image fetch")
        cookies_file = Path(
            SETTINGS.value("cookies_file", str(DATA_DIR / "cookies.json"), type=str)
        )
        torrent_hash = metadata.info_hash_v1 or metadata.info_hash_v2
        try:
            image_paths = download_images(
                first_url(metadata.comment),
                cookies_file,
                DATA_DIR,
                torrent_hash,
                SETTINGS.value("image_minimum_width", 10, type=int),
                SETTINGS.value("image_minimum_height", 10, type=int),
                SETTINGS.value("torrent_images_maximum", 10, type=int),
                SETTINGS.value("click_all_hidden_contents", True, type=bool),
                SETTINGS.value(
                    "tracker_page_timeout_seconds",
                    DEFAULT_TRACKER_PAGE_TIMEOUT_SECONDS,
                    type=int,
                ),
                self._show_fetch_status,
            )
            if not image_paths:
                raise RuntimeError("No qualifying images were returned")
            image_gallery.set_images(image_paths)
            self._show_fetch_status(f"Fetched and cached {len(image_paths)} images")
        except Exception as error:
            self._show_fetch_status(f"Image fetch failed: {error}")
        finally:
            image_gallery.set_fetching(False)

    def _show_fetch_status(self, message: str) -> None:
        self.statusBar().showMessage(message)
        QApplication.processEvents()

    def _load_tags(self, metadata: TorrentMetadata, tag_grid: TagGrid) -> None:
        tag_grid.set_fetching(True)
        self._show_fetch_status("Preparing tag fetch")
        try:
            tags = download_tags(
                first_url(metadata.comment),
                Path(
                    SETTINGS.value(
                        "cookies_file", str(DATA_DIR / "cookies.json"), type=str
                    )
                ),
                tuple(
                    SETTINGS.value(
                        "tag_selectors", "#torrent_tags_list", type=str
                    ).splitlines()
                ),
                SETTINGS.value("tag_minimum_link_text_length", 3, type=int),
                tuple(
                    SETTINGS.value(
                        "tag_name_excludes", "\\[-\\]\n\\[N\\]", type=str
                    ).splitlines()
                ),
                SETTINGS.value(
                    "tracker_page_timeout_seconds",
                    DEFAULT_TRACKER_PAGE_TIMEOUT_SECONDS,
                    type=int,
                ),
                self._show_fetch_status,
            )
            tag_grid.set_tags(tags)
            self._show_fetch_status(f"Fetched {len(tags)} tags")
        except Exception as error:
            self._show_fetch_status(f"Tag fetch failed: {error}")
        finally:
            tag_grid.set_fetching(False)
