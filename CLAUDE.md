# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

SnapMock — an open-source multi-platform screenshot annotation & UI mockup tool built with Python and PyQt6.

## Commands

All commands use `uv run` to execute within the managed virtual environment:

- **Run app:** `uv run python -m snapmock`
- **Run tests:** `uv run pytest`
- **Run single test:** `uv run pytest tests/test_app.py::test_name -v`
- **Lint:** `uv run ruff check .`
- **Lint fix:** `uv run ruff check . --fix`
- **Format:** `uv run ruff format .`
- **Type check:** `uv run mypy snapmock`
- **Install/sync deps:** `uv sync`
- **Add dependency:** `uv add <package>`
- **Add dev dependency:** `uv add --group dev <package>`

## Project Structure

```
snapmock/              # Main application package
    __init__.py        # Package root, exports __version__
    __main__.py        # Entry point for python -m snapmock
    app.py             # QApplication bootstrap
    main_window.py     # MainWindow (QMainWindow subclass)
    config/            # Constants, settings, keyboard shortcuts
    core/              # Scene graph, layers, commands, selection, clipboard, rendering
    items/             # SnapGraphicsItem subclasses (vector, text, raster, etc.)
    tools/             # BaseTool subclasses and ToolManager
    commands/          # Command objects for undo/redo
    io/                # File I/O (project save/load, import/export)
    ui/                # UI panels (toolbar, layer panel, property panel, etc.)
    resources/         # Icons, stamps, themes
tests/                 # Test suite
    conftest.py        # Shared pytest-qt fixtures
    test_app.py        # App/window tests
```

## Conventions

- **Python:** ≥ 3.12
- **UI framework:** PyQt6
- **Package manager:** uv
- **Linter/formatter:** ruff (line-length 99, target py312, rules: E, F, W, I, N, UP)
- **Type checker:** mypy (strict mode)
- **Tests:** pytest + pytest-qt
- **Imports:** sorted by ruff (isort-compatible)

## Architecture

- **All mutations via Commands** — tools push commands to CommandStack, never modify scene directly
- **Signals flow up, calls flow down** — UI listens to manager signals, calls manager methods
- **SnapScene owns** LayerManager + CommandStack; MainWindow owns SnapScene, SnapView, ToolManager
- **Layer z-values**: each layer gets z_base = index × 10,000; items offset within range
