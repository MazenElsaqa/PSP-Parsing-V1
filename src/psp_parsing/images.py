from __future__ import annotations

import hashlib
import io
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


def _hash_image(image: Image.Image) -> str:
    """Content-hash of the raw PNG bytes, used to detect exact duplicates
    (repeated logos, running headers, flowchart icons, etc.)."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return hashlib.sha256(buffer.getvalue()).hexdigest()


def extract_images(document: Any, document_id: str, output_dir: Path) -> list[ImageAsset]:
    output_dir.mkdir(parents=True, exist_ok=True)
    assets: list[ImageAsset] = []
    page_counts: dict[int, int] = {}
    hash_cache: dict[str, ImageAsset] = {}

    for item in getattr(document, "pictures", []):
        page, bbox = _location(item)
        page_counts[page] = page_counts.get(page, 0) + 1
        occurrence_id = f"{document_id}_p{page:03d}_img_{page_counts[page]:03d}"

        image = item.get_image(document)
        if image is None:
            continue

        image_hash = _hash_image(image)
        cached = hash_cache.get(image_hash)

        if cached is not None:
            # Exact duplicate: reuse the already-saved file, classification,
            # and (later) the generated caption. No new file is written and
            # no classifier/LLM call happens for this occurrence.
            duplicate_asset = cached.model_copy(
                update={
                    "id": occurrence_id,
                    "page": page,
                    "source_element_id": occurrence_id,
                    "bbox": bbox,
                    "ocr_text": str(getattr(item, "text", "") or ""),
                    "is_duplicate": True,
                }
            )
            assets.append(duplicate_asset)
            continue

        base_id = f"{document_id}_img_{image_hash[:12]}"
        temporary_path = output_dir / f"{base_id}.png"
        image.save(temporary_path)
        kind, complexity, confidence, reasons = _classify(temporary_path)
        final_path = output_dir / f"{base_id}_{complexity}.png"
        temporary_path.rename(final_path)
        metadata_path = output_dir / f"{base_id}_{complexity}.json"
        asset = ImageAsset(
            id=occurrence_id,
            document_id=document_id,
            page=page,
            kind=kind,
            complexity=complexity,
            classification_confidence=confidence,
            classification_reasons=reasons,
            source_element_id=occurrence_id,
            image_path=final_path,
            metadata_path=metadata_path,
            bbox=bbox,
            ocr_text=str(getattr(item, "text", "") or ""),
            image_hash=image_hash,
            is_duplicate=False,
        )
        metadata_path.write_text(asset.model_dump_json(indent=2), encoding="utf-8")
        hash_cache[image_hash] = asset
        assets.append(asset)

    unique_count = len(hash_cache)
    (output_dir / "index.json").write_text(
        json.dumps([asset.model_dump(mode="json") for asset in assets], indent=2),
        encoding="utf-8",
    )
    (output_dir / "hashes.json").write_text(
        json.dumps(
            {
                "total_occurrences": len(assets),
                "unique_images": unique_count,
                "duplicate_occurrences": len(assets) - unique_count,
                "hash_to_image_id": {
                    image_hash: cached_asset.id
                    for image_hash, cached_asset in hash_cache.items()
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return assets
