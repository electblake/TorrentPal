import json

import pytest

from torrentpal.media import (
    CookieConfigurationError,
    cached_images,
    download_images,
    first_url,
    format_browser_cookie_json,
    load_browser_cookies,
    parse_browser_cookies,
)


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


def test_missing_cookie_export_means_no_cookies(tmp_path) -> None:
    missing = tmp_path / "missing.txt"

    assert load_browser_cookies(missing) == []


def test_parses_json_cookie_export() -> None:
    cookies = parse_browser_cookies(
        '[{"name":"session","value":"secret","domain":".example.com",'
        '"path":"/","httpOnly":true,"secure":true,'
        '"expirationDate":1893456000}]'
    )

    assert cookies == [
        {
            "name": "session",
            "value": "secret",
            "domain": ".example.com",
            "path": "/",
            "httpOnly": True,
            "secure": True,
            "expires": 1893456000.0,
        }
    ]


@pytest.mark.parametrize(
    "contents",
    ["", "not a cookie export", "# Netscape HTTP Cookie File\n"],
)
def test_rejects_non_json_cookie_export(contents) -> None:
    with pytest.raises(CookieConfigurationError, match="JSON"):
        parse_browser_cookies(contents)


def test_formats_valid_cookie_export_as_json() -> None:
    formatted = format_browser_cookie_json(
        '[{"name":"sid","value":"value","domain":"example.com","path":"/"}]'
    )

    assert json.loads(formatted) == [
        {
            "name": "sid",
            "value": "value",
            "domain": "example.com",
            "path": "/",
        }
    ]


def test_download_images_clicks_show_links_before_indexing(tmp_path) -> None:
    image = tmp_path / "gallery.svg"
    image.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"></svg>',
        encoding="utf-8",
    )
    page = tmp_path / "tracker.html"
    page.write_text(
        """<script>
        const BBCode = {spoiler(link, gallery) {
            document.querySelector(gallery).innerHTML =
                `<img src="gallery.svg?${gallery.slice(1)}">`;
            link.textContent = 'Hide';
        }};
        </script>
        <a href="javascript:void(0);"
           onclick="BBCode.spoiler(this, '#gallery-one');">Show</a>
        <div id="gallery-one"></div>
        <a href="javascript:void(0);"
           onclick="BBCode.spoiler(this, '#gallery-two');">Show</a>
        <div id="gallery-two"></div>""",
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

    assert len(images) == 2
    assert [image.name for image in images] == [
        "hash_320x180_0",
        "hash_320x180_1",
    ]
    assert "Revealing hidden content" in statuses
    assert "Revealed 2 hidden content sections" in statuses
