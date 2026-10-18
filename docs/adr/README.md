# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for `portunix-ireco`.

An ADR captures a single architecturally significant decision: the context that
motivated it, the decision itself, and the consequences. ADRs are **immutable** —
to change a decision, write a new ADR that supersedes the old one.

## Format

ADRs follow a lightweight Michael Nygard format:

- **Status** — Proposed / Accepted / Superseded by ADR-NNNN / Deprecated
- **Context** — what forces are at play, what problem we are solving
- **Decision** — what we decided to do
- **Consequences** — positive, negative, and neutral outcomes

## Naming

Files are named `NNNN-short-slug.md` where `NNNN` is a zero-padded sequential
number. Numbers are never reused.

## Index

| ADR  | Title                                                              | Status   |
|------|--------------------------------------------------------------------|----------|
| 0001 | [Invoice profile design](0001-invoice-profile-design.md)           | Accepted |
| 0002 | [Invoice template layer](0002-invoice-template-layer.md)           | Accepted |
| 0003 | [Two-step flexy pipeline](0003-flexy-pipeline-two-step.md)         | Accepted |
| 0004 | [Per-directory `ireco.config.json` schema](0004-ireco-config-schema.md) | Accepted |
| 0005 | [ireco worker/watcher plugin split](0005-ireco-plugin-split.md)    | Accepted (wizard-placement statement superseded in part by ADR-0006; `models.path` default and anchoring superseded in part by [#8](../issues/done/008-models-path-default-and-anchoring.md)) |
| 0006 | [`portunix-ireco` is a runtime; authoring tools live in `portunix-reco-studio`](0006-runtime-only-scope.md) | Accepted |
| 0007 | [ISDOC export for extracted invoices](0007-isdoc-export.md)        | Accepted |
