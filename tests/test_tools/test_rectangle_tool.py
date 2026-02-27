"""Tests for RectangleTool."""

from PyQt6.QtCore import Qt

from snapmock.tools.rectangle_tool import RectangleTool


def test_rectangle_tool_identity() -> None:
    tool = RectangleTool()
    assert tool.tool_id == "rectangle"
    assert tool.display_name == "Rectangle"
    assert tool.cursor == Qt.CursorShape.CrossCursor
