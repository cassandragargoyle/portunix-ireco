"""Read/write helpers for ``.vim.json`` files.

The on-disk shape is whatever VIM 1.4/1.5 emits — a dict with top-level
``vim_version``, ``document``, and ``layers`` keys. This module only
preserves that shape; it does not translate between Python-native VIM
dataclasses (in :mod:`ptx_reco.vim.model.vim_document`) and the dict.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

VimDoc = dict[str, Any]


def read_vim_json(path: str | Path) -> VimDoc:
    """Load a ``.vim.json`` file as a plain dict.

    Args:
        path: Path to the ``.vim.json`` file.

    Returns:
        Parsed JSON content.

    Raises:
        FileNotFoundError: ``path`` does not exist.
        ValueError: file is not valid JSON or lacks required top-level keys.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"VIM file not found: {p}")

    try:
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {p}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"VIM root must be an object: {p}")
    if "layers" not in data:
        raise ValueError(f"Missing 'layers' key in VIM file: {p}")
    return data


def write_vim_json(path: str | Path, data: VimDoc) -> None:
    """Write ``data`` to ``path`` as UTF-8 JSON with two-space indent.

    Atomic: writes to a sibling ``.tmp`` file and renames.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(p)


def get_structural_blocks(doc: VimDoc) -> list[dict[str, Any]]:
    """Return the ``layers.structural.blocks`` list (or ``[]`` if absent)."""
    layers = doc.get("layers") or {}
    structural = layers.get("structural") or {}
    blocks = structural.get("blocks") or []
    return list(blocks)


def get_structural_barcodes(doc: VimDoc) -> list[dict[str, Any]]:
    """Return the ``layers.structural.barcodes`` list (or ``[]`` if absent)."""
    layers = doc.get("layers") or {}
    structural = layers.get("structural") or {}
    barcodes = structural.get("barcodes") or []
    return list(barcodes)


def set_semantic_entities(doc: VimDoc, entities: list[dict[str, Any]]) -> None:
    """Overwrite ``layers.semantic.entities`` with ``entities``.

    Other ``layers.semantic`` fields (``payments``, ``stemming``) are
    preserved if present. If ``layers.semantic`` is missing, it is created.
    """
    layers = doc.setdefault("layers", {})
    semantic = layers.setdefault("semantic", {})
    semantic["entities"] = entities
