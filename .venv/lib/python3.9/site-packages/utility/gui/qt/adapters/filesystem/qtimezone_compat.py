"""QTimeZone UTC helper across Qt bindings (PyQt6 uses QTimeZone.utc(), not QTimeZone.UTC)."""

from __future__ import annotations

from qtpy.QtCore import QTimeZone


def qtimezone_utc() -> QTimeZone:
    """Return a QTimeZone representing UTC for the active Qt binding."""
    utc_meth = getattr(QTimeZone, "utc", None)
    if callable(utc_meth):
        return utc_meth()
    initialization = getattr(QTimeZone, "Initialization", None)
    if initialization is not None:
        utc_init = getattr(initialization, "UTC", None)
        if utc_init is not None:
            return QTimeZone(utc_init)
    return QTimeZone(b"UTC")
