"""Exception + dataclass surface for the ISDOC export module."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ExportError(RuntimeError):
    """Raised when an ISDOC export cannot complete.

    Wraps lower-level failures (missing PDF for an isdocx bundle,
    field-map JSON parse error, etc.). Validation failures use
    :class:`ValidationError` instead and are aggregated by the
    validator rather than raised one-by-one.
    """


@dataclass(frozen=True)
class ValidationError:
    """One failing validation rule.

    Attributes:
        rule: Stable identifier for the rule (``required``, ``xsd``,
            ``BR-CO-10``, ``BR-CZ-ICO``, ``round_trip``, …).
        message: Human-readable explanation.
        path: ISDOC XPath the failure relates to (when known).
        bt: EN 16931 Business Term id the failure relates to (when
            known).
        value: The offending value (when relevant — e.g. an invalid
            IČO that failed mod-11).
    """

    rule: str
    message: str
    path: str | None = None
    bt: str | None = None
    value: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"rule": self.rule, "message": self.message}
        if self.path is not None:
            out["path"] = self.path
        if self.bt is not None:
            out["bt"] = self.bt
        if self.value is not None:
            out["value"] = self.value
        return out


@dataclass
class ValidationReport:
    """Aggregate result of running all validation gates.

    Each gate (``required``, ``xsd``, ``business_rules``,
    ``round_trip``) is recorded with ``"pass"`` or ``"fail"``;
    ``errors`` accumulates every individual :class:`ValidationError`
    across all gates so callers see the full picture, not just the
    first failure.
    """

    gates: dict[str, str] = field(default_factory=dict)
    errors: list[ValidationError] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors

    def add_error(self, error: ValidationError) -> None:
        self.errors.append(error)

    def mark_gate(self, gate: str, status: str) -> None:
        self.gates[gate] = status

    def to_dict(self) -> dict[str, Any]:
        return {
            "gates": dict(self.gates),
            "errors": [e.to_dict() for e in self.errors],
        }
