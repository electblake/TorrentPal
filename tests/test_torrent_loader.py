from pathlib import Path

from torrentpal.metadata_cache import load_cached_metadata
from torrentpal.parser import parse_torrent
from torrentpal.torrent_loader import TorrentLoader

FIXTURE = Path(__file__).parent / "fixtures" / "known.torrent"


def write_torrent(path: Path, name: str) -> Path:
    encoded_name = name.encode()
    contents = FIXTURE.read_bytes().replace(
        b"4:name9:known.bin",
        b"4:name" + str(len(encoded_name)).encode() + b":" + encoded_name,
    )
    path.write_bytes(contents)
    return path


def test_loader_emits_each_torrent_progress_and_cached_image_count(tmp_path) -> None:
    torrent_directory = tmp_path / "torrents"
    torrent_directory.mkdir()
    first = write_torrent(torrent_directory / "first.torrent", "first.bin")
    write_torrent(torrent_directory / "second.torrent", "second.bin")
    (torrent_directory / "invalid.torrent").write_text(
        "not a torrent", encoding="utf-8"
    )
    first_hash = parse_torrent(first).info_hash_v1
    (tmp_path / f"{first_hash}_100x100_0").write_bytes(b"image")
    (tmp_path / f"{first_hash}_200x150_1").write_bytes(b"image")
    (tmp_path / f"{first_hash}_not-an-image").write_bytes(b"ignore")
    started = []
    item_started = []
    loaded = []
    progress = []
    finished = []
    loader = TorrentLoader(7, torrent_directory, tmp_path, True)
    loader.scan_started.connect(
        lambda generation, total: started.append((generation, total))
    )
    loader.item_started.connect(
        lambda generation, name: item_started.append((generation, name))
    )
    loader.torrent_loaded.connect(
        lambda generation, entry: loaded.append((generation, entry))
    )
    loader.progress.connect(
        lambda generation, processed, total: progress.append(
            (generation, processed, total)
        )
    )
    loader.finished.connect(
        lambda generation, unreadable, cache_failures, error, canceled: finished.append(
            (generation, unreadable, cache_failures, error, canceled)
        )
    )

    loader.load()

    assert started == [(7, 3)]
    assert {name for _, name in item_started} == {
        "first.torrent",
        "second.torrent",
        "invalid.torrent",
    }
    assert len(loaded) == 2
    assert {entry.display_name: entry.cached_image_count for _, entry in loaded} == {
        "first.bin": 2,
        "second.bin": 0,
    }
    assert all(entry.metadata_cached for _, entry in loaded)
    assert load_cached_metadata(tmp_path, first) == parse_torrent(first)
    assert progress == [(7, 1, 3), (7, 2, 3), (7, 3, 3)]
    assert finished == [(7, 1, 0, "", False)]
