from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

MAX_TORRENT_BYTES = 64 * 1024 * 1024


class TorrentDownloadError(RuntimeError):
    """Raised when a torrent URL cannot be downloaded safely."""


def validate_torrent_url(raw_url: str) -> str:
    """Return a trimmed HTTP(S) URL or raise a user-facing validation error."""
    url = raw_url.strip()
    parsed_url = urlsplit(url)
    if parsed_url.scheme.lower() not in {"http", "https"} or not parsed_url.netloc:
        raise TorrentDownloadError("Enter a valid HTTP or HTTPS URL")
    return url


def download_torrent(
    raw_url: str,
    destination_directory: Path,
    timeout: float = 30.0,
) -> Path:
    """Download an HTTP(S) torrent URL into the requested directory."""
    url = validate_torrent_url(raw_url)

    destination_directory.mkdir(parents=True, exist_ok=True)
    downloaded_path: Path | None = None
    try:
        # Pass the complete URL directly. Authentication query parameters therefore
        # remain in the URL; this request does not add authentication headers/cookies.
        with urlopen(url, timeout=timeout) as response:
            with NamedTemporaryFile(
                mode="wb",
                prefix="torrentpal-",
                suffix=".torrent",
                dir=destination_directory,
                delete=False,
            ) as torrent_file:
                downloaded_path = Path(torrent_file.name)
                total_bytes = 0
                while chunk := response.read(64 * 1024):
                    total_bytes += len(chunk)
                    if total_bytes > MAX_TORRENT_BYTES:
                        raise TorrentDownloadError(
                            "Torrent file exceeds the 64 MiB download limit"
                        )
                    torrent_file.write(chunk)
        if total_bytes == 0:
            raise TorrentDownloadError("The server returned an empty file")
    except HTTPError as error:
        if downloaded_path is not None:
            downloaded_path.unlink(missing_ok=True)
        raise TorrentDownloadError(
            f"Server returned HTTP {error.code}: {error.reason}"
        ) from error
    except URLError as error:
        if downloaded_path is not None:
            downloaded_path.unlink(missing_ok=True)
        raise TorrentDownloadError(f"Request failed: {error.reason}") from error
    except Exception:
        if downloaded_path is not None:
            downloaded_path.unlink(missing_ok=True)
        raise

    return downloaded_path
