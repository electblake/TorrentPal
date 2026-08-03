from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from torrentpal.domain import TorrentLibraryEntry
from torrentpal.media import cached_image_count
from torrentpal.metadata_cache import metadata_cache_path, save_cached_metadata
from torrentpal.parser import parse_torrent


class TorrentLoader(QObject):
    scan_started = Signal(int, int)
    item_started = Signal(int, str)
    torrent_loaded = Signal(int, object)
    progress = Signal(int, int, int)
    finished = Signal(int, int, int, str, bool)

    def __init__(
        self,
        generation: int,
        torrent_directory: Path,
        data_directory: Path,
        scan_metadata: bool,
    ) -> None:
        super().__init__()
        self.generation = generation
        self.torrent_directory = torrent_directory
        self.data_directory = data_directory
        self.scan_metadata = scan_metadata

    @Slot()
    def load(self) -> None:
        try:
            paths = list(self.torrent_directory.glob("*.torrent"))
            paths.sort(key=self._modified_time, reverse=True)
        except OSError as error:
            self.scan_started.emit(self.generation, 0)
            self.finished.emit(self.generation, 0, 0, str(error), False)
            return

        total = len(paths)
        self.scan_started.emit(self.generation, total)
        torrent_hashes: set[str] = set()
        unreadable_count = 0
        cache_failure_count = 0
        for processed_count, path in enumerate(paths, start=1):
            if QThread.currentThread().isInterruptionRequested():
                self.finished.emit(
                    self.generation,
                    unreadable_count,
                    cache_failure_count,
                    "",
                    True,
                )
                return
            self.item_started.emit(self.generation, path.name)
            if self.scan_metadata:
                try:
                    metadata = parse_torrent(path)
                except Exception:
                    unreadable_count += 1
                    self.progress.emit(self.generation, processed_count, total)
                    continue
                torrent_hash = metadata.info_hash_v1 or metadata.info_hash_v2
                display_name = metadata.name
                total_size = metadata.total_size
                file_count = len(metadata.files)
                tracker_count = len(metadata.trackers)
                try:
                    save_cached_metadata(self.data_directory, path, metadata)
                except Exception:
                    cache_failure_count += 1
                metadata_cached = metadata_cache_path(
                    self.data_directory, path
                ).is_file()
            else:
                torrent_hash = path.stem
                display_name = path.name
                total_size = None
                file_count = None
                tracker_count = None
                metadata_cached = metadata_cache_path(
                    self.data_directory, path
                ).is_file()
            if torrent_hash not in torrent_hashes:
                torrent_hashes.add(torrent_hash)
                self.torrent_loaded.emit(
                    self.generation,
                    TorrentLibraryEntry(
                        path=path,
                        display_name=display_name,
                        torrent_hash=torrent_hash,
                        cached_image_count=cached_image_count(
                            self.data_directory, torrent_hash
                        ),
                        metadata_cached=metadata_cached,
                        total_size=total_size,
                        file_count=file_count,
                        tracker_count=tracker_count,
                    ),
                )
            self.progress.emit(self.generation, processed_count, total)
        self.finished.emit(
            self.generation,
            unreadable_count,
            cache_failure_count,
            "",
            False,
        )

    @staticmethod
    def _modified_time(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0


class MetadataReloadWorker(QObject):
    loaded = Signal(object, object)
    failed = Signal(object, str)
    finished = Signal()

    def __init__(
        self, torrent_path: Path, data_directory: Path
    ) -> None:
        super().__init__()
        self.torrent_path = torrent_path
        self.data_directory = data_directory

    @Slot()
    def load(self) -> None:
        try:
            metadata = parse_torrent(self.torrent_path)
            save_cached_metadata(
                self.data_directory,
                self.torrent_path,
                metadata,
            )
        except Exception as error:
            self.failed.emit(self, str(error))
        else:
            self.loaded.emit(self, metadata)
        finally:
            self.finished.emit()
