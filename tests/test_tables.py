from psp_parsing.models import ExtractedTable, TableCell
from psp_parsing.tables import table_quality


def test_table_quality_preserves_spans() -> None:
    table = ExtractedTable(
        id="table",
        document_id="doc",
        page=1,
        method="accurate",
        cells=[
            TableCell(text="Header", row=0, column=0, column_span=2, is_header=True),
            TableCell(text="A", row=1, column=0),
            TableCell(text="B", row=1, column=1),
        ],
        num_rows=2,
        num_columns=2,
        source_element_id="source",
    )
    metrics = table_quality(table)
    assert metrics["fill_ratio"] == 1.0
    assert metrics["spanning_cells"] == 1
    assert metrics["header_cells"] == 1
