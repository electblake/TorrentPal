from PySide6 import QtCore


def test_pyside6_is_available() -> None:
    assert QtCore.__version__
