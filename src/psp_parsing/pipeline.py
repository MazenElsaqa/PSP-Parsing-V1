from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import PipelineConfig
from .docling_runner import convert_pdf
from .exporters import write_canonical, write_chunks
from .ids import document_id
from .images import CaptionFn, extract_images
from .normalize import normalize_document
from .qa import validate, write_report
from .tables import extract_tables, table_quality


def _build_caption_fn(config: PipelineConfig) -> CaptionFn | None:
    if not config.captions.enabled:
        return None

    # Imported lazily so this module has no hard dependency on the
    # `openai` package or AI_GATEWAY_API_KEY when captions are disabled.
    from .captioning import generate_caption_for_image

    def caption_fn(image_path: Path, context: dict[str, Any]) -> str:
        return generate_caption_for_image(
            image_path,
            context=context,
            model=config.captions.model,
            max_output_tokens=config.captions.max_output_tokens,
        )

    return caption_fn


def run_pipeline(pdf_path: Path, config_path: Path, output_root: Path) -> Path:
    config = PipelineConfig.from_yaml(config_path)
    doc_id = document_id(pdf_path)
    output_dir = output_root / doc_id
    document, conversion = convert_pdf(pdf_path, config, output_dir / "raw")
    canonical = normalize_document(document, pdf_path, config.repeated_text_min_pages)
    write_canonical(canonical, output_dir)
    write_chunks(canonical, output_dir)
    tables = extract_tables(document, doc_id, output_dir / "tables", config.tables.mode)
    images = extract_images(
        document,
        doc_id,
        output_dir / "images",
        caption_fn=_build_caption_fn(config),
        skip_caption_kinds=set(config.captions.skip_kinds),
    )
    unique_images = [image for image in images if not image.is_duplicate]
    captioned_images = [image for image in unique_images if image.caption]

    report = validate(canonical, config)
    report.metrics["extracted_table_files"] = len(tables)
    report.metrics["extracted_image_files"] = len(images)
    report.metrics["unique_image_files"] = len(unique_images)
    report.metrics["duplicate_image_occurrences"] = len(images) - len(unique_images)
    report.metrics["captioned_images"] = len(captioned_images)
    write_report(report, output_dir / "qa")
    manifest: dict[str, Any] = {
        **conversion,
        "document_id": doc_id,
        "output": str(output_dir),
        "files": {
            "canonical": "document.json",
            "elements": "elements.jsonl",
            "chunks": "chunks.jsonl",
            "qa": "qa/report.html",
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return output_dir


def compare_table_runs(run_dirs: list[Path], output_path: Path) -> list[dict[str, Any]]:
    comparison: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        index = run_dir / "tables" / "index.json"
        if not index.exists():
            continue
        records = json.loads(index.read_text(encoding="utf-8"))
        for record in records:
            from .models import ExtractedTable

            table = ExtractedTable.model_validate(record)
            comparison.append({"run": run_dir.name, "table_id": table.id, **table_quality(table)})
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    return comparison
