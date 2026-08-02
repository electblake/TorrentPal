from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class TorrentFile:
    name: str
    path: str
    size: int


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
