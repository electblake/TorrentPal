from torrentpal.media import cached_images, first_url


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
