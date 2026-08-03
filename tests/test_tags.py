import json

from torrentpal.domain import Tag
from torrentpal.media import download_tags


def test_download_tags_from_tracker_html(tmp_path) -> None:
    page = tmp_path / "tracker.html"
    page.write_text(
        """<ul id="torrent_tags_list">
        <li><a href="/torrents.php?taglist=fake.tits">fake.tits</a>
            <a href="#tags">[-]</a><a href="#tags">[+]</a><a href="#tags">[N]</a></li>
        <li><a href="/torrents.php?taglist=amateur">amateur</a></li>
        <li><a href="/ignored">ignore-this</a></li>
        </ul>""",
        encoding="utf-8",
    )
    cookies = tmp_path / "cookies.json"
    cookies.write_text(json.dumps([]), encoding="utf-8")

    tags = download_tags(
        page.as_uri(),
        cookies,
        ("#torrent_tags_list",),
        3,
        (r"\[-\]", r"\[N\]", "ignore"),
        5,
        lambda message: None,
    )

    assert tags == (
        Tag("fake.tits", f"file:///{page.drive}/torrents.php?taglist=fake.tits"),
        Tag("amateur", f"file:///{page.drive}/torrents.php?taglist=amateur"),
    )
