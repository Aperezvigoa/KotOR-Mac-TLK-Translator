"""Reusable theme selector dialog: search, theme list, style list, live-apply signals. No Toolset deps."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, ClassVar

from qtpy.QtCore import (
    Qt,
    Signal,  # pyright: ignore[reportPrivateImportUsage]
)
from qtpy.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from utility.gui.qt.widgets.theme.theme_manager import ThemeManager

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget


def _default_tr(text: str) -> str:
    """Default no-op translator; host can pass a real tr."""
    return text


class ThemeSelectorDialog(QDialog):
    """Non-blocking dialog for selecting application themes and styles. Emits theme_changed/style_changed."""

    theme_changed: ClassVar[Signal] = Signal(str)
    style_changed: ClassVar[Signal] = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        theme_manager: ThemeManager | None = None,
        available_themes: list[str] | None = None,
        available_styles: list[str] | None = None,
        current_theme: str | None = None,
        current_style: str | None = None,
        tr: Callable[[str], str] | None = None,
        install_no_scroll_filter: bool = True,
    ):
        """Initialize the theme selector dialog.

        Args:
            parent: Parent widget.
            theme_manager: Optional ThemeManager; if not provided a default is created.
            available_themes: List of theme names (default: from manager.get_available_themes()).
            available_styles: List of style names (default: from manager.get_default_styles()).
            current_theme: Currently selected theme name.
            current_style: Currently selected style name (empty string = native/system).
            tr: Optional translator; defaults to identity.
            install_no_scroll_filter: If True, install utility NoScrollEventFilter on list/line edit widgets.
        """
        super().__init__(parent)
        self._tr = tr or _default_tr
        self._manager = theme_manager or ThemeManager()
        self._available_themes = (
            available_themes
            if available_themes is not None
            else list(self._manager.get_available_themes())
        )
        self._available_styles = (
            available_styles
            if available_styles is not None
            else list(self._manager.get_default_styles())
        )
        self._current_theme = current_theme
        self._current_style = current_style
        self._apply_button: QPushButton | None = None
        self._init_ui()
        self._populate_lists()
        if install_no_scroll_filter:
            self._install_no_scroll_filter()

    def _init_ui(self) -> None:
        """Set up the user interface (Python-built, no .ui file)."""
        self.setMinimumSize(450, 500)
        self.resize(550, 650)
        self.setWindowTitle(self._tr("Theme Selection"))
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowTitleHint,
        )

        main = QVBoxLayout(self)
        main.setSpacing(10)
        main.setContentsMargins(15, 15, 15, 15)

        # Search
        search_layout = QVBoxLayout()
        search_layout.addWidget(QLabel(self._tr("Search:")))
        search_row = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText(self._tr("Filter themes and styles..."))
        search_row.addWidget(self._search_edit)
        self._clear_search_button = QPushButton(self._tr("Clear"))
        self._clear_search_button.clicked.connect(self._search_edit.clear)
        search_row.addWidget(self._clear_search_button)
        search_layout.addLayout(search_row)
        main.addLayout(search_layout)

        # Themes section
        themes_layout = QVBoxLayout()
        themes_layout.setSpacing(5)
        themes_header = QHBoxLayout()
        themes_label = QLabel(self._tr("Themes:"))
        themes_label.setStyleSheet("font-weight: bold; font-size: 12pt; margin-top: 5px;")
        themes_header.addWidget(themes_label)
        self._current_theme_display = QLineEdit()
        self._current_theme_display.setReadOnly(True)
        self._current_theme_display.setPlaceholderText(self._tr("No theme selected"))
        self._current_theme_display.setStyleSheet(
            "background-color: palette(base); border: 1px solid palette(mid); padding: 2px;",
        )
        themes_header.addWidget(self._current_theme_display)
        themes_layout.addLayout(themes_header)
        self._themes_list = QListWidget()
        self._themes_list.setMinimumHeight(200)
        self._themes_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._themes_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._themes_list.setAlternatingRowColors(True)
        themes_layout.addWidget(self._themes_list)
        main.addLayout(themes_layout)

        # Styles section
        styles_layout = QVBoxLayout()
        styles_layout.setSpacing(5)
        styles_header = QHBoxLayout()
        styles_label = QLabel(self._tr("Application Styles:"))
        styles_label.setStyleSheet("font-weight: bold; font-size: 12pt; margin-top: 5px;")
        styles_header.addWidget(styles_label)
        self._current_style_display = QLineEdit()
        self._current_style_display.setReadOnly(True)
        self._current_style_display.setPlaceholderText(self._tr("No style selected"))
        self._current_style_display.setStyleSheet(
            "background-color: palette(base); border: 1px solid palette(mid); padding: 2px;",
        )
        styles_header.addWidget(self._current_style_display)
        styles_layout.addLayout(styles_header)
        self._styles_list = QListWidget()
        self._styles_list.setMaximumHeight(150)
        self._styles_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._styles_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._styles_list.setAlternatingRowColors(True)
        styles_layout.addWidget(self._styles_list)
        main.addLayout(styles_layout)

        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        main.addWidget(self._status_label)

        # Buttons
        self._button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._button_box.rejected.connect(self.close)
        restore_btn = QPushButton(self._tr("Restore Current"))
        restore_btn.clicked.connect(self._restore_current_selection)
        self._button_box.addButton(restore_btn, QDialogButtonBox.ButtonRole.ResetRole)
        self._apply_button = QPushButton(self._tr("Apply"))
        self._apply_button.setDefault(True)
        self._apply_button.clicked.connect(self._apply_selection)
        self._button_box.addButton(self._apply_button, QDialogButtonBox.ButtonRole.AcceptRole)
        main.addWidget(self._button_box)

        # Connections
        self._search_edit.textChanged.connect(self._filter_items)
        self._themes_list.itemSelectionChanged.connect(self._on_theme_selection_changed)
        self._themes_list.itemDoubleClicked.connect(self._on_theme_double_clicked)
        self._styles_list.itemSelectionChanged.connect(self._on_style_selection_changed)
        self._styles_list.itemDoubleClicked.connect(self._on_style_double_clicked)

    def _install_no_scroll_filter(self) -> None:
        """Install utility NoScrollEventFilter on list and line edit widgets."""
        from utility.gui.qt.adapters.itemmodels.filters import NoScrollEventFilter

        no_scroll = NoScrollEventFilter(self)
        no_scroll.setup_filter(
            include_types=[QListWidget, QLineEdit],
            parent_widget=self,
        )

    def _populate_lists(self) -> None:
        """Populate theme and style lists and current displays."""
        self._themes_list.clear()
        for theme_name in sorted(self._available_themes):
            item = QListWidgetItem(theme_name)
            self._themes_list.addItem(item)

        self._styles_list.clear()
        native_item = QListWidgetItem(self._tr("Native (System Default)"))
        native_item.setData(Qt.ItemDataRole.UserRole, "")
        self._styles_list.addItem(native_item)
        for style_name in sorted(self._available_styles):
            item = QListWidgetItem(style_name)
            item.setData(Qt.ItemDataRole.UserRole, style_name)
            self._styles_list.addItem(item)
        self._restore_current_selection()

    def _filter_items(self, text: str) -> None:
        """Filter theme and style lists by search text."""
        search = text.lower()
        for i in range(self._themes_list.count()):
            item = self._themes_list.item(i)
            if item:
                item.setHidden(search not in item.text().lower())
        for i in range(self._styles_list.count()):
            item = self._styles_list.item(i)
            if item:
                item.setHidden(search not in item.text().lower())
        self._update_status_label()

    def _find_matching_item(
        self, list_widget: QListWidget, value: str, *, user_role: bool = False
    ) -> QListWidgetItem | None:
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item is None:
                continue
            candidate = item.data(Qt.ItemDataRole.UserRole) if user_role else item.text()
            if candidate == value:
                return item
        return None

    def _restore_current_selection(self) -> None:
        if self._current_theme:
            theme_item = self._find_matching_item(self._themes_list, self._current_theme)
            if theme_item is not None:
                self._themes_list.setCurrentItem(theme_item)
                self._themes_list.scrollToItem(theme_item)
        else:
            self._themes_list.clearSelection()

        current_style = "" if self._current_style is None else self._current_style
        style_item = self._find_matching_item(self._styles_list, current_style, user_role=True)
        if style_item is not None:
            self._styles_list.setCurrentItem(style_item)
            self._styles_list.scrollToItem(style_item)
        else:
            self._styles_list.clearSelection()

        self._sync_displays_from_selection()

    def _selected_theme(self) -> str | None:
        item = self._themes_list.currentItem()
        return item.text() if item is not None else None

    def _selected_style(self) -> str | None:
        item = self._styles_list.currentItem()
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return "" if value == "" else (str(value) if value is not None else item.text())

    def _sync_displays_from_selection(self) -> None:
        theme = self._selected_theme()
        style = self._selected_style()
        self._current_theme_display.setText(theme or self._current_theme or "")
        if style == "":
            self._current_style_display.setText(self._tr("Native (System Default)"))
        else:
            self._current_style_display.setText(style or self._current_style or "")
        self._update_status_label()

    def _visible_count(self, list_widget: QListWidget) -> int:
        return sum(1 for i in range(list_widget.count()) if not list_widget.item(i).isHidden())

    def _update_status_label(self) -> None:
        theme = self._selected_theme() or self._current_theme or self._tr("None")
        style = self._selected_style()
        if style is None:
            if self._current_style == "":
                style_text = self._tr("Native (System Default)")
            else:
                style_text = self._current_style or self._tr("None")
        elif style == "":
            style_text = self._tr("Native (System Default)")
        else:
            style_text = style
        self._status_label.setText(
            self._tr(
                "Visible: {themes} themes, {styles} styles. Selected: {theme} / {style}."
            ).format(
                themes=self._visible_count(self._themes_list),
                styles=self._visible_count(self._styles_list),
                theme=theme,
                style=style_text,
            )
        )

    def _on_theme_selection_changed(self) -> None:
        """Handle theme list selection changes."""
        self._sync_displays_from_selection()

    def _on_style_selection_changed(self) -> None:
        """Handle style list selection changes."""
        self._sync_displays_from_selection()

    def _on_theme_double_clicked(self, item: QListWidgetItem) -> None:
        """Apply immediately on theme double-click."""
        self._themes_list.setCurrentItem(item)
        self._apply_selection()

    def _on_style_double_clicked(self, item: QListWidgetItem) -> None:
        """Apply immediately on style double-click."""
        self._styles_list.setCurrentItem(item)
        self._apply_selection()

    def _apply_selection(self) -> None:
        """Emit theme_changed and/or style_changed for selected items."""
        selected_theme = self._selected_theme()
        selected_style = self._selected_style()
        if selected_theme is not None:
            self._current_theme = selected_theme
            self.theme_changed.emit(selected_theme)
        if selected_style is not None:
            self._current_style = selected_style
            self.style_changed.emit(selected_style)
        self._sync_displays_from_selection()

    def update_current_selection(
        self,
        theme_name: str | None = None,
        style_name: str | None = None,
    ) -> None:
        """Update the current selection and refresh lists."""
        if theme_name is not None:
            self._current_theme = theme_name
        if style_name is not None:
            self._current_style = style_name
        self._restore_current_selection()
