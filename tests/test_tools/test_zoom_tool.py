"""ZoomTool: click, Alt+click, right-click, and drag (Navigation PRD 4.3.2; follow-up step 6)."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt
from PyQt6.QtGui import QContextMenuEvent, QMouseEvent
from pytestqt.qtbot import QtBot

from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.core.view import SnapView
from snapmock.tools.tool_manager import ToolManager
from snapmock.tools.zoom_tool import ZoomTool

Modifier = Qt.KeyboardModifier
Button = Qt.MouseButton


def _view(qtbot: QtBot, scene: SnapScene) -> tuple[SnapView, ToolManager]:
    view = SnapView(scene)
    qtbot.addWidget(view)
    view.resize(400, 300)
    view.show()
    manager = ToolManager(scene, SelectionManager(scene))
    manager.register(ZoomTool())
    view.set_tool_manager(manager)
    manager.activate("zoom")
    return view, manager


def _mouse(
    kind: QEvent.Type, point: QPoint, button: Button, modifiers: Modifier = Modifier.NoModifier
) -> QMouseEvent:
    return QMouseEvent(kind, QPointF(point), button, button, modifiers)


def _click(
    view: SnapView,
    point: QPoint,
    *,
    button: Button = Button.LeftButton,
    press: Modifier = Modifier.NoModifier,
    release: Modifier = Modifier.NoModifier,
) -> None:
    view.mousePressEvent(_mouse(QEvent.Type.MouseButtonPress, point, button, press))
    view.mouseReleaseEvent(_mouse(QEvent.Type.MouseButtonRelease, point, button, release))


def _settled(qtbot: QtBot, view: SnapView) -> int:
    """The zoom once the 150 ms zoom animation has run its course."""
    qtbot.wait(300)
    return view.zoom_percent


def test_identity_and_status_hint() -> None:
    tool = ZoomTool()
    assert tool.tool_id == "zoom" and tool.display_name == "Zoom"
    assert tool.status_hint == (
        "Click to zoom in | Alt+click or right-click to zoom out | Drag to zoom region"
    )


def test_left_click_zooms_in_and_alt_at_the_release_zooms_out(
    qtbot: QtBot, scene: SnapScene
) -> None:
    view, _ = _view(qtbot, scene)
    start = view.zoom_percent
    _click(view, QPoint(100, 100))
    assert _settled(qtbot, view) > start
    _click(view, QPoint(100, 100), press=Modifier.AltModifier, release=Modifier.AltModifier)
    assert _settled(qtbot, view) == start


def test_alt_at_the_press_alone_zooms_out(qtbot: QtBot, scene: SnapScene) -> None:
    """The desktop may take Alt before the release: the modifier captured at the press
    counts (follow-up silence 8)."""
    view, _ = _view(qtbot, scene)
    _click(view, QPoint(100, 100))
    zoomed = _settled(qtbot, view)
    _click(view, QPoint(100, 100), press=Modifier.AltModifier)
    assert _settled(qtbot, view) < zoomed
    # A later plain click is a zoom in: the press modifier does not linger
    before = view.zoom_percent
    _click(view, QPoint(100, 100))
    assert _settled(qtbot, view) > before


def test_right_click_zooms_out_and_keeps_the_context_menu_closed(
    qtbot: QtBot, scene: SnapScene
) -> None:
    view, manager = _view(qtbot, scene)
    _click(view, QPoint(100, 100))
    zoomed = _settled(qtbot, view)
    _click(view, QPoint(100, 100), button=Button.RightButton)
    assert _settled(qtbot, view) < zoomed
    event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(100, 100))
    assert manager.handle_context_menu(event)
    # A right release without a press on this tool is not consumed
    tool = manager.active_tool
    assert isinstance(tool, ZoomTool)
    assert not tool.mouse_release(
        _mouse(QEvent.Type.MouseButtonRelease, QPoint(10, 10), Button.RightButton)
    )


def test_drag_zooms_to_the_rectangle(qtbot: QtBot, scene: SnapScene) -> None:
    view, manager = _view(qtbot, scene)
    tool = manager.active_tool
    assert isinstance(tool, ZoomTool)
    view.mousePressEvent(_mouse(QEvent.Type.MouseButtonPress, QPoint(50, 50), Button.LeftButton))
    view.mouseMoveEvent(_mouse(QEvent.Type.MouseMove, QPoint(150, 130), Button.LeftButton))
    assert tool.is_active_operation and tool._zoom_rect_item is not None  # noqa: SLF001
    rect = view.mapToScene(QRectF(50, 50, 100, 80).toRect()).boundingRect()
    view.mouseReleaseEvent(
        _mouse(QEvent.Type.MouseButtonRelease, QPoint(150, 130), Button.LeftButton)
    )
    assert tool._zoom_rect_item is None and not tool.is_active_operation  # noqa: SLF001
    shown = view.mapToScene(view.viewport().rect()).boundingRect()  # type: ignore[union-attr]
    assert shown.contains(rect)
    assert view.zoom_percent > 100
