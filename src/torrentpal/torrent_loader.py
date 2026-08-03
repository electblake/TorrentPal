from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from torrentpal.media import cached_image_count
from torrentpal.parser import parse_torrent


class TorrentLoader(QObject):
    scan_started = Signal(int, int)
    torrent_loaded = Signal(int, object, str, int)
    progress = Signal(int, int, int)
    finished = Signal(int, int, str, bool)

    def __init__(
        self, generation: int, torrent_directory: Path, data_directory: Path
    ) -> None:
        super().__init__()
        self.generation = generation
        self.torrent_directory = torrent_directory
        self.data_directory = data_directory

    @Slot()
    def load(self) -> None:
        try:
            paths = list(self.torrent_directory.glob("*.torrent"))
            paths.sort(key=self._modified_time, reverse=True)
        except OSError as error:
            self.scan_started.emit(self.generation, 0)
            self.finished.emit(self.generation, 0, str(error), False)
            return

        total = len(paths)
        self.scan_started.emit(self.generation, total)
        torrent_hashes: set[str] = set()
        unreadable_count = 0
        for processed_count, path in enumerate(paths, start=1):
            if QThread.currentThread().isInterruptionRequested():
                self.finished.emit(self.generation, unreadable_count, "", True)
                return
            try:
                metadata = parse_torrent(path)
            except Exception:
                unreadable_count += 1
            else:
                torrent_hash = metadata.info_hash_v1 or metadata.info_hash_v2
                if torrent_hash not in torrent_hashes:
                    torrent_hashes.add(torrent_hash)
                    self.torrent_loaded.emit(
                        self.generation,
                        path,
                        metadata.name,
                        cached_image_count(self.data_directory, torrent_hash),
                    )
            self.progress.emit(self.generation, processed_count, total)
        self.finished.emit(self.generation, unreadable_count, "", False)

    @staticmethod
    def _modified_time(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0
