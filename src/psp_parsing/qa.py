from __future__ import annotations

import html
from collections import Counter
from pathlib import Path

from .config import PipelineConfig
from .models import CanonicalDocument, QaReport, ValidationFinding


def validate(document: CanonicalDocument, config: PipelineConfig) -> QaReport:
    findings: list[ValidationFinding] = []
    ids = [item.id for item in document.elements]
    counts = Counter(ids)
    for duplicate, count in counts.items():
        if count > 1:
            findings.append(ValidationFinding(severity="error", code="duplicate_id", message=f"ID occurs {count} times", element_id=duplicate))
    known = set(ids)
    previous_order = -1
    headings = [item for item in document.elements if item.heading_level is not None]
    previous_level: int | None = None
    for item in document.elements:
        page = item.provenance[0].page if item.provenance else None
        if item.parent_id and item.parent_id not in known:
            findings.append(ValidationFinding(severity="error", code="missing_parent", message="Parent reference does not exist", element_id=item.id, page=page))
        if item.reading_order <= previous_order:
            findings.append(ValidationFinding(severity="error", code="reading_order", message="Reading order is not strictly increasing", element_id=item.id, page=page))
        previous_order = item.reading_order
        for prov in item.provenance:
            if not 1 <= prov.page <= document.page_count:
                findings.append(ValidationFinding(severity="error", code="page_range", message="Element points outside the document", element_id=item.id, page=prov.page))
        if item.heading_level is not None:
            if previous_level is not None and item.heading_level - previous_level > config.qa.maximum_heading_level_jump:
                findings.append(ValidationFinding(severity="warning", code="heading_jump", message=f"Heading jumps from H{previous_level} to H{item.heading_level}", element_id=item.id, page=page))
            previous_level = item.heading_level
    if config.qa.expected_pages is not None and document.page_count != config.qa.expected_pages:
        findings.append(ValidationFinding(severity="error", code="page_count", message=f"Expected {config.qa.expected_pages} pages, got {document.page_count}"))
    text_characters = sum(len(item.text) for item in document.elements)
    if text_characters < config.qa.minimum_text_characters:
        findings.append(ValidationFinding(severity="error", code="low_text", message=f"Only {text_characters} text characters extracted"))
    metrics: dict[str, int | float | str | None] = {
        "pages": document.page_count,
        "elements": len(document.elements),
        "text_characters": text_characters,
        "headings": len(headings),
        "tables": sum(item.type.value == "table" for item in document.elements),
        "figures": sum(item.type.value == "figure" for item in document.elements),
        "lists": sum(item.type.value == "list_item" for item in document.elements),
        "errors": sum(item.severity == "error" for item in findings),
        "warnings": sum(item.severity == "warning" for item in findings),
    }
    return QaReport(document_id=document.id, passed=metrics["errors"] == 0, metrics=metrics, findings=findings)


def write_report(report: QaReport, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    metric_rows = "".join(f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(str(value))}</td></tr>" for key, value in report.metrics.items())
    finding_rows = "".join(f"<tr><td>{html.escape(item.severity)}</td><td>{html.escape(item.code)}</td><td>{html.escape(item.message)}</td><td>{html.escape(str(item.page or ''))}</td></tr>" for item in report.findings) or '<tr><td colspan="4">No findings</td></tr>'
    page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>Parsing QA</title><style>body{{font:16px system-ui;max-width:1100px;margin:40px auto;padding:0 20px;color:#18212f}}table{{border-collapse:collapse;width:100%;margin:16px 0 32px}}th,td{{border:1px solid #ccd3dc;padding:10px;text-align:left}}th{{background:#edf2f7}}.pass{{color:#087f5b}}.fail{{color:#c92a2a}}</style><body><h1>Document parsing QA</h1><p class="{'pass' if report.passed else 'fail'}"><strong>{'PASS' if report.passed else 'FAIL'}</strong> — {html.escape(report.document_id)}</p><h2>Metrics</h2><table>{metric_rows}</table><h2>Findings</h2><table><tr><th>Severity</th><th>Code</th><th>Message</th><th>Page</th></tr>{finding_rows}</table></body></html>"""
    (output_dir / "report.html").write_text(page, encoding="utf-8")
