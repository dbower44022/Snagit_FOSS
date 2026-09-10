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


# ---- blend mode and layer type (Navigation and Raster Operations follow-up, step 2) ----


def test_layer_blend_mode_and_type_defaults_and_clone() -> None:
    from snapmock.core.layer import (
        BLEND_MODES,
        LAYER_TYPE_ANNOTATION,
        LAYER_TYPE_BACKGROUND,
        LAYER_TYPES,
    )

    layer = Layer(name="Test")
    assert layer.blend_mode == "Normal" and layer.layer_type == LAYER_TYPE_ANNOTATION
    assert not layer.is_background
    assert BLEND_MODES == (
        "Normal",
        "Multiply",
        "Screen",
        "Overlay",
        "Darken",
        "Lighten",
        "Difference",
    )
    assert LAYER_TYPES == ("Background", "Annotation", "RasterRegion")
    background = Layer(name="Background", layer_type=LAYER_TYPE_BACKGROUND, blend_mode="Multiply")
    assert background.is_background
    clone = background.clone()
    # A copy keeps the blend mode and is an Annotation layer (decision 2)
    assert clone.blend_mode == "Multiply" and clone.layer_type == LAYER_TYPE_ANNOTATION


def test_composition_mode_names_map_to_qt() -> None:
    from PyQt6.QtGui import QPainter

    from snapmock.core.layer import BLEND_MODES, composition_mode, normalize_blend_mode

    modes = {composition_mode(name) for name in BLEND_MODES}
    assert len(modes) == len(BLEND_MODES)
    assert composition_mode("Normal") is QPainter.CompositionMode.CompositionMode_SourceOver
    assert composition_mode("Multiply") is QPainter.CompositionMode.CompositionMode_Multiply
    assert composition_mode("no such mode") is QPainter.CompositionMode.CompositionMode_SourceOver
    assert normalize_blend_mode(None) == "Normal" and normalize_blend_mode("Screen") == "Screen"


def test_set_blend_mode_and_type_emit() -> None:
    lm = LayerManager()
    layer = lm.add_layer("A")
    seen: list[tuple[str, str]] = []
    lm.layer_blend_mode_changed.connect(lambda lid, mode: seen.append((lid, mode)))
    lm.layer_type_changed.connect(lambda lid, kind: seen.append((lid, kind)))
    lm.set_blend_mode(layer.layer_id, "Overlay")
    lm.set_blend_mode(layer.layer_id, "bogus")
    lm.set_layer_type(layer.layer_id, "Background")
    assert seen == [
        (layer.layer_id, "Overlay"),
        (layer.layer_id, "Normal"),
        (layer.layer_id, "Background"),
    ]
    assert lm.background_layer is layer


def test_background_layer_is_pinned_to_the_bottom() -> None:
    lm = LayerManager()
    a = lm.add_layer("A")
    b = lm.add_layer("B")
    c = lm.add_layer("C")
    # Making a layer Background moves it to the bottom
    lm.set_layer_type(b.layer_id, "Background")
    assert [layer.name for layer in lm.layers] == ["B", "A", "C"]
    # The Background layer never moves
    lm.move_layer(b.layer_id, 2)
    assert [layer.name for layer in lm.layers] == ["B", "A", "C"]
    # No other layer moves below it: Move to Bottom lands above it
    lm.move_layer(c.layer_id, 0)
    assert [layer.name for layer in lm.layers] == ["B", "C", "A"]
    # No layer is inserted below it
    lm.add_layer("D", 0)
    assert [layer.name for layer in lm.layers] == ["B", "D", "C", "A"]
    lm.insert_layer(Layer(name="E"), 0)
    assert [layer.name for layer in lm.layers] == ["B", "E", "D", "C", "A"]
    assert lm.layers[0].z_base == 0 and lm.layers[1].z_base == LAYER_Z_RANGE
    # Without a Background layer the bottom is open
    lm.set_layer_type(b.layer_id, "Annotation")
    lm.move_layer(a.layer_id, 0)
    assert lm.layers[0] is a
