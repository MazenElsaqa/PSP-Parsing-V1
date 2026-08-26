from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .ids import document_id, element_id, file_sha256
from .models import BoundingBox, CanonicalDocument, CanonicalElement, ElementType, Provenance

_LABEL_MAP = {
    "section_header": ElementType.HEADING,
    "title": ElementType.HEADING,
    "text": ElementType.PARAGRAPH,
    "paragraph": ElementType.PARAGRAPH,
    "list_item": ElementType.LIST_ITEM,
    "table": ElementType.TABLE,
    "picture": ElementType.FIGURE,
    "caption": ElementType.CAPTION,
    "page_header": ElementType.HEADER,
    "page_footer": ElementType.FOOTER,
}


def _label(item: Any) -> str:
    value = getattr(item, "label", "other")
    return str(getattr(value, "value", value)).lower()


def _text(item: Any) -> str:
    return str(getattr(item, "text", "") or "").strip()


def _provenance(item: Any) -> list[Provenance]:
    output: list[Provenance] = []
    for prov in getattr(item, "prov", []) or []:
        bbox_obj = getattr(prov, "bbox", None)
        bbox = None
        if bbox_obj is not None:
            bbox = BoundingBox(
                left=float(bbox_obj.l),
                top=float(bbox_obj.t),
                right=float(bbox_obj.r),
                bottom=float(bbox_obj.b),
                coordinate_origin=str(getattr(getattr(bbox_obj, "coord_origin", None), "value", "bottom-left")),
            )
        output.append(Provenance(page=int(getattr(prov, "page_no", 1)), bbox=bbox))
    return output


def _heading_level(item: Any, traversal_level: int) -> int | None:
    label = _label(item)
    if label == "title":
        return 1
    if label != "section_header":
        return None
    explicit = getattr(item, "level", None)
    return max(1, int(explicit)) if explicit is not None else max(1, traversal_level)


def normalize_document(document: Any, source: Path, repeated_text_min_pages: int = 3) -> CanonicalDocument:
    doc_id = document_id(source)
    raw_items = list(document.iterate_items())
    text_pages: dict[str, set[int]] = defaultdict(set)
    for item, _ in raw_items:
        text = _text(item)
        for prov in _provenance(item):
            if text:
                text_pages[text].add(prov.page)
    repeated = {text for text, pages in text_pages.items() if len(pages) >= repeated_text_min_pages}

    counters: Counter[tuple[int, str]] = Counter()
    elements: list[CanonicalElement] = []
    heading_stack: list[tuple[int, str]] = []
    for order, (item, traversal_level) in enumerate(raw_items):
        label = _label(item)
        kind = _LABEL_MAP.get(label, ElementType.OTHER)
        text = _text(item)
        prov = _provenance(item)
        page = prov[0].page if prov else 1
        if text in repeated:
            if re.search(r"page\s+\d+", text, re.IGNORECASE):
                kind = ElementType.FOOTER
            elif kind not in {ElementType.HEADER, ElementType.FOOTER}:
                kind = ElementType.HEADER
        short_kind = {ElementType.HEADING: "hdg", ElementType.PARAGRAPH: "txt", ElementType.LIST_ITEM: "lst", ElementType.TABLE: "tbl", ElementType.FIGURE: "img", ElementType.CAPTION: "cap", ElementType.HEADER: "hdr", ElementType.FOOTER: "ftr"}.get(kind, "obj")
        counters[(page, short_kind)] += 1
        current_id = element_id(doc_id, page, short_kind, counters[(page, short_kind)])
        level = _heading_level(item, int(traversal_level))
        parent_id = heading_stack[-1][1] if heading_stack else None
        if kind == ElementType.HEADING and level is not None:
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            parent_id = heading_stack[-1][1] if heading_stack else None
            heading_stack.append((level, current_id))
        elements.append(CanonicalElement(id=current_id, document_id=doc_id, type=kind, text=text, reading_order=order, parent_id=parent_id, heading_level=level, provenance=prov, metadata={"docling_label": label, "traversal_level": traversal_level}))

    by_id = {element.id: element for element in elements}
    for element in elements:
        if element.parent_id in by_id:
            by_id[element.parent_id].children_ids.append(element.id)
    pages = getattr(document, "pages", {})
    return CanonicalDocument(id=doc_id, source_name=source.name, source_sha256=file_sha256(source), page_count=len(pages), elements=elements, root_ids=[element.id for element in elements if element.parent_id is None])
