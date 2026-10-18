"""Validate ``ireco.config.json`` documents against the v1 schema.

Errors are reported with **JSON-pointer-style paths** (e.g.
``invoice.recipients[0].ico``) so users can locate the offending value
without an external library. The rules implemented here mirror
``docs/schemas/ireco-config-1.0.json`` — when the schema changes, this
module changes with it.
"""

from __future__ import annotations

from typing import Any

from ptx_ireco.config.schema import (
    CONFIG_VERSION,
    DIC_PATTERN,
    DOC_TYPES,
    EXPORT_ISDOC_FORMATS,
    EXPORT_ISDOC_PROFILES,
    EXTRACTION_DEPTHS,
    ICO_PATTERN,
    OCR_MIN_DPI,
    OCR_MODES,
    ORDERS_SOURCES,
    RECIPIENT_ID_PATTERN,
    TENANCY_MODES,
    WATCHER_BACKENDS,
    WATCHER_POST_PROCESS_HANDLERS,
)


class ValidationError(ValueError):
    """One or more schema violations.

    The first message line is a one-liner suitable for CLI display; if
    multiple errors were collected they are joined by newlines.
    """

    def __init__(self, errors: list[str]) -> None:
        if not errors:
            raise ValueError("ValidationError requires at least one error string")
        self.errors = list(errors)
        super().__init__("\n".join(errors))


def validate_config(data: Any) -> None:
    """Validate ``data`` as a v1 ``ireco.config.json`` document.

    Raises :class:`ValidationError` on the first batch of failures (all
    checks at the same level are collected before raising; nested
    failures short-circuit the rest of that subtree to keep messages
    actionable rather than overwhelming).
    """
    errors: list[str] = []
    _validate_root(data, errors)
    if errors:
        raise ValidationError(errors)


# ---------------------------------------------------------------------------
# Root-level checks
# ---------------------------------------------------------------------------


def _validate_root(data: Any, errors: list[str]) -> None:
    if not isinstance(data, dict):
        errors.append("(root): must be a JSON object")
        return

    allowed = {"$schema", "version", "doc_types", "io", "invoice", "watcher", "models", "parse"}
    for extra in sorted(set(data.keys()) - allowed):
        errors.append(f"(root): unknown key '{extra}'")

    _check_version(data, errors)
    doc_types = _check_doc_types(data, errors)
    _check_io(data, errors)
    _check_invoice_section(data, doc_types, errors)
    _check_watcher_section(data, errors)
    _check_models_section(data, errors)
    _check_parse_section(data, errors)


def _check_version(data: dict[str, Any], errors: list[str]) -> None:
    if "version" not in data:
        errors.append("version: required")
        return
    version = data["version"]
    if not isinstance(version, int) or isinstance(version, bool):
        errors.append("version: must be an integer")
        return
    if version != CONFIG_VERSION:
        errors.append(
            f"version: unsupported config version {version} "
            f"(this build understands version {CONFIG_VERSION})"
        )


def _check_doc_types(data: dict[str, Any], errors: list[str]) -> list[str]:
    if "doc_types" not in data:
        errors.append("doc_types: required")
        return []
    value = data["doc_types"]
    if not isinstance(value, list) or not value:
        errors.append("doc_types: must be a non-empty array")
        return []

    seen: set[str] = set()
    valid: list[str] = []
    for i, item in enumerate(value):
        path = f"doc_types[{i}]"
        if not isinstance(item, str):
            errors.append(f"{path}: must be a string")
            continue
        if item not in DOC_TYPES:
            errors.append(
                f"{path}: must be one of {list(DOC_TYPES)} (got {item!r})"
            )
            continue
        if item in seen:
            errors.append(f"{path}: duplicate value {item!r}")
            continue
        seen.add(item)
        valid.append(item)
    return valid


def _check_io(data: dict[str, Any], errors: list[str]) -> None:
    if "io" not in data:
        errors.append("io: required")
        return
    io = data["io"]
    if not isinstance(io, dict):
        errors.append("io: must be a JSON object")
        return

    allowed = {"input_dir", "output_dir"}
    for extra in sorted(set(io.keys()) - allowed):
        errors.append(f"io: unknown key '{extra}'")
    for required in ("input_dir", "output_dir"):
        if required not in io:
            errors.append(f"io.{required}: required")
            continue
        v = io[required]
        if not isinstance(v, str) or not v:
            errors.append(f"io.{required}: must be a non-empty string")


# ---------------------------------------------------------------------------
# invoice section
# ---------------------------------------------------------------------------


def _check_invoice_section(
    data: dict[str, Any], doc_types: list[str], errors: list[str]
) -> None:
    has_invoice_type = "invoice" in doc_types
    if not has_invoice_type:
        if "invoice" in data:
            errors.append(
                "invoice: must be absent when 'invoice' is not in doc_types"
            )
        return

    if "invoice" not in data:
        errors.append("invoice: required when 'invoice' is in doc_types")
        return

    invoice = data["invoice"]
    if not isinstance(invoice, dict):
        errors.append("invoice: must be a JSON object")
        return

    allowed = {"tenancy", "extraction", "recipients"}
    for extra in sorted(set(invoice.keys()) - allowed):
        errors.append(f"invoice: unknown key '{extra}'")

    tenancy = invoice.get("tenancy")
    if tenancy is None:
        errors.append("invoice.tenancy: required")
        return
    if tenancy not in TENANCY_MODES:
        errors.append(
            f"invoice.tenancy: must be one of {list(TENANCY_MODES)} "
            f"(got {tenancy!r})"
        )
        return

    if tenancy == "multitenant":
        _check_multitenant(invoice, errors)
    else:
        _check_known_tenancy(invoice, errors)


def _check_multitenant(invoice: dict[str, Any], errors: list[str]) -> None:
    recipients = invoice.get("recipients")
    if recipients not in (None, []):
        errors.append(
            "invoice.recipients: must be absent or empty when "
            "tenancy is 'multitenant'"
        )

    if "extraction" not in invoice:
        errors.append(
            "invoice.extraction: required when tenancy is 'multitenant'"
        )
        return
    _check_extraction(invoice["extraction"], "invoice.extraction", errors)


def _check_known_tenancy(invoice: dict[str, Any], errors: list[str]) -> None:
    if "extraction" in invoice:
        errors.append(
            "invoice.extraction: forbidden when tenancy is 'known' "
            "(declare extraction per recipient instead)"
        )

    recipients = invoice.get("recipients")
    if not isinstance(recipients, list) or not recipients:
        errors.append(
            "invoice.recipients: must be a non-empty array when "
            "tenancy is 'known'"
        )
        return

    seen_ids: set[str] = set()
    for i, recipient in enumerate(recipients):
        path = f"invoice.recipients[{i}]"
        if not isinstance(recipient, dict):
            errors.append(f"{path}: must be a JSON object")
            continue
        rid = _check_recipient(recipient, path, errors)
        if rid is None:
            continue
        if rid in seen_ids:
            errors.append(f"{path}.id: duplicate value {rid!r}")
        seen_ids.add(rid)


def _check_recipient(
    recipient: dict[str, Any], path: str, errors: list[str]
) -> str | None:
    allowed = {"id", "name", "ico", "dic", "extraction"}
    for extra in sorted(set(recipient.keys()) - allowed):
        errors.append(f"{path}: unknown key '{extra}'")

    rid = recipient.get("id")
    if not isinstance(rid, str) or not rid:
        errors.append(f"{path}.id: required, must be non-empty kebab-case string")
        rid = None
    elif not RECIPIENT_ID_PATTERN.match(rid):
        errors.append(
            f"{path}.id: must be kebab-case (lowercase, digits, hyphens) — "
            f"got {rid!r}"
        )
        rid = None

    name = recipient.get("name")
    if not isinstance(name, str) or not name:
        errors.append(f"{path}.name: required, must be a non-empty string")

    ico = recipient.get("ico")
    if not isinstance(ico, str) or not ICO_PATTERN.match(ico):
        errors.append(f"{path}.ico: must be 8 digits")

    if "dic" in recipient:
        dic = recipient["dic"]
        if not isinstance(dic, str) or not DIC_PATTERN.match(dic):
            errors.append(
                f"{path}.dic: must match pattern '^[A-Z]{{2}}[0-9A-Z]+$'"
            )

    if "extraction" not in recipient:
        errors.append(f"{path}.extraction: required")
    else:
        _check_extraction(recipient["extraction"], f"{path}.extraction", errors)

    return rid


def _check_extraction(extraction: Any, path: str, errors: list[str]) -> None:
    if not isinstance(extraction, dict):
        errors.append(f"{path}: must be a JSON object")
        return

    allowed = {"depth", "orders"}
    for extra in sorted(set(extraction.keys()) - allowed):
        errors.append(f"{path}: unknown key '{extra}'")

    depth = extraction.get("depth")
    if depth not in EXTRACTION_DEPTHS:
        errors.append(
            f"{path}.depth: must be one of {list(EXTRACTION_DEPTHS)} "
            f"(got {depth!r})"
        )
        depth = None

    orders = extraction.get("orders")
    if orders is None:
        return
    if depth != "items":
        errors.append(
            f"{path}.orders: only allowed when depth is 'items'"
        )
        return
    _check_orders(orders, f"{path}.orders", errors)


def _check_orders(orders: Any, path: str, errors: list[str]) -> None:
    if not isinstance(orders, dict):
        errors.append(f"{path}: must be a JSON object")
        return

    allowed = {"source", "path"}
    for extra in sorted(set(orders.keys()) - allowed):
        errors.append(f"{path}: unknown key '{extra}'")

    source = orders.get("source")
    if source not in ORDERS_SOURCES:
        errors.append(
            f"{path}.source: must be one of {list(ORDERS_SOURCES)} "
            f"(got {source!r})"
        )

    raw_path = orders.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        errors.append(f"{path}.path: must be a non-empty string")
        return
    if not _is_valid_glob(raw_path):
        errors.append(f"{path}.path: invalid glob syntax")


# ---------------------------------------------------------------------------
# watcher section (optional)
# ---------------------------------------------------------------------------


def _check_watcher_section(data: dict[str, Any], errors: list[str]) -> None:
    if "watcher" not in data:
        return
    watcher = data["watcher"]
    if not isinstance(watcher, dict):
        errors.append("watcher: must be a JSON object")
        return

    allowed = {
        "backend",
        "workers",
        "cooldown_seconds",
        "patterns",
        "recursive",
        "post_process",
        "post_process_options",
    }
    for extra in sorted(set(watcher.keys()) - allowed):
        errors.append(f"watcher: unknown key '{extra}'")

    if "backend" in watcher:
        backend = watcher["backend"]
        if not isinstance(backend, str) or backend not in WATCHER_BACKENDS:
            errors.append(
                f"watcher.backend: must be one of {list(WATCHER_BACKENDS)} "
                f"(got {backend!r})"
            )

    if "workers" in watcher:
        workers = watcher["workers"]
        if not isinstance(workers, int) or isinstance(workers, bool) or workers < 1:
            errors.append(f"watcher.workers: must be a positive integer (got {workers!r})")

    if "cooldown_seconds" in watcher:
        cooldown = watcher["cooldown_seconds"]
        if isinstance(cooldown, bool) or not isinstance(cooldown, (int, float)) or cooldown < 0:
            errors.append(
                f"watcher.cooldown_seconds: must be a non-negative number (got {cooldown!r})"
            )

    if "patterns" in watcher:
        patterns = watcher["patterns"]
        if not isinstance(patterns, list) or not patterns:
            errors.append("watcher.patterns: must be a non-empty array of strings")
        else:
            for i, pat in enumerate(patterns):
                if not isinstance(pat, str) or not pat:
                    errors.append(f"watcher.patterns[{i}]: must be a non-empty string")

    if "recursive" in watcher:
        recursive = watcher["recursive"]
        if not isinstance(recursive, bool):
            errors.append(f"watcher.recursive: must be a boolean (got {recursive!r})")

    _check_watcher_post_process(watcher, errors)


def _check_watcher_post_process(watcher: dict[str, Any], errors: list[str]) -> None:
    """Validate ``watcher.post_process`` + ``watcher.post_process_options``.

    Mirrors the ``$defs`` shape in
    ``docs/schemas/ireco-config-1.0.json``. Added for issue 006 — the
    JSON Schema and this validator MUST stay in sync (this function
    is the missing half of that contract that escaped review).
    """
    if "post_process" in watcher:
        pp = watcher["post_process"]
        if not isinstance(pp, list):
            errors.append("watcher.post_process: must be an array of strings")
        else:
            seen: set[str] = set()
            for i, handler in enumerate(pp):
                path = f"watcher.post_process[{i}]"
                if not isinstance(handler, str):
                    errors.append(f"{path}: must be a string")
                    continue
                if handler not in WATCHER_POST_PROCESS_HANDLERS:
                    errors.append(
                        f"{path}: must be one of "
                        f"{list(WATCHER_POST_PROCESS_HANDLERS)} (got {handler!r})"
                    )
                    continue
                if handler in seen:
                    errors.append(f"{path}: duplicate value {handler!r}")
                    continue
                seen.add(handler)

    if "post_process_options" in watcher:
        ppo = watcher["post_process_options"]
        if not isinstance(ppo, dict):
            errors.append("watcher.post_process_options: must be a JSON object")
            return
        allowed_handlers = set(WATCHER_POST_PROCESS_HANDLERS)
        for key in sorted(set(ppo.keys()) - allowed_handlers):
            errors.append(
                f"watcher.post_process_options: unknown handler '{key}' "
                f"(allowed: {sorted(allowed_handlers)})"
            )
        if "export-isdoc" in ppo:
            _check_export_isdoc_options(
                ppo["export-isdoc"],
                "watcher.post_process_options.export-isdoc",
                errors,
            )


def _check_export_isdoc_options(
    options: Any, path: str, errors: list[str]
) -> None:
    if not isinstance(options, dict):
        errors.append(f"{path}: must be a JSON object")
        return
    allowed = {"format", "profile", "allow_incomplete", "output_dir", "source_pdf"}
    for extra in sorted(set(options.keys()) - allowed):
        errors.append(f"{path}: unknown option '{extra}'")

    if "format" in options:
        fmt = options["format"]
        if not isinstance(fmt, str) or fmt not in EXPORT_ISDOC_FORMATS:
            errors.append(
                f"{path}.format: must be one of {list(EXPORT_ISDOC_FORMATS)} "
                f"(got {fmt!r})"
            )

    if "profile" in options:
        profile = options["profile"]
        if not isinstance(profile, str) or profile not in EXPORT_ISDOC_PROFILES:
            errors.append(
                f"{path}.profile: must be one of {list(EXPORT_ISDOC_PROFILES)} "
                f"(got {profile!r})"
            )

    if "allow_incomplete" in options:
        flag = options["allow_incomplete"]
        if not isinstance(flag, bool):
            errors.append(
                f"{path}.allow_incomplete: must be a boolean (got {flag!r})"
            )

    for key in ("output_dir", "source_pdf"):
        if key in options:
            value = options[key]
            if not isinstance(value, str) or not value:
                errors.append(f"{path}.{key}: must be a non-empty string")


# ---------------------------------------------------------------------------
# models section (optional)
# ---------------------------------------------------------------------------


def _check_models_section(data: dict[str, Any], errors: list[str]) -> None:
    if "models" not in data:
        return
    models = data["models"]
    if not isinstance(models, dict):
        errors.append("models: must be a JSON object")
        return

    allowed = {"path"}
    for extra in sorted(set(models.keys()) - allowed):
        errors.append(f"models: unknown key '{extra}'")

    if "path" in models:
        path = models["path"]
        if not isinstance(path, str) or not path:
            errors.append("models.path: must be a non-empty string")


# ---------------------------------------------------------------------------
# parse section (optional) — issue 007
# ---------------------------------------------------------------------------


def _check_parse_section(data: dict[str, Any], errors: list[str]) -> None:
    if "parse" not in data:
        return
    parse_cfg = data["parse"]
    if not isinstance(parse_cfg, dict):
        errors.append("parse: must be a JSON object")
        return

    allowed = {"ocr"}
    for extra in sorted(set(parse_cfg.keys()) - allowed):
        errors.append(f"parse: unknown key '{extra}'")

    if "ocr" in parse_cfg:
        _check_parse_ocr(parse_cfg["ocr"], "parse.ocr", errors)


def _check_parse_ocr(ocr: Any, path: str, errors: list[str]) -> None:
    if not isinstance(ocr, dict):
        errors.append(f"{path}: must be a JSON object")
        return

    allowed = {"enabled", "language", "dpi", "min_ink_ratio", "mode"}
    for extra in sorted(set(ocr.keys()) - allowed):
        errors.append(f"{path}: unknown key '{extra}'")

    if "enabled" in ocr:
        enabled = ocr["enabled"]
        if not isinstance(enabled, bool):
            errors.append(f"{path}.enabled: must be a boolean (got {enabled!r})")

    if "language" in ocr:
        language = ocr["language"]
        if not isinstance(language, str) or not language:
            errors.append(f"{path}.language: must be a non-empty string")

    if "dpi" in ocr:
        dpi = ocr["dpi"]
        if not isinstance(dpi, int) or isinstance(dpi, bool) or dpi < OCR_MIN_DPI:
            errors.append(f"{path}.dpi: must be an integer >= {OCR_MIN_DPI} (got {dpi!r})")

    if "min_ink_ratio" in ocr:
        ratio = ocr["min_ink_ratio"]
        if (
            isinstance(ratio, bool)
            or not isinstance(ratio, (int, float))
            or not (0.0 <= float(ratio) <= 1.0)
        ):
            errors.append(
                f"{path}.min_ink_ratio: must be a number in [0.0, 1.0] (got {ratio!r})"
            )

    if "mode" in ocr:
        mode = ocr["mode"]
        if not isinstance(mode, str) or mode not in OCR_MODES:
            errors.append(
                f"{path}.mode: must be one of {list(OCR_MODES)} (got {mode!r})"
            )


def _is_valid_glob(pattern: str) -> bool:
    """Cheap syntactic glob check.

    We don't require the matched files to exist (they may be created
    later in the workflow); we only reject patterns that ``fnmatch``
    would reject as malformed.
    """
    if not pattern.strip():
        return False
    # Unmatched character class is the only way ``fnmatch.translate``
    # raises in practice; anything else is a valid (possibly empty) glob.
    import fnmatch

    try:
        fnmatch.translate(pattern)
    except re.error:
        return False
    return True
