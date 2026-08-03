from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TorrentFile:
    name: str
    path: str
    size: int


@dataclass(frozen=True, slots=True)
class Tag:
    name: str
    url: str


@dataclass(frozen=True, slots=True)
class TorrentMetadata:
    name: str
    info_hash_v1: str
    info_hash_v2: str
    magnet_uri: str
    created: datetime | None
    creator: str
    comment: str
    trackers: tuple[str, ...]
    files: tuple[TorrentFile, ...]
    piece_size: int
    total_size: int


@dataclass(frozen=True, slots=True)
class TorrentLibraryEntry:
    path: Path
    display_name: str
    torrent_hash: str
    cached_image_count: int
    metadata_cached: bool
    total_size: int | None = None
    file_count: int | None = None
    tracker_count: int | None = None
