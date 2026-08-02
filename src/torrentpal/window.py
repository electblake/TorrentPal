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
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from torrentpal.config import SETTINGS
from torrentpal.domain import TorrentMetadata
from torrentpal.models import FileTreeModel, MetadataTableModel, TrackerModel
from torrentpal.parser import parse_torrent
from torrentpal.widgets import (
    CollapsiblePanel,
    DropZone,
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
        title = QLabel("Settings")
        title_font = QFont(title.font())
        title_font.setPointSize(title_font.pointSize() + 4)
        title_font.setWeight(QFont.Weight.DemiBold)
        title.setFont(title_font)
        layout.addWidget(title)
        layout.addSpacing(16)

        form = QFormLayout()
        self.cookies_path = QLineEdit()
        self.cookies_path.setObjectName("cookiesFilePath")
        self.cookies_path.setPlaceholderText("Path to browser cookies export")
        form.addRow("Cookies file", self.cookies_path)
        layout.addLayout(form)
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
        self.cookies_path.setText(SETTINGS.value("cookies_file", type=str))
        self.stack.setCurrentWidget(self.settings_page)

    def _save_settings(self) -> None:
        SETTINGS.setValue("cookies_file", self.cookies_path.text())
        SETTINGS.sync()
        self.stack.setCurrentWidget(self.input_page)

    def _reset_settings(self) -> None:
        SETTINGS.remove("cookies_file")
        SETTINGS.sync()
        self.cookies_path.clear()

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
