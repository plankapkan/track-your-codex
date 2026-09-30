"""Project grouping without invoking Git or traversing project contents."""
from pathlib import Path, PurePosixPath, PureWindowsPath
import os
import json
import subprocess
import sys


class FolderPickerUnavailable(RuntimeError):
    pass


def canonical_native_path(value):
    """Resolve local aliases, including existing parents of missing children."""
    if os.name != 'nt' and PureWindowsPath(value).drive:
        return value  # A Windows journal path is not local on POSIX.
    path = Path(value)
    if not path.is_absolute():
        return value
    try:
        return str(path.resolve(strict=False))
    except (OSError, RuntimeError):
        return value  # Keep inaccessible/historical journal paths usable.


def project_under_root(cwd, root):
    normalized = cwd.replace('\\', '/').rstrip('/')
    root = root.replace('\\', '/').rstrip('/')
    left, right = normalized, root
    if PureWindowsPath(root).drive:
        left, right = left.casefold(), right.casefold()
    if left.startswith(right + '/'):
        return normalized[len(root) + 1:].split('/')[0]
    return None


class ProjectResolver:
    def __init__(self, root=None):
        self.root = root
        self.canonical_root = canonical_native_path(root) if root else None
        self.cache = {}

    def resolve(self, cwd):
        if cwd in self.cache:
            return self.cache[cwd]
        value = self._resolve(cwd)
        self.cache[cwd] = value
        return value

    def _resolve(self, cwd):
        if not cwd:
            return 'Без проекта'
        normalized = cwd.replace('\\', '/').rstrip('/')
        parts = normalized.split('/')
        if self.root:
            # Preserve lexical grouping of historical paths first; only a miss
            # needs filesystem canonicalization. resolve() handles /var aliases
            # and Windows short names even if cwd's final directories are gone.
            found = project_under_root(cwd, self.root)
            if found is not None:
                return found
            found = project_under_root(canonical_native_path(cwd), self.canonical_root)
            if found is not None:
                return found
            return 'Без проекта'
        # Preserve legacy grouping even when historical paths no longer exist.
        for i, part in enumerate(parts):
            if part.lower() == 'ai_projects' and i + 1 < len(parts):
                return parts[i + 1]
        path = Path(cwd)
        if path.is_absolute():
            for parent in (path, *path.parents):
                if (parent / '.git').exists():
                    return parent.name or 'Без проекта'
        return PurePosixPath(normalized).name or 'Без проекта'


def validate_root(value):
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Укажите существующую папку или null')
    path = Path(value).expanduser()
    if not path.is_absolute() or not path.is_dir():
        raise ValueError('Папка проектов должна быть существующим абсолютным путём')
    return str(path.resolve())


def pick_folder():
    """Run Tk on its own process/main thread; timeout also reaps the child."""
    try:
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--pick'],
                                capture_output=True, text=True, timeout=120,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FolderPickerUnavailable('Диалог выбора папки недоступен или время ожидания истекло') from exc
    if result.returncode:
        raise FolderPickerUnavailable('Диалог выбора папки недоступен; введите путь вручную')
    try:
        value = json.loads(result.stdout)
    except (ValueError, UnicodeError) as exc:
        raise FolderPickerUnavailable('Не удалось получить результат выбора папки') from exc
    if value is not None and not isinstance(value, str):
        raise FolderPickerUnavailable('Некорректный результат выбора папки')
    return value


if __name__ == '__main__':
    # Errors deliberately result in a nonzero exit status for the HTTP parent.
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    try:
        selected = filedialog.askdirectory(title='Выберите папку проектов', mustexist=True)
        print(json.dumps(selected or None))
    finally:
        root.destroy()
