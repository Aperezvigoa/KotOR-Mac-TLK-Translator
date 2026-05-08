"""Stable import path for :class:`FileSystemExplorerWidget`.

The explorer implementation lives in ``filesystem.qfileexplorer``; this module
re-exports it for tests and callers that use the historical
``utility.gui.qt.widgets.item_explorer`` path.
"""

from __future__ import annotations

from utility.gui.qt.filesystem.qfileexplorer.explorer import FileSystemExplorerWidget

__all__ = ["FileSystemExplorerWidget"]
