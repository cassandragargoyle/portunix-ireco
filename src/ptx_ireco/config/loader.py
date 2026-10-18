"""Read, write, and look up ``ireco.config.json`` files.

The loader is responsible for:

- Locating the file in a working directory (no recursive lookup —
  ADR-0004 says only the cwd is consulted).
- Parsing JSON with friendly errors.
- Validating against the v1 schema via
  :func:`ptx_ireco.config.validator.validate_config`.
- Writing atomically (temp + ``os.replace``) so a crash mid-write
  cannot corrupt an existing file.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from ptx_ireco.config.schema import CONFIG_VERSION
from ptx_ireco.config.validator import ValidationError, validate_config

CONFIG_FILENAME = "ireco.config.json"


class ConfigError(RuntimeError):
    """Base class for config-related errors raised by this package."""


class ConfigNotFoundError(ConfigError, FileNotFoundError):
    """Raised when no ``ireco.config.json`` exists at the expected path."""


class InvalidConfigError(ConfigError):
    """Raised when a config file is unparseable or fails schema validation."""

    def __init__(self, message: str, *, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors = list(errors) if errors else []


class UnsupportedVersionError(InvalidConfigError):
    """Raised specifically for ``version`` mismatch — a clearer signal than
    a generic schema failure (acceptance criterion A.3)."""


def find_config(directory: str | Path) -> Path | None:
    """Return the path to ``ireco.config.json`` in ``directory`` if it exists.

    Returns ``None`` when the file is absent — callers decide whether
    that is an error in their context.
    """
    candidate = Path(directory) / CONFIG_FILENAME
    return candidate if candidate.is_file() else None


def resolve_models_path(raw: str | None, config_path: str | Path | None) -> Path | None:
    """Return the ``models.path`` root or ``None`` when the key is absent.

    A relative path is anchored at the config file's parent directory;
    without a known config location it stays relative and is resolved
    against cwd by the caller. Shared by the worker and the watcher so
    both read the same config the same way (issue #8).
    """
    if not raw:
        return None
    p = Path(raw)
    if p.is_absolute():
        return p
    if config_path is not None:
        return (Path(config_path).parent / p).resolve()
    return p


def load_config_dict(data: Any, *, source: str | Path = "<dict>") -> dict[str, Any]:
    """Validate an in-memory ``data`` value as a v1 config and return it.

    Raises :class:`UnsupportedVersionError` for a version mismatch and
    :class:`InvalidConfigError` for any other schema failure.
    """
    if isinstance(data, dict) and "version" in data:
        version = data["version"]
        if isinstance(version, int) and not isinstance(version, bool):
            if version != CONFIG_VERSION:
                raise UnsupportedVersionError(
                    f"{source}: unsupported config version {version} "
                    f"(this build understands version {CONFIG_VERSION})"
                )

    try:
        validate_config(data)
    except ValidationError as exc:
        raise InvalidConfigError(
            f"{source}: invalid configuration:\n  - " + "\n  - ".join(exc.errors),
            errors=exc.errors,
        ) from exc

    assert isinstance(data, dict)  # narrowed by validate_config
    return data


def load_config_file(path: str | Path) -> dict[str, Any]:
    """Read ``path`` as JSON and validate as a v1 config.

    Args:
        path: Filesystem path to a candidate ``ireco.config.json``.

    Raises:
        ConfigNotFoundError: ``path`` does not exist.
        InvalidConfigError: file is not valid JSON or fails schema.
        UnsupportedVersionError: ``version`` does not equal 1.
    """
    p = Path(path)
    if not p.is_file():
        raise ConfigNotFoundError(f"Config file not found: {p}")

    try:
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise InvalidConfigError(f"{p}: invalid JSON: {exc}") from exc

    return load_config_dict(data, source=str(p))


def write_config(path: str | Path, data: dict[str, Any]) -> None:
    """Atomically write ``data`` to ``path`` as pretty-printed UTF-8 JSON.

    The data is validated before any filesystem write, so a malformed
    document never produces a partial file. The write itself uses a
    temp file in the same directory plus :func:`os.replace`, which is
    atomic on POSIX and best-effort atomic on Windows.
    """
    load_config_dict(data, source=str(path))

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, target)
    except BaseException:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise
