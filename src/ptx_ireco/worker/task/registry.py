"""Task type registry for ``ireco.invoice.*`` handlers.

Four task types are registered:

- ``ireco.invoice.parse`` — input ``{pdf_path, out_path}`` → result dict.
- ``ireco.invoice.extract`` — input ``{vim_path, out_path?, in_place?}``
  + ``config.{models_path?, invoice.*}`` → result dict.
- ``ireco.invoice.run`` — input ``{pdf_path, out_path}`` → result dict.
- ``ireco.invoice.export`` — input ``{vim_path, output_dir, options}``
  → ``{outputs, metadata}``. Added for issue 006 / ADR-0007.

Per ADR-0005 / issue 003, ``out_path`` is mandatory whenever a write
happens. The TaskAdapter is a machine surface; defaulting paths is a
CLI concern, so missing ``out_path`` for ``parse``/``run`` is mapped
to ``INVALID_INPUT`` rather than being silently auto-derived.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ptx_ireco.export.isdoc import api as isdoc_api
from ptx_ireco.worker.api.pipeline import (
    ExtractionOptions,
    ExtractionResult,
    ModelPaths,
    extract,
    parse,
    run,
)

# Handler signature: (input_data, config_data) -> contract result dict.
TaskHandler = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


class _HandlerInputError(ValueError):
    """Raised by handlers for missing/invalid TaskRequest input fields."""


def _require_str(data: dict[str, Any], key: str, *, prefix: str) -> str:
    value = data.get(key)
    if not value or not isinstance(value, str):
        raise _HandlerInputError(f"Missing required field: '{prefix}.{key}'")
    return value


def _resolve_repo_root(config: dict[str, Any]) -> Path:
    """``models.path`` from the request's config block → cwd ``./``.

    The CLI front-end is responsible for layering an explicit ``--models``
    flag on top of this; at the TaskAdapter boundary only the request's
    ``config`` block and cwd are visible (single source of truth).
    """
    models_section = config.get("models") or {}
    raw = models_section.get("path") or config.get("models_path")
    return Path(raw) if raw else Path.cwd()


def _build_extraction_options(config: dict[str, Any]) -> ExtractionOptions | None:
    invoice = config.get("invoice") or {}
    if invoice.get("tenancy") != "known":
        return None
    recipients = invoice.get("recipients") or []
    return ExtractionOptions(recipients=recipients)


def _format_extraction(
    result: ExtractionResult, *, model_paths: ModelPaths, vim_path: Path
) -> dict[str, Any]:
    """Mirror the driver CLI's stdout summary for the TaskAdapter result."""
    profile_root = model_paths.profiles.parent.parent
    extraction_root = model_paths.extraction.parent.parent
    summary: dict[str, Any] = {
        "vim_path": str(vim_path),
        "template_match": result.template_match.template_id if result.template_match else None,
        "country": result.detected_country,
        "profile": str(result.profile.path.relative_to(profile_root)),
        "flexylayout": str(result.flexylayout_path.relative_to(extraction_root)),
        "entities": [e.type for e in result.entities],
    }
    if result.recipient_id is not None:
        summary["recipient_id"] = result.recipient_id
    return summary


def _handle_parse(input_data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    pdf_path = _require_str(input_data, "pdf_path", prefix="input")
    out_path = _require_str(input_data, "out_path", prefix="input")
    written = parse(pdf_path, out_path)
    return {"vim_path": str(written)}


def _handle_extract(input_data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    vim_path = _require_str(input_data, "vim_path", prefix="input")
    out_path = input_data.get("out_path")
    in_place = bool(input_data.get("in_place", False))
    if out_path is None and not in_place:
        in_place = True  # default to in-place when neither is provided
    repo_root = _resolve_repo_root(config)
    model_paths = ModelPaths.default(repo_root)
    options = _build_extraction_options(config)
    result = extract(
        vim_path,
        out=out_path,
        in_place=in_place,
        models=repo_root,
        options=options,
    )
    target = Path(vim_path) if in_place or out_path is None else Path(out_path)
    return _format_extraction(result, model_paths=model_paths, vim_path=target)


def _handle_run(input_data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    pdf_path = _require_str(input_data, "pdf_path", prefix="input")
    out_path = _require_str(input_data, "out_path", prefix="input")
    repo_root = _resolve_repo_root(config)
    model_paths = ModelPaths.default(repo_root)
    options = _build_extraction_options(config)
    result = run(
        pdf_path,
        out_path,
        models=repo_root,
        options=options,
    )
    return _format_extraction(result, model_paths=model_paths, vim_path=Path(out_path))


def _handle_export(input_data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Run the ISDOC export step (issue 006 / ADR-0007).

    ``options`` is forwarded to :func:`ptx_ireco.export.isdoc.api.export`;
    unknown keys are rejected as ``INVALID_INPUT`` rather than silently
    ignored, so downstream typos surface early.
    """
    vim_path = _require_str(input_data, "vim_path", prefix="input")
    output_dir = input_data.get("output_dir")
    options = input_data.get("options") or {}
    if not isinstance(options, dict):
        raise _HandlerInputError("'input.options' must be a JSON object")
    allowed_options = {
        "format",
        "profile",
        "allow_incomplete",
        "models",
        "source_pdf",
    }
    unknown = set(options) - allowed_options
    if unknown:
        raise _HandlerInputError(
            f"Unknown export options: {sorted(unknown)} "
            f"(allowed: {sorted(allowed_options)})"
        )
    repo_root = _resolve_repo_root(config)
    models_value = options.get("models")
    models = Path(models_value) if models_value else repo_root
    result = isdoc_api.export(
        Path(vim_path),
        out_dir=Path(output_dir) if output_dir else None,
        format=options.get("format", "isdoc"),
        profile=options.get("profile", "standard"),
        allow_incomplete=bool(options.get("allow_incomplete", False)),
        models=models,
        source_pdf=Path(options["source_pdf"]) if options.get("source_pdf") else None,
    )
    outputs = [str(result.isdoc_path), str(result.provenance_path)]
    if result.bundle_path is not None:
        outputs.append(str(result.bundle_path))
    metadata: dict[str, Any] = {
        "isdoc_version": "6.0.2",
        "profile": result.profile,
        "validations": dict(result.validations),
    }
    if result.errors:
        metadata["validation_errors"] = [e.to_dict() for e in result.errors]
    return {"outputs": outputs, "metadata": metadata}


_REGISTRY: dict[str, TaskHandler] = {
    "ireco.invoice.parse": _handle_parse,
    "ireco.invoice.extract": _handle_extract,
    "ireco.invoice.run": _handle_run,
    "ireco.invoice.export": _handle_export,
}


def get_handler(task_type: str) -> TaskHandler | None:
    return _REGISTRY.get(task_type)


def list_task_types() -> list[str]:
    return list(_REGISTRY.keys())
