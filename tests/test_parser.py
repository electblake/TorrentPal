from pathlib import Path

from torrentpal.parser import parse_torrent

FIXTURE = Path(__file__).parent / "fixtures" / "known.torrent"


def test_parses_known_torrent_fixture() -> None:
    metadata = parse_torrent(FIXTURE)
    assert metadata.name == "known.bin"
    assert metadata.total_size == 12345
    assert metadata.piece_size == 16384
    assert metadata.creator == "TorrentPal"
    assert metadata.comment == "Known fixture"
    assert metadata.trackers == ("http://tracker.example/announce",)
    assert metadata.files[0].path == "known.bin"
    assert metadata.magnet_uri.startswith("magnet:?xt=urn:btih:")
