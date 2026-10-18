"""Public Python entry point for ISDOC export.

::

    from ptx_ireco.export.isdoc import api
    result = api.export(Path("scan.vim.json"), format="isdocx")

The façade orchestrates: load VIM → run mapper → emit XML → validate
→ write provenance sidecar → optional ISDOCX bundle.

Behavior gates:

- ``allow_incomplete=False`` (default) — any validation failure
  raises :class:`ValidationFailed` after writing nothing on disk.
- ``allow_incomplete=True`` — non-conformant artefacts are written
  and the failures are returned in :attr:`ExportResult.validations`
  / :attr:`ExportResult.errors`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ptx_ireco.export.isdoc import bundle, writer
from ptx_ireco.export.isdoc.codes import load_field_map
from ptx_ireco.export.isdoc.errors import ExportError, ValidationError
from ptx_ireco.export.isdoc.mapper import Mapper
from ptx_ireco.export.isdoc.provenance import ProvenanceAccumulator
from ptx_ireco.export.isdoc.validator import validate
from ptx_ireco.vim.io import read_vim_json

logger = logging.getLogger(__name__)

ExportFormat = Literal["isdoc", "isdocx"]
ExportProfile = Literal["minimal", "standard", "full"]

_VALID_FORMATS: set[str] = {"isdoc", "isdocx"}
_VALID_PROFILES: set[str] = {"minimal", "standard", "full"}


class ValidationFailed(ExportError):
    """Raised when validation fails and ``allow_incomplete`` is ``False``.

    Attributes:
        errors: All :class:`ValidationError` records produced by the
            validator (across every gate).
    """

    def __init__(self, errors: list[ValidationError]) -> None:
        first = errors[0] if errors else None
        message = (
            f"ISDOC validation failed ({len(errors)} error(s); first: "
            f"{first.message if first else 'unknown'})"
        )
        super().__init__(message)
        self.errors = list(errors)


@dataclass(frozen=True)
class ExportResult:
    """Outcome of one :func:`export` call."""

    format: ExportFormat
    profile: ExportProfile
    isdoc_path: Path
    provenance_path: Path
    bundle_path: Path | None
    validations: dict[str, str]
    errors: list[ValidationError] = field(default_factory=list)


def export(
    vim_path: str | Path,
    *,
    out_dir: str | Path | None = None,
    format: ExportFormat = "isdoc",
    profile: ExportProfile = "standard",
    allow_incomplete: bool = False,
    models: str | Path | None = None,
    source_pdf: str | Path | None = None,
) -> ExportResult:
    """Run an ISDOC export end-to-end.

    Args:
        vim_path: Input ``.vim.json`` (output of step 2 — extract).
        out_dir: Where to write outputs. ``None`` ⇒ ``vim_path``'s
            parent directory.
        format: ``"isdoc"`` (XML only) or ``"isdocx"`` (ZIP bundle).
        profile: Completeness profile.
        allow_incomplete: When ``True``, write artefacts even if
            validation fails (caller still sees the failures).
        models: Repo root containing ``models/invoice/exports/isdoc/``.
            Defaults to ``vim_path``'s parent until it finds a
            ``models/`` folder, then falls back to the cwd.
        source_pdf: Required when ``format == "isdocx"`` and the
            source PDF cannot be auto-discovered next to ``vim_path``
            (or via ``document.source`` inside the VIM file).
    """
    if format not in _VALID_FORMATS:
        raise ExportError(f"Unknown format: {format!r} (expected one of {_VALID_FORMATS})")
    if profile not in _VALID_PROFILES:
        raise ExportError(
            f"Unknown profile: {profile!r} (expected one of {_VALID_PROFILES})"
        )

    vim = Path(vim_path)
    if not vim.is_file():
        raise ExportError(f"VIM input not found: {vim}")

    target_dir = _resolve_out_dir(out_dir, vim)
    models_root = _resolve_models_root(models, vim)
    stem = _stem(vim)

    field_map = load_field_map(models_root)

    vim_doc = read_vim_json(vim)
    provenance = ProvenanceAccumulator(
        isdoc_version=str(field_map.get("isdoc_version") or "6.0.2"),
        vim_source=vim.name,
        vim_version=vim_doc.get("vim_version"),
    )

    mapper = Mapper(field_map, profile=profile, provenance=provenance)
    root = mapper.build(vim_doc)

    serialised = writer.serialize(root)
    report = validate(
        root=root,
        serialised=serialised,
        field_map=field_map,
        profile=profile,
        vim_doc=vim_doc,
        models_root=models_root,
    )
    # Fold transform-time failures (raised by codes.py and caught
    # per-field by the mapper) into the report so allow_incomplete
    # governs them uniformly with the four gates.
    for transform_err in mapper.transform_errors:
        report.add_error(transform_err)
    if mapper.transform_errors:
        report.mark_gate("transform", "fail")
    else:
        report.mark_gate("transform", "pass")

    if not report.passed and not allow_incomplete:
        raise ValidationFailed(report.errors)

    isdoc_path = target_dir / f"{stem}.isdoc"
    provenance_path = target_dir / f"{stem}.isdoc.provenance.json"
    writer.write(root, isdoc_path)
    provenance.write(provenance_path)

    bundle_path: Path | None = None
    if format == "isdocx":
        pdf = _resolve_source_pdf(source_pdf, vim, vim_doc)
        bundle_path = target_dir / f"{stem}.isdocx"
        bundle.write(isdoc_path=isdoc_path, pdf_path=pdf, out_path=bundle_path)

    return ExportResult(
        format=format,
        profile=profile,
        isdoc_path=isdoc_path,
        provenance_path=provenance_path,
        bundle_path=bundle_path,
        validations=dict(report.gates),
        errors=list(report.errors),
    )


# ---------------------------------------------------------------------------
# Plumbing
# ---------------------------------------------------------------------------


def _stem(vim: Path) -> str:
    """Return the base name without the ``.vim.json`` suffix.

    ``scan.vim.json`` → ``scan``; ``foo.json`` (no double suffix) →
    ``foo`` (we strip a single suffix in that fallback path).
    """
    name = vim.name
    if name.endswith(".vim.json"):
        return name[: -len(".vim.json")]
    return vim.stem


def _resolve_out_dir(raw: str | Path | None, vim: Path) -> Path:
    if raw is None:
        return vim.parent
    target = Path(raw)
    if not target.is_dir():
        raise ExportError(f"Output directory does not exist: {target}")
    return target


def _resolve_models_root(raw: str | Path | None, vim: Path) -> Path:
    """Return the directory that contains ``models/invoice/exports/...``.

    Resolution: explicit ``models`` arg → walk up from ``vim``'s
    parent until a ``models`` directory is found → cwd.
    """
    if raw is not None:
        p = Path(raw)
        if not p.is_dir():
            raise ExportError(f"Models root does not exist: {p}")
        return p
    candidate = vim.parent.resolve()
    while candidate != candidate.parent:
        if (candidate / "models").is_dir():
            return candidate
        candidate = candidate.parent
    return Path.cwd()


def _resolve_source_pdf(
    raw: str | Path | None, vim: Path, vim_doc: dict[str, Any]
) -> Path:
    if raw is not None:
        p = Path(raw)
        if not p.is_file():
            raise ExportError(f"Source PDF not found: {p}")
        return p
    next_to = vim.with_suffix("").with_suffix(".pdf")
    if next_to.is_file():
        return next_to
    document = vim_doc.get("document") or {}
    source = document.get("source")
    if source:
        candidate = Path(source)
        if candidate.is_file():
            return candidate
    raise ExportError("isdocx requires --source-pdf or a discoverable PDF")
