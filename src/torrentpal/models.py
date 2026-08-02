from dataclasses import dataclass, field

from PySide6.QtCore import QAbstractItemModel, QAbstractTableModel, QModelIndex, Qt

from torrentpal.domain import TorrentMetadata
from torrentpal.formatting import format_date, format_size


class MetadataTableModel(QAbstractTableModel):
    def __init__(self, metadata: TorrentMetadata) -> None:
        super().__init__()
        self.rows = (
            ("Name", metadata.name),
            ("Info hash v1", metadata.info_hash_v1),
            ("Info hash v2", metadata.info_hash_v2),
            ("Created", format_date(metadata.created)),
            ("Created by", metadata.creator),
            ("Comment", metadata.comment),
            ("Piece size", format_size(metadata.piece_size)),
            ("Total size", format_size(metadata.total_size)),
        )

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 2

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            return self.rows[index.row()][index.column()]

    def flags(self, index: QModelIndex):
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


@dataclass
class FileNode:
    name: str
    size: int = 0
    parent: "FileNode | None" = None
    children: list["FileNode"] = field(default_factory=list)


class FileTreeModel(QAbstractItemModel):
    def __init__(self, metadata: TorrentMetadata) -> None:
        super().__init__()
        self.root = FileNode("")
        for torrent_file in sorted(metadata.files, key=lambda item: item.path):
            parent = self.root
            parts = torrent_file.path.replace("\\", "/").split("/")
            for part in parts[:-1]:
                child = next(
                    (node for node in parent.children if node.name == part), None
                )
                if child is None:
                    child = FileNode(part, parent=parent)
                    parent.children.append(child)
                parent = child
            parent.children.append(FileNode(parts[-1], torrent_file.size, parent))

    def index(self, row, column, parent=QModelIndex()):
        parent_node = parent.internalPointer() if parent.isValid() else self.root
        return self.createIndex(row, column, parent_node.children[row])

    def parent(self, index):
        node = index.internalPointer()
        parent_node = node.parent
        if parent_node is self.root or parent_node is None:
            return QModelIndex()
        return self.createIndex(
            parent_node.parent.children.index(parent_node), 0, parent_node
        )

    def rowCount(self, parent=QModelIndex()):
        node = parent.internalPointer() if parent.isValid() else self.root
        return len(node.children)

    def columnCount(self, parent=QModelIndex()):
        return 2

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            node = index.internalPointer()
            return (
                node.name
                if index.column() == 0
                else (format_size(node.size) if node.size else "")
            )

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return ("Name", "Size")[section]


class TrackerModel(QAbstractTableModel):
    def __init__(self, trackers: tuple[str, ...]) -> None:
        super().__init__()
        self.trackers = trackers

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.trackers)

    def columnCount(self, parent=QModelIndex()):
        return 1

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            return self.trackers[index.row()]

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return "Tracker"
