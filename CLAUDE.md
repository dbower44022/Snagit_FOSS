# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Snagit_FOSS — an open-source multi-platform desktop screen capture application built with Python and PyQt6.

## Commands

All commands use `uv run` to execute within the managed virtual environment:

- **Run app:** `uv run python -m snagit_foss`
- **Run tests:** `uv run pytest`
- **Run single test:** `uv run pytest tests/test_app.py::test_name -v`
- **Lint:** `uv run ruff check .`
- **Lint fix:** `uv run ruff check . --fix`
- **Format:** `uv run ruff format .`
- **Type check:** `uv run mypy snagit_foss`
- **Install/sync deps:** `uv sync`
- **Add dependency:** `uv add <package>`
- **Add dev dependency:** `uv add --group dev <package>`

## Project Structure

```
snagit_foss/           # Main application package
    __init__.py        # Package root, exports __version__
    __main__.py        # Entry point for python -m snagit_foss
    app.py             # QApplication bootstrap and MainWindow
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
