from __future__ import annotations

import json
import platform
import time
from pathlib import Path
from typing import Any

import docling
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling.document_converter import DocumentConverter, PdfFormatOption

from .config import PipelineConfig


def build_converter(config: PipelineConfig) -> DocumentConverter:
    options = PdfPipelineOptions()
    options.do_ocr = config.ocr.enabled
    options.do_table_structure = True
    options.table_structure_options.do_cell_matching = config.tables.do_cell_matching
    options.table_structure_options.mode = (
        TableFormerMode.ACCURATE if config.tables.mode == "accurate" else TableFormerMode.FAST
    )
    options.images_scale = config.image_scale
    options.generate_page_images = config.generate_page_images
    options.generate_picture_images = config.generate_picture_images
    if hasattr(options.ocr_options, "lang"):
        options.ocr_options.lang = config.ocr.languages
    if hasattr(options.ocr_options, "force_full_page_ocr"):
        options.ocr_options.force_full_page_ocr = config.ocr.force_full_page
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )


def convert_pdf(pdf_path: Path, config: PipelineConfig, raw_dir: Path) -> tuple[Any, dict[str, Any]]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    result = build_converter(config).convert(pdf_path)
    elapsed = time.perf_counter() - started
    document = result.document
    (raw_dir / "docling.md").write_text(document.export_to_markdown(), encoding="utf-8")
    document.save_as_json(raw_dir / "docling.json")
    manifest: dict[str, Any] = {
        "source": str(pdf_path),
        "duration_seconds": round(elapsed, 3),
        "docling_version": getattr(docling, "__version__", "unknown"),
        "python_version": platform.python_version(),
        "status": str(getattr(result, "status", "success")),
        "errors": [str(error) for error in getattr(result, "errors", [])],
        "config": config.model_dump(mode="json"),
    }
    (raw_dir / "conversion.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return document, manifest
