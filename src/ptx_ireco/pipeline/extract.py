"""Step 2: read a parsed ``.vim.json`` and write its semantic layer.

Idempotency policy: the ``layers.semantic.entities`` array is
**overwritten** on each run. Other ``layers.semantic`` keys (e.g.
``payments``, ``stemming``) are preserved. Re-running ``extract`` on a
file that has already been extracted produces the same output (modulo
flexylayout / template / profile changes).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from ptx_ireco.config.recipient_match import RecipientMatch, match_recipient
from ptx_ireco.invoice.flexy_engine import (
    FlexyExtractionError,
    find_flexylayout,
    load_flexylayout,
    run_flexylayout,
)
from ptx_ireco.invoice.profile_resolver import (
    ProfileNotFoundError,
    ResolvedProfile,
    resolve_profile,
)
from ptx_ireco.invoice.template_match import TemplateMatch, match_templates
from ptx_ireco.vim.io import VimDoc, get_structural_blocks, read_vim_json, set_semantic_entities, write_vim_json
from ptx_ireco.vim.semantic import SemanticEntity

logger = logging.getLogger(__name__)


class ExtractionError(RuntimeError):
    """Raised when extraction cannot complete (no template, no profile, …)."""


@dataclass
class ExtractionOptions:
    """Optional inputs that come from ``ireco.config.json``.

    ``recipients`` mirrors the schema's ``invoice.recipients[]`` for the
    ``known`` tenancy mode; when present, the extractor matches the
    parsed buyer entity against this list and exposes the result via
    :class:`ExtractionResult.recipient_id`. ``None`` (the default) keeps
    the original behavior — no recipient matching is performed.
    """

    recipients: list[dict[str, Any]] | None = None


@dataclass
class ExtractionResult:
    """Outcome of running step 2 against a VIM dict."""

    template_match: TemplateMatch | None
    detected_country: str
    profile: ResolvedProfile
    flexylayout_path: Path
    entities: list[SemanticEntity]
    recipient_id: str | None = None
    recipient_match: RecipientMatch | None = None


@dataclass
class ModelPaths:
    """Paths to the on-disk invoice model directories.

    All three default to the canonical project layout under
    ``models/invoice/`` relative to the current working directory; pass
    explicit values for tests or non-standard installs.
    """

    templates: Path
    profiles: Path
    extraction: Path

    @classmethod
    def default(cls, repo_root: str | Path) -> ModelPaths:
        root = Path(repo_root)
        return cls(
            templates=root / "models" / "invoice" / "templates",
            profiles=root / "models" / "invoice" / "profiles",
            extraction=root / "models" / "invoice" / "extraction",
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract(
    vim_doc: VimDoc,
    model_paths: ModelPaths,
    *,
    options: ExtractionOptions | None = None,
) -> ExtractionResult:
    """Run the extraction pipeline against ``vim_doc`` and return the result.

    The semantic entities are returned but **not** written into
    ``vim_doc``; use :func:`extract_into` or :func:`extract_file` to
    materialize the side effect.
    """
    template = match_templates(vim_doc, model_paths.templates)

    country = template.country if template is not None else _detect_country(vim_doc)
    if country is None:
        raise ExtractionError(
            "Could not determine country: no template matched and no "
            "Czech-style anchors present in document."
        )

    issue_date = _find_issue_date(vim_doc)
    if issue_date is None:
        raise ExtractionError(
            "Could not determine issue_date from document — required for "
            "profile resolution per ADR-0001."
        )

    try:
        profile = resolve_profile(country, issue_date, model_paths.profiles)
    except ProfileNotFoundError as exc:
        raise ExtractionError(str(exc)) from exc

    flexylayout_id = template.flexylayout_id if template is not None else None
    try:
        flexy_path = find_flexylayout(model_paths.extraction, country, flexylayout_id)
    except FileNotFoundError as exc:
        raise ExtractionError(str(exc)) from exc

    flexy = load_flexylayout(flexy_path)
    try:
        entities = run_flexylayout(vim_doc, flexy)
    except FlexyExtractionError as exc:
        raise ExtractionError(f"Flexylayout extraction failed: {exc}") from exc

    recipient_match = _match_buyer_against_recipients(entities, options)
    recipient_id = recipient_match.recipient_id if recipient_match else None

    return ExtractionResult(
        template_match=template,
        detected_country=country,
        profile=profile,
        flexylayout_path=flexy_path,
        entities=entities,
        recipient_id=recipient_id,
        recipient_match=recipient_match,
    )


def extract_into(
    vim_doc: VimDoc,
    model_paths: ModelPaths,
    *,
    options: ExtractionOptions | None = None,
) -> ExtractionResult:
    """Run :func:`extract` and write the entities into ``vim_doc`` in place."""
    result = extract(vim_doc, model_paths, options=options)
    set_semantic_entities(vim_doc, [e.to_dict() for e in result.entities])
    if result.recipient_id is not None:
        document = vim_doc.setdefault("document", {})
        document["recipient_id"] = result.recipient_id
    return result


def extract_file(
    vim_path: str | Path,
    model_paths: ModelPaths,
    *,
    out_path: str | Path | None = None,
    options: ExtractionOptions | None = None,
) -> ExtractionResult:
    """Read ``vim_path``, run extraction, and write the result.

    Args:
        vim_path: Input ``.vim.json`` (output of step 1).
        model_paths: Where templates / profiles / flexylayouts live.
        out_path: Where to write the result. Defaults to ``vim_path``
            (in-place — preserves the "step 2 writes back into the same
            file" invariant from ADR-0003).
        options: Optional ``ExtractionOptions`` (e.g. configured
            recipients for ``known`` tenancy).
    """
    in_path = Path(vim_path)
    target = Path(out_path) if out_path is not None else in_path

    doc = read_vim_json(in_path)
    result = extract_into(doc, model_paths, options=options)
    write_vim_json(target, doc)
    return result


# ---------------------------------------------------------------------------
# Heuristics for country / date detection
# ---------------------------------------------------------------------------


_CZ_ANCHORS = ("DIČ:", "IČO:", "DUZP", "Variabilní symbol", "Česká republika")


def _detect_country(vim_doc: VimDoc) -> str | None:
    text = "\n".join(_block_lines(vim_doc))
    if any(anchor in text for anchor in _CZ_ANCHORS):
        return "CZE"
    return None


def _find_issue_date(vim_doc: VimDoc) -> date | None:
    text = "\n".join(_block_lines(vim_doc))
    # Prefer "Datum vystavení:" (issue date). DUZP fallback only if that
    # is absent — many CZ invoices have both, equal.
    for pattern in (
        r"Datum\s+vystavení:\s*(\d{1,2})\.(\d{1,2})\.(\d{4})",
        r"DUZP:\s*(\d{1,2})\.(\d{1,2})\.(\d{4})",
    ):
        match = re.search(pattern, text)
        if match:
            day, month, year = (int(g) for g in match.groups())
            try:
                return date(year, month, day)
            except ValueError:
                continue
    return None


def _match_buyer_against_recipients(
    entities: list[SemanticEntity],
    options: ExtractionOptions | None,
) -> RecipientMatch | None:
    if options is None or not options.recipients:
        return None
    buyer = next((e for e in entities if e.type == "buyer"), None)
    if buyer is None:
        logger.debug("No 'buyer' entity in extraction; skipping recipient match.")
        return None
    return match_recipient(buyer.fields, options.recipients)


def _block_lines(vim_doc: VimDoc) -> list[str]:
    out: list[str] = []
    for b in get_structural_blocks(vim_doc):
        if b.get("header"):
            out.append(str(b["header"]))
        for line in b.get("content") or []:
            out.append(str(line))
    return out
