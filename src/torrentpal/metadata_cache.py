import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from torrentpal.domain import TorrentFile, TorrentMetadata

CACHE_VERSION = 1


class MetadataCacheError(ValueError):
    pass


def metadata_cache_path(data_directory: Path, torrent_path: Path) -> Path:
    return data_directory / "metadata" / f"{torrent_path.stem}.json"


def load_cached_metadata(
    data_directory: Path, torrent_path: Path
) -> TorrentMetadata | None:
    cache_path = metadata_cache_path(data_directory, torrent_path)
    if not cache_path.is_file():
        return None
    try:
        payload = _mapping(
            json.loads(cache_path.read_text(encoding="utf-8")), "cache"
        )
        if payload.get("cache_version") != CACHE_VERSION:
            raise MetadataCacheError("unsupported metadata cache version")
        data = _mapping(payload["metadata"], "metadata")
        created = data["created"]
        trackers = _list(data["trackers"], "trackers")
        files = _list(data["files"], "files")
        return TorrentMetadata(
            name=_string(data, "name"),
            info_hash_v1=_string(data, "info_hash_v1"),
            info_hash_v2=_string(data, "info_hash_v2"),
            magnet_uri=_string(data, "magnet_uri"),
            created=datetime.fromisoformat(created) if created is not None else None,
            creator=_string(data, "creator"),
            comment=_string(data, "comment"),
            trackers=tuple(_string_value(value, "tracker") for value in trackers),
            files=tuple(
                TorrentFile(
                    name=_string(_mapping(file_data, "file"), "name"),
                    path=_string(_mapping(file_data, "file"), "path"),
                    size=_integer(_mapping(file_data, "file"), "size"),
                )
                for file_data in files
            ),
            piece_size=_integer(data, "piece_size"),
            total_size=_integer(data, "total_size"),
        )
    except MetadataCacheError:
        raise
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise MetadataCacheError(f"invalid metadata cache: {error}") from error
    except OSError as error:
        raise MetadataCacheError(f"could not read metadata cache: {error}") from error


def save_cached_metadata(
    data_directory: Path,
    torrent_path: Path,
    metadata: TorrentMetadata,
) -> Path:
    cache_path = metadata_cache_path(data_directory, torrent_path)
    payload = {
        "cache_version": CACHE_VERSION,
        "metadata": {
            "name": metadata.name,
            "info_hash_v1": metadata.info_hash_v1,
            "info_hash_v2": metadata.info_hash_v2,
            "magnet_uri": metadata.magnet_uri,
            "created": metadata.created.isoformat() if metadata.created else None,
            "creator": metadata.creator,
            "comment": metadata.comment,
            "trackers": list(metadata.trackers),
            "files": [
                {
                    "name": torrent_file.name,
                    "path": torrent_file.path,
                    "size": torrent_file.size,
                }
                for torrent_file in metadata.files
            ],
            "piece_size": metadata.piece_size,
            "total_size": metadata.total_size,
        },
    }
    contents = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.is_file() and cache_path.read_text(encoding="utf-8") == contents:
        return cache_path
    temporary_path = cache_path.with_name(
        f".{cache_path.name}.{uuid4().hex}.writing"
    )
    try:
        temporary_path.write_text(contents, encoding="utf-8")
        temporary_path.replace(cache_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return cache_path


def _string(mapping: dict, key: str) -> str:
    return _string_value(mapping[key], key)


def _string_value(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise MetadataCacheError(f"{name} must be text")
    return value


def _mapping(value: object, name: str) -> dict:
    if not isinstance(value, dict):
        raise MetadataCacheError(f"{name} must be an object")
    return value


def _list(value: object, name: str) -> list:
    if not isinstance(value, list):
        raise MetadataCacheError(f"{name} must be a list")
    return value


def _integer(mapping: dict, key: str) -> int:
    value = mapping[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise MetadataCacheError(f"{key} must be an integer")
    return value
