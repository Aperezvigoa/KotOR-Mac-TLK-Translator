from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import QObject, QTimer, Signal  # pyright: ignore[reportPrivateImportUsage]


class FileSystemWatcherError(OSError): ...


class PyFileSystemWatcher(QObject):
    directoryChanged = Signal(str)
    fileChanged = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._watcher: dict[Path, float] = {}
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_all)
        self._timer.setInterval(100)

    def addPath(self, path: str):
        path_obj = Path(path)
        if path_obj in self._watcher:
            return
        if not path_obj.is_file() and not path_obj.is_dir():
            raise FileSystemWatcherError(f"Failed to add path: {path}")
        self._watcher[path_obj] = path_obj.stat().st_mtime
        if not self._timer.isActive():
            self._timer.start()

    def removePath(self, path: str):
        path_obj = Path(path)
        self._watcher.pop(path_obj, None)
        if not self._watcher:
            self._timer.stop()

    def files(self) -> list[str]:
        return [str(p) for p in self._watcher if p.is_file()]

    def directories(self) -> list[str]:
        return [str(p) for p in self._watcher if p.is_dir()]

    def _check_all(self):
        for path_obj, last_modified in list(self._watcher.items()):
            try:
                current_modified = path_obj.stat().st_mtime
            except OSError:
                continue
            if current_modified != last_modified:
                self._watcher[path_obj] = current_modified
                if path_obj.is_file():
                    self.fileChanged.emit(str(path_obj))
                else:
                    self.directoryChanged.emit(str(path_obj))
