from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class ElementType(StrEnum):
    SECTION = "section"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    LIST_ITEM = "list_item"
    TABLE = "table"
    FIGURE = "figure"
    CAPTION = "caption"
    HEADER = "header"
    FOOTER = "footer"
    OTHER = "other"


class BoundingBox(BaseModel):
    left: float
    top: float
    right: float
    bottom: float
    coordinate_origin: str = "bottom-left"

    @model_validator(mode="after")
    def valid_box(self) -> BoundingBox:
        if self.right < self.left or self.top < self.bottom:
            raise ValueError("Invalid bounding box coordinates")
        return self


class Provenance(BaseModel):
    page: int
    bbox: BoundingBox | None = None
    source: str = "docling"
    confidence: float | None = None


class CanonicalElement(BaseModel):
    id: str
    document_id: str
    type: ElementType
    text: str = ""
    reading_order: int
    parent_id: str | None = None
    children_ids: list[str] = Field(default_factory=list)
    heading_level: int | None = None
    provenance: list[Provenance] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class CanonicalDocument(BaseModel):
    id: str
    source_name: str
    source_sha256: str
    page_count: int
    elements: list[CanonicalElement]
    root_ids: list[str] = Field(default_factory=list)


class TableCell(BaseModel):
    text: str = ""
    row: int
    column: int
    row_span: int = 1
    column_span: int = 1
    is_header: bool = False


class ExtractedTable(BaseModel):
    id: str
    document_id: str
    page: int
    method: str
    caption: str | None = None
    bbox: BoundingBox | None = None
    cells: list[TableCell]
    num_rows: int
    num_columns: int
    source_element_id: str
    files: dict[str, Path] = Field(default_factory=dict)


class ImageAsset(BaseModel):
    id: str
    document_id: str
    page: int
    kind: str
    complexity: str
    classification_confidence: float
    classification_reasons: list[str]
    source_element_id: str
    image_path: Path
    metadata_path: Path
    caption: str | None = None
    bbox: BoundingBox | None = None
    ocr_text: str = ""
    ocr_confidence: float | None = None
    image_hash: str = ""
    is_duplicate: bool = False


class ValidationFinding(BaseModel):
    severity: str
    code: str
    message: str
    element_id: str | None = None
    page: int | None = None


class QaReport(BaseModel):
    document_id: str
    passed: bool
    metrics: dict[str, int | float | str | None]
    findings: list[ValidationFinding]
