"""Tests for Layer and LayerManager."""

from snapmock.config.constants import LAYER_Z_RANGE
from snapmock.core.layer import Layer
from snapmock.core.layer_manager import LayerManager


def test_layer_defaults() -> None:
    layer = Layer(name="Test")
    assert layer.name == "Test"
    assert layer.visible is True
    assert layer.locked is False
    assert layer.opacity == 1.0
    assert layer.item_ids == []
    assert len(layer.layer_id) > 0


def test_layer_clone() -> None:
    layer = Layer(name="Original")
    clone = layer.clone()
    assert clone.name == "Original copy"
    assert clone.layer_id != layer.layer_id


def test_add_layer() -> None:
    mgr = LayerManager()
    layer = mgr.add_layer("Background")
    assert mgr.count == 1
    assert layer.name == "Background"
    assert mgr.active_layer is layer


def test_add_layer_auto_names() -> None:
    mgr = LayerManager()
    mgr.add_layer()
    mgr.add_layer()
    assert mgr.layers[0].name == "Layer 1"
    assert mgr.layers[1].name == "Layer 2"


def test_remove_layer() -> None:
    mgr = LayerManager()
    mgr.add_layer("A")
    b = mgr.add_layer("B")
    removed = mgr.remove_layer(b.layer_id)
    assert removed is b
    assert mgr.count == 1


def test_cannot_remove_last_layer() -> None:
    mgr = LayerManager()
    layer = mgr.add_layer("Solo")
    result = mgr.remove_layer(layer.layer_id)
    assert result is None
    assert mgr.count == 1


def test_move_layer() -> None:
    mgr = LayerManager()
    a = mgr.add_layer("A")
    mgr.add_layer("B")
    mgr.add_layer("C")
    mgr.move_layer(a.layer_id, 2)
    assert mgr.layers[2].layer_id == a.layer_id
    assert mgr.layers[0].name == "B"
    assert mgr.layers[1].name == "C"


def test_z_base_calculation() -> None:
    mgr = LayerManager()
    mgr.add_layer("Bottom")
    mgr.add_layer("Middle")
    mgr.add_layer("Top")
    layers = mgr.layers
    assert layers[0].z_base == 0
    assert layers[1].z_base == LAYER_Z_RANGE
    assert layers[2].z_base == 2 * LAYER_Z_RANGE


def test_set_active() -> None:
    mgr = LayerManager()
    mgr.add_layer("A")
    b = mgr.add_layer("B")
    mgr.set_active(b.layer_id)
    assert mgr.active_layer_id == b.layer_id


def test_visibility() -> None:
    mgr = LayerManager()
    layer = mgr.add_layer("A")
    mgr.set_visibility(layer.layer_id, False)
    assert mgr.layer_by_id(layer.layer_id) is not None
    result = mgr.layer_by_id(layer.layer_id)
    assert result is not None and result.visible is False


def test_lock() -> None:
    mgr = LayerManager()
    layer = mgr.add_layer("A")
    mgr.set_locked(layer.layer_id, True)
    result = mgr.layer_by_id(layer.layer_id)
    assert result is not None and result.locked is True


def test_opacity_clamped() -> None:
    mgr = LayerManager()
    layer = mgr.add_layer("A")
    mgr.set_opacity(layer.layer_id, 1.5)
    result = mgr.layer_by_id(layer.layer_id)
    assert result is not None and result.opacity == 1.0
    mgr.set_opacity(layer.layer_id, -0.5)
    result = mgr.layer_by_id(layer.layer_id)
    assert result is not None and result.opacity == 0.0


def test_rename_layer() -> None:
    mgr = LayerManager()
    layer = mgr.add_layer("Old Name")
    mgr.rename_layer(layer.layer_id, "New Name")
    result = mgr.layer_by_id(layer.layer_id)
    assert result is not None and result.name == "New Name"
