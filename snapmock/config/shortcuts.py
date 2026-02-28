"""Keyboard shortcut definitions.

Each entry maps a logical action name to a key sequence string
compatible with ``QKeySequence``.
"""

SHORTCUTS: dict[str, str] = {
    # File
    "file.new": "Ctrl+N",
    "file.open": "Ctrl+O",
    "file.save": "Ctrl+S",
    "file.save_as": "Ctrl+Shift+S",
    "file.export": "Ctrl+E",
    # Edit
    "edit.undo": "Ctrl+Z",
    "edit.redo": "Ctrl+Shift+Z",
    "edit.cut": "Ctrl+X",
    "edit.copy": "Ctrl+C",
    "edit.paste": "Ctrl+V",
    "edit.duplicate": "Ctrl+D",
    "edit.delete": "Delete",
    "edit.select_all": "Ctrl+A",
    "edit.select_all_layers": "Ctrl+Shift+A",
    "edit.deselect": "Escape",
    # View
    "view.zoom_in": "Ctrl+=",
    "view.zoom_out": "Ctrl+-",
    "view.fit_window": "Ctrl+0",
    "view.actual_size": "Ctrl+1",
    "view.toggle_grid": "Ctrl+'",
    "view.toggle_rulers": "Ctrl+R",
    "view.zoom_to_selection": "Ctrl+Shift+0",
    # Tools
    "tool.select": "V",
    "tool.rectangle": "R",
    "tool.ellipse": "E",
    "tool.line": "L",
    "tool.arrow": "A",
    "tool.freehand": "P",
    "tool.text": "T",
    "tool.callout": "C",
    "tool.highlight": "H",
    "tool.blur": "B",
    "tool.numbered_step": "N",
    "tool.stamp": "S",
    "tool.crop": "X",
    "tool.raster_select": "M",
    "tool.eyedropper": "I",
    # Layers
    "layer.new": "Ctrl+Shift+N",
    "layer.delete": "Ctrl+Shift+Delete",
    "layer.merge_down": "Ctrl+Shift+E",
    # Additional edit shortcuts
    "edit.paste_in_place": "Ctrl+Shift+V",
    # Additional tools
    "tool.pan": "",
    "tool.zoom": "Z",
    "tool.lasso_select": "Shift+M",
}
