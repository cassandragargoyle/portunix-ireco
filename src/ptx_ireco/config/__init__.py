"""Per-directory ``ireco.config.json`` runtime support (ADR-0004).

This package is the **runtime consumer** of ``ireco.config.json``.
Authoring (interactive wizard, ``--from-file`` writer) lives in
``portunix-reco-studio`` since INT-037 (issue #005); see
``ptx_reco_studio.ireco_config`` and ``ptx-reco-studio ireco-config init``.

This package provides:

- :mod:`ptx_ireco.config.validator` — schema validation that emits
  JSON-pointer paths in error messages.
- :mod:`ptx_ireco.config.loader` — read/parse/atomic-write helpers.
- :mod:`ptx_ireco.config.recipient_match` — match a parsed buyer entity
  against the configured recipient list.

The on-disk file lives at the root of a working directory and is
optional; pipeline behavior without it must remain unchanged.
"""

from __future__ import annotations

from ptx_ireco.config.loader import (
    CONFIG_FILENAME,
    ConfigError,
    ConfigNotFoundError,
    InvalidConfigError,
    UnsupportedVersionError,
    find_config,
    load_config_dict,
    load_config_file,
    write_config,
)
from ptx_ireco.config.validator import ValidationError, validate_config

__all__ = [
    "CONFIG_FILENAME",
    "ConfigError",
    "ConfigNotFoundError",
    "InvalidConfigError",
    "UnsupportedVersionError",
    "ValidationError",
    "find_config",
    "load_config_dict",
    "load_config_file",
    "validate_config",
    "write_config",
]
