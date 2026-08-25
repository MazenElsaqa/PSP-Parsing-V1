from psp_parsing.config import PipelineConfig, QaThresholds
from psp_parsing.models import CanonicalDocument, CanonicalElement, ElementType
from psp_parsing.qa import validate


def test_qa_catches_missing_parent() -> None:
    document = CanonicalDocument(
        id="doc_test",
        source_name="test.pdf",
        source_sha256="0" * 64,
        page_count=1,
        elements=[
            CanonicalElement(
                id="item_1",
                document_id="doc_test",
                type=ElementType.PARAGRAPH,
                text="Enough content for the configured minimum.",
                reading_order=0,
                parent_id="missing",
            )
        ],
    )
    config = PipelineConfig(qa=QaThresholds(expected_pages=1, minimum_text_characters=1))
    report = validate(document, config)
    assert not report.passed
    assert "missing_parent" in {finding.code for finding in report.findings}


def test_qa_accepts_minimal_valid_document() -> None:
    document = CanonicalDocument(
        id="doc_test",
        source_name="test.pdf",
        source_sha256="0" * 64,
        page_count=1,
        elements=[CanonicalElement(id="item_1", document_id="doc_test", type=ElementType.PARAGRAPH, text="valid", reading_order=0)],
    )
    config = PipelineConfig(qa=QaThresholds(expected_pages=1, minimum_text_characters=1))
    assert validate(document, config).passed
