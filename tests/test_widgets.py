from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from torrentpal.widgets import ImageGallery


def test_clicking_image_cycles_view_mode_and_updates_label(qtbot, tmp_path) -> None:
    image_path = tmp_path / "image.png"
    pixmap = QPixmap(400, 200)
    pixmap.fill(Qt.GlobalColor.red)
    pixmap.save(str(image_path), "PNG")
    gallery = ImageGallery((image_path,))
    qtbot.addWidget(gallery)
    image = gallery.pages.currentWidget()

    assert gallery.view_mode == "Fit"
    assert gallery.view_mode_label.text() == "View: Fit"

    expected_modes = ("Fill Vertical", "Fill Width", "Actual", "Fit")
    for expected_mode in expected_modes:
        qtbot.mouseClick(image, Qt.MouseButton.LeftButton)
        assert gallery.view_mode == expected_mode
        assert gallery.view_mode_label.text() == f"View: {expected_mode}"


def test_image_view_modes_scale_from_original_image(qtbot, tmp_path) -> None:
    image_path = tmp_path / "image.png"
    pixmap = QPixmap(400, 200)
    pixmap.fill(Qt.GlobalColor.red)
    pixmap.save(str(image_path), "PNG")
    gallery = ImageGallery((image_path,))
    qtbot.addWidget(gallery)
    image = gallery.pages.currentWidget()

    assert image.pixmap().size().toTuple() == (760, 380)

    qtbot.mouseClick(image, Qt.MouseButton.LeftButton)
    assert image.pixmap().size().toTuple() == (1040, 520)

    qtbot.mouseClick(image, Qt.MouseButton.LeftButton)
    assert image.pixmap().size().toTuple() == (760, 380)

    qtbot.mouseClick(image, Qt.MouseButton.LeftButton)
    assert image.pixmap().size().toTuple() == (400, 200)
