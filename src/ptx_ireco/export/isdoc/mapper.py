"""Walk ``field_map.json`` and build an ISDOC ``lxml`` element tree.

The mapper is **EN 16931 BT/BG-indexed**: each entry in
``field_map.json`` describes one Business Term (or Group of Business
Terms) and its target ISDOC XPath. The mapper does not hard-code
field paths — every path comes from the JSON table.

Differences from the original ADR-0007 sketch:

- Source is the live VIM 1.5 semantic layer, which stores values
  under ``layers.semantic.entities[?type=<entity_type>].fields[<key>]``.
  Each field-map entry therefore carries ``entity_type`` + ``field``
  rather than a single dotted ``semantic_path``. The original
  ``semantic_path`` shape was speculative; this is the actual
  semantic shape produced by the extractor.
- Group-style entries (``BG-*``) own ``children`` describing fields
  inside one repeating element (e.g. ``InvoiceLine``).
- ``literal``-style entries write a fixed string with no semantic
  source (e.g. ``DocumentType`` codes).
"""

from __future__ import annotations

import logging
from typing import Any

from lxml import etree  # type: ignore[import-untyped]

from ptx_ireco.export.isdoc.codes import get_transform
from ptx_ireco.export.isdoc.errors import ExportError, ValidationError
from ptx_ireco.export.isdoc.provenance import ProvenanceAccumulator

logger = logging.getLogger(__name__)


class Mapper:
    """Build an ISDOC element tree from a populated VIM document.

    The mapper is stateless across calls; instances exist only to bind
    a single ``field_map`` + ``profile`` for the duration of one
    export. Reuse a fresh instance per document.
    """

    def __init__(
        self,
        field_map: dict[str, Any],
        *,
        profile: str,
        provenance: ProvenanceAccumulator,
    ) -> None:
        self._field_map = field_map
        self._profile = profile
        self._provenance = provenance
        self._namespace = field_map.get("namespace") or ""
        self._nsmap = {None: self._namespace} if self._namespace else None
        # Transform failures are accumulated here so api.py can fold
        # them into the ValidationReport instead of aborting the
        # export. ``allow_incomplete=False`` then surfaces them as
        # ValidationFailed; ``True`` writes the partial XML and
        # exposes the failures via ExportResult.errors. Without this
        # buffer a single bad value (often from the upstream parser
        # producing label-as-value, e.g. country = "Odběratel:")
        # would sink the whole export.
        self._transform_errors: list[ValidationError] = []

    def build(self, vim_doc: dict[str, Any]) -> etree._Element:
        """Build and return the ``<Invoice>`` root element."""
        entities = self._index_entities(vim_doc)

        root = self._make_element(self._root_tag())
        # ISDOC's <Invoice> has a *required* `version` attribute (not
        # a child element). The XSD's restriction pattern allows
        # MAJOR.MINOR(.PATCH).
        version = self._field_map.get("isdoc_version") or "6.0.2"
        root.set("version", version)

        for entry in self._field_map.get("fields") or []:
            self._emit_entry(root, entry, entities)

        return root

    @property
    def transform_errors(self) -> list[ValidationError]:
        """Transform failures collected during the most recent build().

        Each entry carries ``rule="transform"``, the offending
        XPath, the BT/BG that owned the field, and the raw value
        that failed. The api façade folds these into the
        ValidationReport so ``allow_incomplete`` governs them
        uniformly with the other gates.
        """
        return list(self._transform_errors)

    # ------------------------------------------------------------------
    # Internal — entry handlers
    # ------------------------------------------------------------------

    def _emit_entry(
        self,
        root: etree._Element,
        entry: dict[str, Any],
        entities: dict[str, list[dict[str, Any]]],
    ) -> None:
        if not self._in_profile(entry):
            return

        if "children" in entry:
            self._emit_group(root, entry, entities)
            return
        if "value" in entry:
            self._emit_literal(root, entry)
            return
        self._emit_scalar(root, entry, entities)

    def _emit_scalar(
        self,
        root: etree._Element,
        entry: dict[str, Any],
        entities: dict[str, list[dict[str, Any]]],
    ) -> None:
        xpath = self._require_xpath(entry)
        entity_type = entry.get("entity_type")
        field = entry.get("field")
        if not entity_type or not field:
            raise ExportError(
                f"Field-map entry needs 'entity_type' + 'field' (got {entry!r})"
            )
        instances = entities.get(entity_type) or []
        if not instances:
            return
        # Scalar entries always read from the first matching instance;
        # group-style entries iterate.
        instance = instances[0]
        raw = (instance.get("fields") or {}).get(field)
        if raw in (None, ""):
            return
        try:
            text = self._apply_transform(entry.get("transform"), raw)
        except ExportError as exc:
            self._record_transform_error(entry, raw, exc, xpath=xpath)
            return
        element = self._set_text_at_xpath(root, xpath, text)
        self._record(entry, instance, text, element_xpath=xpath)

    def _emit_group(
        self,
        root: etree._Element,
        entry: dict[str, Any],
        entities: dict[str, list[dict[str, Any]]],
    ) -> None:
        xpath = self._require_xpath(entry)
        entity_type = entry.get("entity_type")
        if not entity_type:
            raise ExportError(f"Group entry needs 'entity_type' (got {entry!r})")
        instances = entities.get(entity_type) or []
        if not instances:
            return
        for instance in instances:
            group_el = self._append_at_xpath(root, xpath)
            for child in entry["children"]:
                if not self._in_profile(child):
                    continue
                if "value" in child:
                    self._emit_child_literal(group_el, child)
                    continue
                child_xpath = child.get("isdoc_xpath")
                child_field = child.get("field")
                if not child_xpath or not child_field:
                    raise ExportError(
                        "Group child needs 'isdoc_xpath' + 'field' "
                        f"(got {child!r})"
                    )
                raw = (instance.get("fields") or {}).get(child_field)
                if raw in (None, ""):
                    continue
                absolute = f"{xpath}/{child_xpath.lstrip('/')}"
                try:
                    text = self._apply_transform(child.get("transform"), raw)
                except ExportError as exc:
                    self._record_transform_error(child, raw, exc, xpath=absolute, parent=entry)
                    continue
                el = self._set_text_at_xpath(group_el, child_xpath, text)
                self._record(child, instance, text, element_xpath=absolute, parent=entry)

    def _emit_literal(self, root: etree._Element, entry: dict[str, Any]) -> None:
        xpath = self._require_xpath(entry)
        text = str(entry["value"])
        self._set_text_at_xpath(root, xpath, text)
        self._provenance.record(
            isdoc_xpath=xpath,
            value=text,
            bt=entry.get("bt"),
            bg=entry.get("bg"),
            source_block=f"computed:literal",
            confidence=None,
        )

    def _emit_child_literal(self, parent_el: etree._Element, entry: dict[str, Any]) -> None:
        xpath = self._require_xpath(entry)
        text = str(entry["value"])
        self._set_text_at_xpath(parent_el, xpath, text)

    # ------------------------------------------------------------------
    # Internal — element-tree plumbing
    # ------------------------------------------------------------------

    def _root_tag(self) -> str:
        return self._field_map.get("root_element") or "Invoice"

    def _qname(self, local: str) -> str:
        if self._namespace:
            return f"{{{self._namespace}}}{local}"
        return local

    def _make_element(self, local: str) -> etree._Element:
        return etree.Element(self._qname(local), nsmap=self._nsmap)

    @staticmethod
    def _split_xpath(xpath: str) -> list[str]:
        parts = [p for p in xpath.split("/") if p]
        if not parts:
            raise ExportError(f"Empty xpath: {xpath!r}")
        return parts

    def _set_text_at_xpath(
        self, root: etree._Element, xpath: str, text: str
    ) -> etree._Element:
        """Walk/create elements along ``xpath`` and set the leaf text.

        Absolute paths (starting with ``/<root>``) are anchored at
        ``root`` (the leading segment must match). Relative paths
        anchor directly at ``root``.
        """
        parts = self._split_xpath(xpath)
        local_root = etree.QName(root).localname
        if parts[0] == local_root:
            parts = parts[1:]
        current = root
        for part in parts:
            child = current.find(self._qname(part))
            if child is None:
                child = etree.SubElement(current, self._qname(part))
            current = child
        current.text = text
        return current

    def _append_at_xpath(self, root: etree._Element, xpath: str) -> etree._Element:
        """Create a new element at ``xpath`` (no merging — for repeating groups)."""
        parts = self._split_xpath(xpath)
        local_root = etree.QName(root).localname
        if parts[0] == local_root:
            parts = parts[1:]
        if not parts:
            raise ExportError(f"Group xpath cannot equal root: {xpath!r}")
        current = root
        for part in parts[:-1]:
            child = current.find(self._qname(part))
            if child is None:
                child = etree.SubElement(current, self._qname(part))
            current = child
        new_el = etree.SubElement(current, self._qname(parts[-1]))
        return new_el

    @staticmethod
    def _require_xpath(entry: dict[str, Any]) -> str:
        xpath = entry.get("isdoc_xpath")
        if not xpath:
            raise ExportError(f"Field-map entry missing 'isdoc_xpath': {entry!r}")
        return str(xpath)

    @staticmethod
    def _apply_transform(name: str | None, raw: Any) -> str:
        if not name:
            return str(raw)
        fn = get_transform(name)
        return fn(raw)

    def _in_profile(self, entry: dict[str, Any]) -> bool:
        # ``emit_in`` (when set) is authoritative — restricts emission
        # to the listed profiles. ``required_in`` doubles as the
        # default emit set: a field listed only in ``standard`` /
        # ``full`` is not emitted in ``minimal`` (this matches issue
        # 006 §B "minimal strips line items"). A field with neither
        # key is emitted in every profile.
        emit_in = entry.get("emit_in")
        if emit_in is not None:
            return self._profile in emit_in
        required_in = entry.get("required_in")
        if required_in is not None:
            return self._profile in required_in
        return True

    @staticmethod
    def _index_entities(vim_doc: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        layers = vim_doc.get("layers") or {}
        semantic = layers.get("semantic") or {}
        out: dict[str, list[dict[str, Any]]] = {}
        for entity in semantic.get("entities") or []:
            etype = entity.get("type")
            if not etype:
                continue
            out.setdefault(etype, []).append(entity)
        return out

    def _record_transform_error(
        self,
        entry: dict[str, Any],
        raw: Any,
        exc: ExportError,
        *,
        xpath: str,
        parent: dict[str, Any] | None = None,
    ) -> None:
        bt = entry.get("bt") or (parent.get("bt") if parent else None)
        bg = parent.get("bg") if parent else entry.get("bg")
        self._transform_errors.append(
            ValidationError(
                rule="transform",
                message=str(exc),
                path=xpath,
                bt=bt or bg,
                value=str(raw),
            )
        )

    def _record(
        self,
        entry: dict[str, Any],
        instance: dict[str, Any],
        value: str,
        *,
        element_xpath: str,
        parent: dict[str, Any] | None = None,
    ) -> None:
        bt = entry.get("bt") or (parent.get("bt") if parent else None)
        bg = parent.get("bg") if parent else entry.get("bg")
        confidence = instance.get("confidence")
        self._provenance.record(
            isdoc_xpath=element_xpath,
            value=value,
            bt=bt,
            bg=bg,
            source_block=instance.get("source_block"),
            source_barcode=instance.get("source_barcode"),
            confidence=confidence if isinstance(confidence, (int, float)) else None,
        )
