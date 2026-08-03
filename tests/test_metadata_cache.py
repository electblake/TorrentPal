import json
from pathlib import Path

import pytest

from torrentpal.metadata_cache import (
    MetadataCacheError,
    load_cached_metadata,
    metadata_cache_path,
    save_cached_metadata,
)
from torrentpal.parser import parse_torrent

FIXTURE = Path(__file__).parent / "fixtures" / "known.torrent"


def test_metadata_cache_round_trips_as_json(tmp_path) -> None:
    metadata = parse_torrent(FIXTURE)

    cache_path = save_cached_metadata(tmp_path, FIXTURE, metadata)

    assert cache_path == metadata_cache_path(tmp_path, FIXTURE)
    assert json.loads(cache_path.read_text(encoding="utf-8"))["metadata"][
        "name"
    ] == "known.bin"
    assert load_cached_metadata(tmp_path, FIXTURE) == metadata


def test_metadata_cache_rejects_invalid_json(tmp_path) -> None:
    cache_path = metadata_cache_path(tmp_path, FIXTURE)
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text("not json", encoding="utf-8")

    with pytest.raises(MetadataCacheError, match="invalid metadata cache"):
        load_cached_metadata(tmp_path, FIXTURE)
