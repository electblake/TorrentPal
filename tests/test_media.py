import json

from torrentpal.media import cached_images, download_images, first_url


def test_first_url_from_comment() -> None:
    assert (
        first_url("Details: https://example.com/page more")
        == "https://example.com/page"
    )


def test_cached_images_are_sorted_largest_first(tmp_path) -> None:
    small = tmp_path / "hash_640x480_0"
    large = tmp_path / "hash_1920x1080_1"
    medium = tmp_path / "hash_1280x720_2"
    for path in (small, large, medium):
        path.touch()

    assert cached_images(tmp_path, "hash", 10, 10, 10) == (large, medium, small)
    assert cached_images(tmp_path, "hash", 1000, 700, 1) == (large,)


def test_download_images_clicks_show_links_before_indexing(tmp_path) -> None:
    image = tmp_path / "gallery.svg"
    image.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"></svg>',
        encoding="utf-8",
    )
    page = tmp_path / "tracker.html"
    page.write_text(
        """<script>
        const BBCode = {spoiler(link) {
            document.querySelector('#gallery').innerHTML =
                '<img src="gallery.svg">';
            link.textContent = 'Hide';
        }};
        </script>
        <a href="javascript:void(0);" onclick="BBCode.spoiler(this);">Show</a>
        <div id="gallery"></div>""",
        encoding="utf-8",
    )
    cookies = tmp_path / "cookies.json"
    cookies.write_text(json.dumps([]), encoding="utf-8")
    statuses = []

    images = download_images(
        page.as_uri(),
        cookies,
        tmp_path,
        "hash",
        320,
        180,
        10,
        True,
        statuses.append,
    )

    assert len(images) == 1
    assert images[0].name == "hash_320x180_0"
    assert "Revealing hidden content" in statuses
