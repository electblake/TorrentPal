from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
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
    QSlider,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from torrentpal.config import DATA_DIR, SETTINGS
from torrentpal.domain import TorrentMetadata
from torrentpal.media import cached_images, download_images, download_tags, first_url
from torrentpal.models import FileTreeModel, MetadataTableModel, TrackerModel
from torrentpal.parser import parse_torrent
from torrentpal.widgets import (
    CollapsiblePanel,
    DropZone,
    ImageGallery,
    TagGrid,
    comment_browser,
    file_tree,
    metadata_table,
    tracker_table,
)


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
        self.drop_zone.browse_button.clicked.connect(self._browse)
        self.drop_zone.file_selected.connect(self.open_torrent)
        layout.addWidget(self.drop_zone)
        layout.addStretch()
        settings_button = QPushButton("Settings")
        settings_button.clicked.connect(self._open_settings)
        layout.addWidget(settings_button, alignment=Qt.AlignmentFlag.AlignRight)
        return page

    def _build_settings_page(self) -> QWidget:
        page, layout = self._page()
        back = QPushButton("Back")
        back.setObjectName("settingsBackButton")
        back.clicked.connect(lambda: self.stack.setCurrentWidget(self.input_page))
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
        self.cookies_path.setPlaceholderText("Path to browser cookies export")
        form.addRow("Cookies file", self.cookies_path)
        self.cookies_text = QTextEdit()
        self.cookies_text.setObjectName("cookiesText")
        self.cookies_text.setPlaceholderText("Paste exported browser cookies JSON")
        form.addRow("Cookies", self.cookies_text)
        self.image_minimum_width = QSlider(Qt.Orientation.Horizontal)
        self.image_minimum_width.setObjectName("imageMinimumWidth")
        self.image_minimum_width.setRange(10, 1920)
        minimum_width_row = QWidget()
        minimum_width_layout = QHBoxLayout(minimum_width_row)
        minimum_width_layout.setContentsMargins(0, 0, 0, 0)
        self.image_minimum_width_value = QLabel("10 px")
        self.image_minimum_width.valueChanged.connect(
            lambda value: self.image_minimum_width_value.setText(f"{value} px")
        )
        minimum_width_layout.addWidget(self.image_minimum_width)
        minimum_width_layout.addWidget(self.image_minimum_width_value)
        form.addRow("Image Minimum Width", minimum_width_row)
        self.image_minimum_height = QSlider(Qt.Orientation.Horizontal)
        self.image_minimum_height.setObjectName("imageMinimumHeight")
        self.image_minimum_height.setRange(10, 1920)
        minimum_height_row = QWidget()
        minimum_height_layout = QHBoxLayout(minimum_height_row)
        minimum_height_layout.setContentsMargins(0, 0, 0, 0)
        self.image_minimum_height_value = QLabel("10 px")
        self.image_minimum_height.valueChanged.connect(
            lambda value: self.image_minimum_height_value.setText(f"{value} px")
        )
        minimum_height_layout.addWidget(self.image_minimum_height)
        minimum_height_layout.addWidget(self.image_minimum_height_value)
        form.addRow("Image Minimum Height", minimum_height_row)
        self.torrent_images_maximum = QSpinBox()
        self.torrent_images_maximum.setObjectName("torrentImagesMaximum")
        self.torrent_images_maximum.setRange(1, 100)
        form.addRow("Torrent Images Max", self.torrent_images_maximum)
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
        self.cancel_settings_button.clicked.connect(
            lambda: self.stack.setCurrentWidget(self.input_page)
        )
        layout.addWidget(buttons)
        layout.addStretch()
        return page

    def _open_settings(self) -> None:
        cookies_file = SETTINGS.value(
            "cookies_file", str(DATA_DIR / "cookies.txt"), type=str
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
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        cookies_file = DATA_DIR / "cookies.txt"
        cookies_file.write_text(self.cookies_text.toPlainText(), encoding="utf-8")
        self.cookies_path.setText(str(cookies_file))
        SETTINGS.setValue("cookies_file", str(cookies_file))
        SETTINGS.sync()

    def _save_settings(self) -> None:
        SETTINGS.setValue("cookies_file", self.cookies_path.text())
        SETTINGS.setValue("image_minimum_width", self.image_minimum_width.value())
        SETTINGS.setValue("image_minimum_height", self.image_minimum_height.value())
        SETTINGS.setValue("torrent_images_maximum", self.torrent_images_maximum.value())
        SETTINGS.setValue("tag_selectors", self.tag_selectors.toPlainText())
        SETTINGS.setValue(
            "tag_minimum_link_text_length",
            self.tag_minimum_link_text_length.value(),
        )
        SETTINGS.setValue("tag_name_excludes", self.tag_name_excludes.toPlainText())
        SETTINGS.sync()
        self.stack.setCurrentWidget(self.input_page)

    def _reset_settings(self) -> None:
        SETTINGS.remove("cookies_file")
        SETTINGS.remove("image_minimum_width")
        SETTINGS.remove("image_minimum_height")
        SETTINGS.remove("torrent_images_maximum")
        SETTINGS.remove("tag_selectors")
        SETTINGS.remove("tag_minimum_link_text_length")
        SETTINGS.remove("tag_name_excludes")
        SETTINGS.sync()
        self.cookies_path.clear()
        self.cookies_text.clear()
        self.image_minimum_width.setValue(10)
        self.image_minimum_height.setValue(10)
        self.torrent_images_maximum.setValue(10)
        self.tag_selectors.setPlainText("#torrent_tags_list")
        self.tag_minimum_link_text_length.setValue(3)
        self.tag_name_excludes.setPlainText("\\[-\\]\n\\[N\\]")

    def _browse(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open torrent", "", "Torrent files (*.torrent)"
        )
        self.open_torrent(Path(filename))

    def open_torrent(self, path: Path) -> None:
        metadata = parse_torrent(path)
        results = self._build_results_page(metadata)
        self.stack.addWidget(results)
        self.stack.setCurrentWidget(results)

    def _build_results_page(self, metadata: TorrentMetadata) -> QWidget:
        page, outer = self._page()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(16)
        back = QPushButton("Back")
        back.clicked.connect(lambda: self.stack.setCurrentWidget(self.input_page))
        layout.addWidget(back, alignment=Qt.AlignmentFlag.AlignLeft)
        heading = QLabel(metadata.name)
        heading_font = QFont(heading.font())
        heading_font.setPointSize(heading_font.pointSize() + 4)
        heading_font.setWeight(QFont.Weight.DemiBold)
        heading.setFont(heading_font)
        heading.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(heading)
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
        layout.addWidget(image_gallery)
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
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return page

    def _load_images(
        self,
        metadata: TorrentMetadata,
        image_gallery: ImageGallery,
    ) -> None:
        image_gallery.set_fetching(True)
        self._show_fetch_status("Preparing image fetch")
        cookies_file = Path(
            SETTINGS.value("cookies_file", str(DATA_DIR / "cookies.txt"), type=str)
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
                self._show_fetch_status,
            )
            image_gallery.set_images(image_paths)
            self._show_fetch_status(f"Fetched and cached {len(image_paths)} images")
        except Exception as error:
            self._show_fetch_status(f"Image fetch failed: {error}")
            raise
        finally:
            image_gallery.set_fetching(False)

    def _show_fetch_status(self, message: str) -> None:
        self.statusBar().showMessage(message)
        QApplication.processEvents()

    def _load_tags(self, metadata: TorrentMetadata, tag_grid: TagGrid) -> None:
        tag_grid.set_fetching(True)
        self._show_fetch_status("Preparing tag fetch")
        tags = download_tags(
            first_url(metadata.comment),
            Path(
                SETTINGS.value("cookies_file", str(DATA_DIR / "cookies.txt"), type=str)
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
            self._show_fetch_status,
        )
        tag_grid.set_tags(tags)
        self._show_fetch_status(f"Fetched {len(tags)} tags")
        tag_grid.set_fetching(False)
