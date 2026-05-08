"""Reusable Qt theme manager, catalog, and selector dialog for host-owned settings."""

from utility.gui.qt.widgets.theme.theme_apply import (
    apply_style,
    apply_tooltip_style_to_app,
    get_original_style,
    get_tooltip_stylesheet,
)
from utility.gui.qt.widgets.theme.theme_catalog import build_builtin_theme_configs
from utility.gui.qt.widgets.theme.theme_dialog import ThemeDialog
from utility.gui.qt.widgets.theme.theme_manager import ThemeManager
from utility.gui.qt.widgets.theme.theme_selector_dialog import ThemeSelectorDialog
from utility.gui.qt.widgets.theme.theme_types import ThemeConfig, ThemeSources

__all__ = [
    "ThemeConfig",
    "ThemeDialog",
    "ThemeManager",
    "ThemeSelectorDialog",
    "ThemeSources",
    "apply_style",
    "apply_tooltip_style_to_app",
    "build_builtin_theme_configs",
    "get_original_style",
    "get_tooltip_stylesheet",
]
