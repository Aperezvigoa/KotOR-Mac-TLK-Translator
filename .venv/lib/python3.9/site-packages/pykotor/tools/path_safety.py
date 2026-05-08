"""Path canonicalization and allowlist validation for extract/write operations.

Per KotorMCP redesign plan: path_safety.py provides shared helpers so extract
and write operations do not write outside intended bases (path traversal,
symlink escape, overlong paths). Used by CLI get_cmd, MCP handle_extract_resource,
and (optionally) write_override/create_archive.
"""

from __future__ import annotations

import os

from pathlib import Path

# Platform-appropriate max path length; 4096 is safe on Windows and common on Unix
MAX_PATH_LENGTH = 4096


def resolve_and_validate_under_base(
    user_path: str | Path,
    base: Path,
    *,
    allow_nonexistent: bool = True,
) -> Path:
    """Resolve user_path to an absolute path and ensure it is under base.

    Rejects path traversal, symlink escape out of base, and overlong paths.
    Use for extract output and write_override/create_archive targets.

    Args:
        user_path: User-provided path (file or directory).
        base: Allowed base directory; resolved path must be under this.
        allow_nonexistent: If True, path may not exist yet (e.g. output file).
            If False, path must exist (strict resolve).

    Returns:
        Resolved absolute Path under base.

    Raises:
        ValueError: If path is outside base, too long, or invalid.
    """
    base_resolved = Path(base).expanduser().resolve()
    if not base_resolved.is_dir() and allow_nonexistent:
        base_resolved = base_resolved.parent
    p = Path(user_path).expanduser()
    if allow_nonexistent:
        try:
            resolved = p.resolve()
        except OSError:
            resolved = (base_resolved / p).resolve()
    else:
        resolved = p.resolve(strict=True)
    if len(str(resolved)) > MAX_PATH_LENGTH:
        raise ValueError(
            f"Path length exceeds maximum ({MAX_PATH_LENGTH}): {len(str(resolved))}",
        )
    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        raise ValueError(
            f"Path is outside allowed base: {resolved} not under {base_resolved}",
        ) from None
    return resolved


def get_extract_base() -> Path:
    """Return the default base directory for extract operations (MCP/server).

    Uses PYKOTOR_EXTRACT_DIR if set, otherwise current working directory.
    CLI get_cmd typically uses explicit --output and validates against CWD
    or a caller-provided base.
    """
    env = os.environ.get("PYKOTOR_EXTRACT_DIR", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path.cwd()


def validate_extract_output_path(
    user_path: str | Path,
    base: Path | None = None,
) -> Path:
    """Validate and resolve an extract output path under the allowed base.

    For CLI: pass base=Path.cwd() or the directory part of --output.
    For MCP: pass base=get_extract_base() or None (uses get_extract_base()).
    """
    if base is None:
        base = get_extract_base()
    return resolve_and_validate_under_base(user_path, base, allow_nonexistent=True)
