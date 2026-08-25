from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFilter

from .models import BoundingBox, ImageAsset


def _classify(image_path: Path) -> tuple[str, str, float, list[str]]:
    with Image.open(image_path) as source:
        rgb = source.convert("RGB")
        gray = rgb.convert("L")
        edges = np.asarray(gray.filter(ImageFilter.FIND_EDGES), dtype=np.uint8)
        edge_density = float(np.count_nonzero(edges > 40) / edges.size)
        sampled = np.asarray(rgb.resize((min(256, rgb.width), min(256, rgb.height))))
        color_count = len(np.unique(sampled.reshape(-1, 3), axis=0))
        width, height = rgb.size
    reasons = [f"edge_density={edge_density:.3f}", f"sampled_colors={color_count}"]
    if edge_density > 0.22 and color_count < 3000:
        kind = "diagram/schematic"
    elif color_count > 5000 and edge_density > 0.08:
        kind = "photo"
    elif height < 200 and width < 400:
        kind = "logo/icon"
    elif edge_density > 0.14:
        kind = "chart"
    else:
        kind = "unknown"
    complexity = "complex" if edge_density > 0.16 or color_count > 7000 else "simple"
    confidence = min(0.95, 0.5 + abs(edge_density - 0.1) + min(color_count, 8000) / 40000)
    return kind, complexity, round(confidence, 3), reasons


def _location(item: Any) -> tuple[int, BoundingBox | None]:
    prov = (getattr(item, "prov", None) or [None])[0]
    if prov is None:
        return 1, None
    raw = getattr(prov, "bbox", None)
    bbox = None if raw is None else BoundingBox(
        left=float(raw.l), top=float(raw.t), right=float(raw.r), bottom=float(raw.b),
        coordinate_origin=str(getattr(getattr(raw, "coord_origin", None), "value", "bottom-left")),
    )
    return int(getattr(prov, "page_no", 1)), bbox


def extract_images(document: Any, document_id: str, output_dir: Path) -> list[ImageAsset]:
    output_dir.mkdir(parents=True, exist_ok=True)
    assets: list[ImageAsset] = []
    page_counts: dict[int, int] = {}
    for item in getattr(document, "pictures", []):
        page, bbox = _location(item)
        page_counts[page] = page_counts.get(page, 0) + 1
        base_id = f"{document_id}_p{page:03d}_img_{page_counts[page]:03d}"
        temporary_path = output_dir / f"{base_id}.png"
        image = item.get_image(document)
        if image is None:
            continue
        image.save(temporary_path)
        kind, complexity, confidence, reasons = _classify(temporary_path)
        final_path = output_dir / f"{base_id}_{complexity}.png"
        temporary_path.rename(final_path)
        metadata_path = output_dir / f"{base_id}_{complexity}.json"
        asset = ImageAsset(
            id=base_id,
            document_id=document_id,
            page=page,
            kind=kind,
            complexity=complexity,
            classification_confidence=confidence,
            classification_reasons=reasons,
            source_element_id=base_id,
            image_path=final_path,
            metadata_path=metadata_path,
            bbox=bbox,
            ocr_text=str(getattr(item, "text", "") or ""),
        )
        metadata_path.write_text(asset.model_dump_json(indent=2), encoding="utf-8")
        assets.append(asset)
    (output_dir / "index.json").write_text(
        json.dumps([asset.model_dump(mode="json") for asset in assets], indent=2),
        encoding="utf-8",
    )
    return assets
