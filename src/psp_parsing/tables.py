from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import BoundingBox, ExtractedTable, TableCell


def _page_and_bbox(item: Any) -> tuple[int, BoundingBox | None]:
    prov = (getattr(item, "prov", None) or [None])[0]
    if prov is None:
        return 1, None
    raw = getattr(prov, "bbox", None)
    bbox = None
    if raw is not None:
        bbox = BoundingBox(
            left=float(raw.l),
            top=float(raw.t),
            right=float(raw.r),
            bottom=float(raw.b),
            coordinate_origin=str(
                getattr(getattr(raw, "coord_origin", None), "value", "bottom-left")
            ),
        )
    return int(getattr(prov, "page_no", 1)), bbox


def extract_tables(document: Any, document_id: str, output_dir: Path, method: str) -> list[ExtractedTable]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tables: list[ExtractedTable] = []
    page_counts: dict[int, int] = {}
    for item in getattr(document, "tables", []):
        page, bbox = _page_and_bbox(item)
        page_counts[page] = page_counts.get(page, 0) + 1
        table_id = f"{document_id}_p{page:03d}_tbl_{page_counts[page]:03d}"
        data = getattr(item, "data", None)
        cells: list[TableCell] = []
        for cell in getattr(data, "table_cells", []) or []:
            row_start = int(getattr(cell, "start_row_offset_idx", 0))
            row_end = int(getattr(cell, "end_row_offset_idx", row_start + 1))
            col_start = int(getattr(cell, "start_col_offset_idx", 0))
            col_end = int(getattr(cell, "end_col_offset_idx", col_start + 1))
            cells.append(
                TableCell(
                    text=str(getattr(cell, "text", "")),
                    row=row_start,
                    column=col_start,
                    row_span=max(1, row_end - row_start),
                    column_span=max(1, col_end - col_start),
                    is_header=bool(
                        getattr(cell, "column_header", False)
                        or getattr(cell, "row_header", False)
                    ),
                )
            )
        rows = int(getattr(data, "num_rows", 0) or 0)
        columns = int(getattr(data, "num_cols", 0) or 0)
        result = ExtractedTable(
            id=table_id,
            document_id=document_id,
            page=page,
            method=method,
            bbox=bbox,
            cells=cells,
            num_rows=rows,
            num_columns=columns,
            source_element_id=table_id,
        )
        json_path = output_dir / f"{table_id}.json"
        html_path = output_dir / f"{table_id}.html"
        csv_path = output_dir / f"{table_id}.csv"
        json_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        frame = item.export_to_dataframe(doc=document)
        html_path.write_text(frame.to_html(index=False), encoding="utf-8")
        frame.to_csv(csv_path, index=False)
        result.files = {"json": json_path, "html": html_path, "csv": csv_path}
        tables.append(result)
    (output_dir / "index.json").write_text(
        json.dumps([table.model_dump(mode="json") for table in tables], indent=2),
        encoding="utf-8",
    )
    return tables


def table_quality(table: ExtractedTable) -> dict[str, float | int]:
    slots = max(1, table.num_rows * table.num_columns)
    occupied = sum(cell.row_span * cell.column_span for cell in table.cells if cell.text.strip())
    return {
        "rows": table.num_rows,
        "columns": table.num_columns,
        "cells": len(table.cells),
        "fill_ratio": round(min(1.0, occupied / slots), 4),
        "header_cells": sum(cell.is_header for cell in table.cells),
        "spanning_cells": sum(
            cell.row_span > 1 or cell.column_span > 1 for cell in table.cells
        ),
    }
