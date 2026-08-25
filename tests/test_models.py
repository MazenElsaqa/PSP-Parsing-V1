from pathlib import Path

import pytest

from psp_parsing.ids import document_id, element_id
from psp_parsing.models import BoundingBox, ElementType


def test_document_id_is_stable(tmp_path: Path) -> None:
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"stable content")
    assert document_id(source) == document_id(source)
    assert document_id(source).startswith("doc_")


def test_element_id_is_page_aware() -> None:
    assert element_id("doc_abc", 8, "img", 1) == "doc_abc_p008_img_001"


def test_invalid_bbox_is_rejected() -> None:
    with pytest.raises(ValueError):
        BoundingBox(left=20, right=10, top=100, bottom=0)


def test_element_types_cover_required_structure() -> None:
    required = {"heading", "paragraph", "list_item", "table", "figure", "caption"}
    assert required.issubset({item.value for item in ElementType})
