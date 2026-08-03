import html
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import (
    QDragEnterEvent,
    QDragLeaveEvent,
    QDropEvent,
    QImageReader,
    QMouseEvent,
    QMovie,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTableView,
    QTextBrowser,
    QToolButton,
    QTreeView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from torrentpal.domain import Tag


class TorrentList(QGroupBox):
    open_requested = Signal(Path)

    def __init__(self) -> None:
        super().__init__("Torrents")
        self.setObjectName("torrentsGroup")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)

        self.table = QTreeWidget()
        self.table.setObjectName("torrentsTable")
        self.table.setAccessibleName("Torrents")
        self.table.setAccessibleDescription("Select a torrent to open its metadata")
        self.table.setColumnCount(2)
        self.table.setHeaderLabels(("Torrent", "Cached Images"))
        self.table.setRootIsDecorated(False)
        self.table.setAlternatingRowColors(True)
        self.table.setUniformRowHeights(True)
        header = self.table.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.itemClicked.connect(self._open_item)
        layout.addWidget(self.table)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("torrentLoadingProgress")
        self.progress_bar.setAccessibleName("Torrent loading progress")
        layout.addWidget(self.progress_bar)

        self.load_status = QLabel()
        self.load_status.setObjectName("torrentLoadingStatus")
        self.load_status.setWordWrap(True)
        self.load_status.hide()
        layout.addWidget(self.load_status)

        self.empty_label = QLabel(
            "No torrents yet. Import files, a folder, or download from a URL."
        )
        self.empty_label.setObjectName("torrentsEmpty")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_label)
        self._is_loading = False
        self.begin_loading()

    @property
    def is_loading(self) -> bool:
        return self._is_loading

    def begin_loading(self) -> None:
        self._is_loading = True
        self.table.clear()
        self.table.show()
        self.empty_label.hide()
        self.load_status.hide()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat("Finding torrents…")
        self.progress_bar.show()

    def set_loading_total(self, total: int) -> None:
        self.progress_bar.setRange(0, max(total, 1))
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Loading torrents… %v / %m")

    def add_torrent(
        self, path: Path, display_name: str, cached_image_total: int
    ) -> None:
        item = QTreeWidgetItem([display_name, str(cached_image_total)])
        item.setData(0, Qt.ItemDataRole.UserRole, str(path))
        item.setToolTip(0, str(path))
        item.setToolTip(1, f"{cached_image_total} cached images")
        item.setTextAlignment(
            1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.table.addTopLevelItem(item)

    def set_loading_progress(self, processed: int, total: int) -> None:
        self.progress_bar.setRange(0, max(total, 1))
        self.progress_bar.setValue(processed)

    def finish_loading(self, unreadable_count: int, error_message: str) -> None:
        self._is_loading = False
        self.progress_bar.hide()
        self.table.resizeColumnToContents(1)
        has_torrents = self.table.topLevelItemCount() > 0
        self.table.setVisible(has_torrents)
        self.empty_label.setVisible(not has_torrents)
        if error_message:
            self.load_status.setText(f"Could not load torrents: {error_message}")
        elif unreadable_count:
            noun = "file" if unreadable_count == 1 else "files"
            self.load_status.setText(
                f"Skipped {unreadable_count} unreadable torrent {noun}."
            )
        else:
            self.load_status.clear()
        self.load_status.setVisible(bool(self.load_status.text()))

    def _open_item(self, item: QTreeWidgetItem, column: int) -> None:
        del column
        self.open_requested.emit(Path(item.data(0, Qt.ItemDataRole.UserRole)))


class TagGrid(QWidget):
    load_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("tagGrid")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.tags_widget = QWidget()
        self.tags_layout = QGridLayout(self.tags_widget)
        self.tags_layout.setContentsMargins(0, 0, 0, 0)
        self.tags_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.tags_widget)
        self.load_button = QPushButton("Fetch Tags")
        self.load_button.setObjectName("fetchTagsButton")
        self.load_button.clicked.connect(self.load_requested)
        layout.addWidget(self.load_button, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_fetching(self, fetching: bool) -> None:
        self.load_button.setText("Fetching.." if fetching else "Fetch Tags")
        self.load_button.setEnabled(not fetching)

    def set_tags(self, tags: tuple[Tag, ...]) -> None:
        while self.tags_layout.count():
            item = self.tags_layout.takeAt(0)
            item.widget().deleteLater()
        for index, tag in enumerate(tags):
            link = QLabel(
                f'<a href="{html.escape(tag.url, quote=True)}">'
                f"{html.escape(tag.name)}</a>"
            )
            link.setObjectName("torrentTag")
            link.setOpenExternalLinks(True)
            link.setToolTip(tag.url)
            self.tags_layout.addWidget(link, index // 4, index % 4)


class _GalleryImage(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ImageGallery(QWidget):
    load_requested = Signal()
    VIEW_MODES = ("Fit", "Fill Vertical", "Fill Width", "Actual")
    VIEW_SIZE = QSize(760, 520)

    def __init__(self, image_paths: tuple[Path, ...]) -> None:
        super().__init__()
        self.setObjectName("imageGallery")
        self._view_mode_index = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.pages = QStackedWidget()
        self.pages.setObjectName("imagePages")
        self.pages.setMinimumHeight(240)
        layout.addWidget(self.pages)

        controls = QHBoxLayout()
        controls.addStretch()
        self.previous_button = QPushButton("Prev")
        self.previous_button.setObjectName("previousImageButton")
        self.previous_button.setAccessibleDescription("Show the previous cached image")
        self.previous_button.clicked.connect(lambda: self._move(-1))
        self.page_label = QLabel()
        self.page_label.setObjectName("imagePageLabel")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.load_button = QPushButton("Fetch Image")
        self.load_button.setObjectName("fetchImageButton")
        self.load_button.setAccessibleDescription(
            "Fetch and cache images from the torrent comment link"
        )
        self.load_button.clicked.connect(self.load_requested)
        self.next_button = QPushButton("Next")
        self.next_button.setObjectName("nextImageButton")
        self.next_button.setAccessibleDescription("Show the next cached image")
        self.next_button.clicked.connect(lambda: self._move(1))
        self.view_mode_label = QLabel()
        self.view_mode_label.setObjectName("imageViewModeLabel")
        self.view_mode_label.setAccessibleName("Current image view mode")
        controls.addWidget(self.previous_button)
        controls.addWidget(self.page_label)
        controls.addWidget(self.load_button)
        controls.addWidget(self.next_button)
        controls.addWidget(self.view_mode_label)
        controls.addStretch()
        layout.addLayout(controls)
        self._update_view_mode_label()
        self.set_images(image_paths)

    @property
    def view_mode(self) -> str:
        return self.VIEW_MODES[self._view_mode_index]

    def set_fetching(self, fetching: bool) -> None:
        self.load_button.setText("Fetching.." if fetching else "Fetch Image")
        self.load_button.setEnabled(not fetching)

    def set_images(self, image_paths: tuple[Path, ...]) -> None:
        while self.pages.count():
            page = self.pages.widget(0)
            self.pages.removeWidget(page)
            page.deleteLater()
        for image_path in image_paths:
            image = _GalleryImage()
            image.setObjectName("mediaImage")
            image.setAccessibleName("Cached torrent image")
            image.setAccessibleDescription("Click to change the image view mode")
            image.setToolTip("Click to change the image view mode")
            image.setCursor(Qt.CursorShape.PointingHandCursor)
            image.setAlignment(Qt.AlignmentFlag.AlignCenter)
            image.setScaledContents(False)
            image.clicked.connect(self._cycle_view_mode)
            reader = QImageReader(str(image_path))
            if reader.supportsAnimation():
                movie = QMovie(str(image_path), parent=image)
                image.setMovie(movie)
                image.source_size = reader.size()
                image.source_pixmap = None
            else:
                image.source_pixmap = QPixmap(str(image_path))
                image.source_size = image.source_pixmap.size()
            self._apply_view_mode(image)
            self.pages.addWidget(image)
        multiple_images = self.pages.count() > 1
        self.previous_button.setEnabled(multiple_images)
        self.next_button.setEnabled(multiple_images)
        if self.pages.count():
            self._set_current_index(0)
        else:
            self.page_label.setText("0 / 0")

    def _cycle_view_mode(self) -> None:
        self._view_mode_index = (self._view_mode_index + 1) % len(self.VIEW_MODES)
        self._update_view_mode_label()
        current_image = self.pages.currentWidget()
        if current_image is not None:
            self._apply_view_mode(current_image)

    def _update_view_mode_label(self) -> None:
        self.view_mode_label.setText(f"View: {self.view_mode}")

    def _apply_view_mode(self, image: _GalleryImage) -> None:
        target_size = self._view_size(image.source_size)
        if image.movie() is not None:
            image.movie().setScaledSize(target_size)
        else:
            image.setPixmap(
                image.source_pixmap.scaled(
                    target_size,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        image.updateGeometry()
        self.pages.updateGeometry()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if not self.isVisible():
            return
        current_image = self.pages.currentWidget()
        if current_image is not None:
            self._apply_view_mode(current_image)

    def _view_size(self, source_size: QSize) -> QSize:
        if not source_size.isValid():
            return QSize()
        view_size = self.VIEW_SIZE
        if self.isVisible() and self.pages.width() > 0 and self.pages.height() > 0:
            view_size = self.pages.contentsRect().size()
        if self.view_mode == "Actual":
            return source_size
        if self.view_mode == "Fill Width":
            return QSize(
                view_size.width(),
                round(
                    source_size.height()
                    * view_size.width()
                    / source_size.width()
                ),
            )
        if self.view_mode == "Fill Vertical":
            return QSize(
                round(
                    source_size.width()
                    * view_size.height()
                    / source_size.height()
                ),
                view_size.height(),
            )
        return source_size.scaled(
            view_size,
            Qt.AspectRatioMode.KeepAspectRatio,
        )

    def _move(self, offset: int) -> None:
        self._set_current_index(
            (self.pages.currentIndex() + offset) % self.pages.count()
        )

    def _set_current_index(self, index: int) -> None:
        current_image = self.pages.currentWidget()
        if current_image is not None and current_image.movie() is not None:
            current_image.movie().stop()
        self.pages.setCurrentIndex(index)
        current_image = self.pages.currentWidget()
        self._apply_view_mode(current_image)
        if current_image.movie() is not None:
            current_image.movie().start()
        self.page_label.setText(f"{index + 1} / {self.pages.count()}")


class DropZone(QGroupBox):
    paths_selected = Signal(tuple)
    paste_requested = Signal()
    url_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__("Import torrents")
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        drop_text = QLabel("Drag .torrent files or a folder here")
        self.browse_button = QPushButton("Open Files…")
        self.browse_button.setObjectName("openTorrentFilesButton")
        self.browse_button.setAccessibleDescription(
            "Choose one or more local .torrent files to import"
        )
        self.folder_button = QPushButton("Open Folder…")
        self.folder_button.setObjectName("openTorrentFolderButton")
        self.folder_button.setAccessibleDescription(
            "Choose a folder containing .torrent files to import"
        )
        file_actions = QHBoxLayout()
        file_actions.addWidget(drop_text)
        file_actions.addStretch()
        file_actions.addWidget(self.browse_button)
        file_actions.addWidget(self.folder_button)
        self.url_input = QLineEdit()
        self.url_input.setObjectName("torrentUrlInput")
        self.url_input.setPlaceholderText("https://example.com/file.torrent?authkey=…")
        self.url_input.setAccessibleName("Torrent file URL")
        self.url_input.setClearButtonEnabled(True)
        self.paste_button = QPushButton("Paste from Clipboard")
        self.paste_button.setObjectName("pasteTorrentUrlButton")
        self.paste_button.setAccessibleDescription(
            "Paste a valid HTTP or HTTPS torrent URL from the clipboard"
        )
        self.paste_button.clicked.connect(self.paste_requested)
        self.download_button = QPushButton("Download and Open")
        self.download_button.setObjectName("downloadTorrentButton")
        self.download_button.setAccessibleDescription(
            "Download the torrent from this URL and open it"
        )
        self.download_button.setEnabled(False)
        self.url_input.textChanged.connect(self._update_download_button)
        self.url_input.returnPressed.connect(self._request_url)
        self.download_button.clicked.connect(self._request_url)
        url_actions = QHBoxLayout()
        url_actions.addWidget(self.url_input, stretch=1)
        url_actions.addWidget(self.paste_button)
        url_actions.addWidget(self.download_button)
        self.status_label = QLabel()
        self.status_label.setObjectName("torrentOperationStatus")
        self.status_label.setAccessibleName("Torrent operation status")
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        self.import_status = self.status_label
        self.url_status = self.status_label
        self._downloading = False
        layout.addLayout(file_actions)
        layout.addLayout(url_actions)
        layout.addWidget(self.status_label)

    def _request_url(self) -> None:
        if self.download_button.isEnabled():
            self.url_requested.emit(self.url_input.text())

    def _update_download_button(self) -> None:
        self.download_button.setEnabled(
            not self._downloading and bool(self.url_input.text().strip())
        )

    def set_downloading(self, downloading: bool) -> None:
        self._downloading = downloading
        self.url_input.setEnabled(not downloading)
        self.paste_button.setEnabled(not downloading)
        self.download_button.setText(
            "Downloading…" if downloading else "Download and Open"
        )
        self._update_download_button()

    def set_url_status(self, message: str) -> None:
        self._set_status(message)

    def set_import_status(self, message: str) -> None:
        self._set_status(message)

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_label.setVisible(bool(message))

    @staticmethod
    def _paths_from_mime_data(mime_data) -> tuple[Path, ...]:
        paths = tuple(
            Path(url.toLocalFile())
            for url in mime_data.urls()
            if url.isLocalFile() and url.toLocalFile()
        )
        return tuple(
            path
            for path in paths
            if path.is_dir() or path.suffix.lower() == ".torrent"
        )

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._paths_from_mime_data(event.mimeData()):
            self.setTitle("Drop torrents to import")
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self.setTitle("Import torrents")

    def dropEvent(self, event: QDropEvent) -> None:
        self.setTitle("Import torrents")
        paths = self._paths_from_mime_data(event.mimeData())
        if paths:
            self.paths_selected.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()


class CollapsiblePanel(QWidget):
    def __init__(self, title: str, view: QAbstractItemView) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.toggle = QToolButton()
        self.toggle.setText(title)
        self.toggle.setCheckable(True)
        self.toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setAccessibleDescription(f"Expand or collapse {title.lower()}")
        self.view = view
        self.view.hide()
        self.toggle.toggled.connect(self._set_expanded)
        layout.addWidget(self.toggle)
        layout.addWidget(self.view)

    def _set_expanded(self, expanded: bool) -> None:
        self.toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self.view.setVisible(expanded)


def metadata_table() -> QTableView:
    view = QTableView()
    view.horizontalHeader().hide()
    view.verticalHeader().hide()
    view.setShowGrid(False)
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    return view


def comment_browser(comment: str) -> QTextBrowser:
    browser = QTextBrowser()
    browser.setObjectName("commentBrowser")
    browser.setMarkdown(comment)
    browser.setOpenExternalLinks(True)
    browser.setAccessibleName("Torrent comment")
    browser.setMinimumHeight(96)
    return browser


def tracker_table() -> QTableView:
    view = QTableView()
    view.verticalHeader().hide()
    view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    return view


def file_tree() -> QTreeView:
    view = QTreeView()
    view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    view.setAlternatingRowColors(True)
    return view
