"""Tests for LayerPropertiesDialog."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from snapmock.core.layer import Layer
from snapmock.ui.layer_properties_dialog import LayerPropertiesDialog


def _make_layer(**kwargs: object) -> Layer:
    defaults: dict[str, object] = {
        "name": "Layer 1",
        "visible": True,
        "locked": False,
        "opacity": 1.0,
    }
    defaults.update(kwargs)
    return Layer(**defaults)  # type: ignore[arg-type]


class TestLayerPropertiesDialogDisplay:
    def test_shows_layer_name(self, qtbot: QtBot) -> None:
        layer = _make_layer(name="Background")
        dlg = LayerPropertiesDialog(layer)
        qtbot.addWidget(dlg)
        assert dlg._name_edit.text() == "Background"

    def test_shows_opacity_as_percentage(self, qtbot: QtBot) -> None:
        layer = _make_layer(opacity=0.75)
        dlg = LayerPropertiesDialog(layer)
        qtbot.addWidget(dlg)
        assert dlg._opacity_spin.value() == 75  # noqa: PLR2004

    def test_shows_item_count(self, qtbot: QtBot) -> None:
        layer = _make_layer()
        layer.item_ids = ["a", "b", "c"]
        dlg = LayerPropertiesDialog(layer)
        qtbot.addWidget(dlg)
        assert dlg._item_count_label.text() == "3"


class TestLayerPropertiesDialogGetChanges:
    def test_returns_empty_when_nothing_changed(self, qtbot: QtBot) -> None:
        layer = _make_layer()
        dlg = LayerPropertiesDialog(layer)
        qtbot.addWidget(dlg)
        assert dlg.get_changes() == {}

    def test_detects_name_change(self, qtbot: QtBot) -> None:
        layer = _make_layer(name="Layer 1")
        dlg = LayerPropertiesDialog(layer)
        qtbot.addWidget(dlg)
        dlg._name_edit.setText("Renamed Layer")
        changes = dlg.get_changes()
        assert "name" in changes
        assert changes["name"] == ("Layer 1", "Renamed Layer")

    def test_detects_opacity_change(self, qtbot: QtBot) -> None:
        layer = _make_layer(opacity=1.0)
        dlg = LayerPropertiesDialog(layer)
        qtbot.addWidget(dlg)
        dlg._opacity_spin.setValue(50)
        changes = dlg.get_changes()
        assert "opacity" in changes
        assert changes["opacity"][0] == pytest.approx(1.0)
        assert changes["opacity"][1] == pytest.approx(0.5)

    def test_detects_visible_change(self, qtbot: QtBot) -> None:
        layer = _make_layer(visible=True)
        dlg = LayerPropertiesDialog(layer)
        qtbot.addWidget(dlg)
        dlg._visible_cb.setChecked(False)
        changes = dlg.get_changes()
        assert "visible" in changes
        assert changes["visible"] == (True, False)

    def test_detects_locked_change(self, qtbot: QtBot) -> None:
        layer = _make_layer(locked=False)
        dlg = LayerPropertiesDialog(layer)
        qtbot.addWidget(dlg)
        dlg._locked_cb.setChecked(True)
        changes = dlg.get_changes()
        assert "locked" in changes
        assert changes["locked"] == (False, True)
