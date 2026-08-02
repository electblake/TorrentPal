from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QDragEnterEvent,
    QDragLeaveEvent,
    QDropEvent,
    QImageReader,
    QMovie,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTableView,
    QTextBrowser,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)


class ImageGallery(QWidget):
    load_requested = Signal()

    def __init__(self, image_paths: tuple[Path, ...]) -> None:
        super().__init__()
        self.setObjectName("imageGallery")
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
        controls.addWidget(self.previous_button)
        controls.addWidget(self.page_label)
        controls.addWidget(self.load_button)
        controls.addWidget(self.next_button)
        controls.addStretch()
        layout.addLayout(controls)
        self.set_images(image_paths)

    def set_fetching(self, fetching: bool) -> None:
        self.load_button.setText("Fetching.." if fetching else "Fetch Image")
        self.load_button.setEnabled(not fetching)

    def set_images(self, image_paths: tuple[Path, ...]) -> None:
        while self.pages.count():
            page = self.pages.widget(0)
            self.pages.removeWidget(page)
            page.deleteLater()
        for image_path in image_paths:
            image = QLabel()
            image.setObjectName("mediaImage")
            image.setAccessibleName("Cached torrent image")
            image.setAlignment(Qt.AlignmentFlag.AlignCenter)
            image.setScaledContents(False)
            reader = QImageReader(str(image_path))
            if reader.supportsAnimation():
                movie = QMovie(str(image_path), parent=image)
                movie.setScaledSize(
                    reader.size().scaled(760, 520, Qt.AspectRatioMode.KeepAspectRatio)
                )
                image.setMovie(movie)
            else:
                image.setPixmap(
                    QPixmap(str(image_path)).scaled(
                        760,
                        520,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            self.pages.addWidget(image)
        multiple_images = self.pages.count() > 1
        self.previous_button.setEnabled(multiple_images)
        self.next_button.setEnabled(multiple_images)
        if self.pages.count():
            self._set_current_index(0)
        else:
            self.page_label.setText("0 / 0")

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
        if current_image.movie() is not None:
            current_image.movie().start()
        self.page_label.setText(f"{index + 1} / {self.pages.count()}")


class DropZone(QGroupBox):
    file_selected = Signal(Path)

    def __init__(self) -> None:
        super().__init__("Open torrent file")
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 32, 24, 32)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_text = QLabel("Drag a .torrent file here")
        drop_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        separator = QLabel("or")
        separator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.browse_button = QPushButton("Browse…")
        self.browse_button.setAccessibleDescription("Choose a local .torrent file")
        layout.addWidget(drop_text)
        layout.addWidget(separator)
        layout.addWidget(self.browse_button, alignment=Qt.AlignmentFlag.AlignCenter)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        self.setTitle("Drop torrent file")
        event.acceptProposedAction()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self.setTitle("Open torrent file")

    def dropEvent(self, event: QDropEvent) -> None:
        self.setTitle("Open torrent file")
        self.file_selected.emit(Path(event.mimeData().urls()[0].toLocalFile()))
        event.acceptProposedAction()


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
