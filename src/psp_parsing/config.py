from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class OcrConfig(BaseModel):
    enabled: bool = True
    force_full_page: bool = False
    languages: list[str] = Field(default_factory=lambda: ["en"])


class TableConfig(BaseModel):
    mode: Literal["fast", "accurate"] = "accurate"
    do_cell_matching: bool = True


class QaThresholds(BaseModel):
    expected_pages: int | None = 27
    minimum_text_characters: int = 100
    maximum_heading_level_jump: int = 1
    minimum_table_fill_ratio: float = 0.5


class CaptionConfig(BaseModel):
    """AI-generated caption settings for extracted figures/pictures.

    Captions are only generated once per unique image hash; every
    duplicate occurrence of the same image reuses the cached caption
    without an extra model call.
    """

    enabled: bool = False
    model: str = "gpt-4o-mini"
    max_output_tokens: int = 220
    skip_kinds: list[str] = Field(default_factory=lambda: ["logo/icon"])


class PipelineConfig(BaseModel):
    ocr: OcrConfig = Field(default_factory=OcrConfig)
    tables: TableConfig = Field(default_factory=TableConfig)
    qa: QaThresholds = Field(default_factory=QaThresholds)
    captions: CaptionConfig = Field(default_factory=CaptionConfig)
    image_scale: float = 2.0
    generate_page_images: bool = True
    generate_picture_images: bool = True
    repeated_text_min_pages: int = 3

    @classmethod
    def from_yaml(cls, path: Path) -> PipelineConfig:
        with path.open(encoding="utf-8") as stream:
            return cls.model_validate(yaml.safe_load(stream) or {})
