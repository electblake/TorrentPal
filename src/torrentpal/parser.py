from datetime import UTC, datetime
from pathlib import Path

import libtorrent as lt

from torrentpal.domain import TorrentFile, TorrentMetadata


def parse_torrent(path: Path) -> TorrentMetadata:
    torrent = lt.torrent_info(str(path))
    hashes = torrent.info_hashes()
    files = torrent.files()
    created_timestamp = torrent.creation_date()

    return TorrentMetadata(
        name=torrent.name(),
        info_hash_v1=str(hashes.v1) if hashes.has_v1() else "",
        info_hash_v2=str(hashes.v2) if hashes.has_v2() else "",
        magnet_uri=lt.make_magnet_uri(torrent),
        created=datetime.fromtimestamp(created_timestamp, UTC)
        if created_timestamp
        else None,
        creator=torrent.creator(),
        comment=torrent.comment(),
        trackers=tuple(tracker.url for tracker in torrent.trackers()),
        files=tuple(
            TorrentFile(
                files.file_name(index), files.file_path(index), files.file_size(index)
            )
            for index in range(files.num_files())
        ),
        piece_size=torrent.piece_length(),
        total_size=torrent.total_size(),
    )
