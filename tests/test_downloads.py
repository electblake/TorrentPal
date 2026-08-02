from io import BytesIO

import pytest

import torrentpal.downloads
from torrentpal.downloads import TorrentDownloadError, download_torrent


def test_download_torrent_keeps_authentication_in_url(tmp_path, monkeypatch) -> None:
    torrent_bytes = b"d4:infod4:name4:testee"
    requested_url = (
        "https://tracker.example/download.php?id=42&authkey=secret&torrent_pass=pass"
    )

    def open_url(url, timeout):
        assert url == requested_url
        assert timeout == 30.0
        return BytesIO(torrent_bytes)

    monkeypatch.setattr(torrentpal.downloads, "urlopen", open_url)

    downloaded_path = download_torrent(requested_url, tmp_path)

    assert downloaded_path.suffix == ".torrent"
    assert downloaded_path.read_bytes() == torrent_bytes


@pytest.mark.parametrize(
    "url", ["", "file:///tmp/test.torrent", "tracker.example/file"]
)
def test_download_torrent_requires_http_url(tmp_path, url) -> None:
    with pytest.raises(TorrentDownloadError, match="valid HTTP or HTTPS URL"):
        download_torrent(url, tmp_path)
