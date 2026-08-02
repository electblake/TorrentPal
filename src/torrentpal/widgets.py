from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QLabel,
    QPushButton,
    QTableView,
    QTextBrowser,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)


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
