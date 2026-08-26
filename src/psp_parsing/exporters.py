from __future__ import annotations

import json
from pathlib import Path

from .models import CanonicalDocument


def write_canonical(document: CanonicalDocument, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "document.json").write_text(
        document.model_dump_json(indent=2), encoding="utf-8"
    )
    with (output_dir / "elements.jsonl").open("w", encoding="utf-8") as stream:
        for element in document.elements:
            stream.write(element.model_dump_json() + "\n")


def write_chunks(document: CanonicalDocument, output_dir: Path) -> None:
    headings: dict[str, str] = {
        item.id: item.text for item in document.elements if item.heading_level is not None
    }
    with (output_dir / "chunks.jsonl").open("w", encoding="utf-8") as stream:
        for item in document.elements:
            if not item.text or item.type.value in {"header", "footer", "caption"}:
                continue
            path: list[str] = []
            parent = item.parent_id
            by_id = {element.id: element for element in document.elements}
            while parent:
                if parent in headings:
                    path.append(headings[parent])
                parent = by_id[parent].parent_id if parent in by_id else None
            record = {
                "id": f"chunk_{item.id}",
                "document_id": document.id,
                "text": item.text,
                "heading_path": list(reversed(path)),
                "page": item.provenance[0].page if item.provenance else None,
                "element_ids": [item.id],
                "type": item.type.value,
            }
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
