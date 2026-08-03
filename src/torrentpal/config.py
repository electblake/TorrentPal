from platformdirs import user_config_path, user_data_path
from PySide6.QtCore import QSettings

CONFIG_DIR = user_config_path("TorrentPal", appauthor=False, ensure_exists=True)
DATA_DIR = user_data_path("TorrentPal", appauthor=False)
SETTINGS = QSettings(str(CONFIG_DIR / "settings.ini"), QSettings.Format.IniFormat)
DEFAULT_TRACKER_PAGE_TIMEOUT_SECONDS = 120
