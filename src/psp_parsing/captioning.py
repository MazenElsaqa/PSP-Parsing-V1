"""AI-generated captions for extracted figures/pictures.

Uses the Google Gemini API directly (free tier via a Google AI Studio API
key) with a vision-capable model. Captions are generated once per unique
image hash by the caller (see images.py) -- this module only knows how to
caption a single image file and never decides on its own whether an image
is a duplicate.
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

_SYSTEM_PROMPT = (
    "You caption figures extracted from an engineering (instrumentation & "
    "control) PDF for a retrieval system that feeds an LLM. Be factual and "
    "concrete: name the diagram/chart/photo type, list the key labels, "
    "steps, numbers, or relationships actually visible, and state what "
    "information someone would learn from it. If the image is purely "
    "decorative (a logo, icon, or divider with no informational content), "
    "say so in one short sentence instead of inventing detail. Do not "
    "start with phrases like 'This image shows'. Keep it under 120 words."
)


def _encode_image_base64(image_path: Path) -> str:
    return base64.b64encode(image_path.read_bytes()).decode("ascii")


def _get_api_key() -> str:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Get a free key at "
            "https://aistudio.google.com/apikey and export it as "
            "GEMINI_API_KEY before enabling captions.enabled in the "
            "pipeline config."
        )
    return api_key


def generate_caption_for_image(
    image_path: Path,
    context: dict[str, Any] | None = None,
    model: str = "gemini-2.0-flash",
    max_output_tokens: int = 220,
) -> str:
    """Generate one AI caption for a single (already deduplicated) image.

    `context` may include page number, nearby heading path, or the
    heuristic kind/complexity from `_classify`, and is folded into the
    prompt to help the model ground its description in the document.
    """
    context = context or {}

    hint_lines = []
    if context.get("page") is not None:
        hint_lines.append(f"Page: {context['page']}")
    if context.get("heading_path"):
        hint_lines.append(f"Section: {context['heading_path']}")
    if context.get("kind"):
        hint_lines.append(f"Heuristic type guess: {context['kind']}")
    if context.get("ocr_text"):
        hint_lines.append(f"Nearby/embedded text: {context['ocr_text'][:300]}")

    hints = "\n".join(hint_lines)
    user_text = "Describe this figure." + (f"\n\nContext:\n{hints}" if hints else "")

    try:
        api_key = _get_api_key()
        encoded = _encode_image_base64(image_path)

        url = f"{_GEMINI_BASE_URL}/{model}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": user_text},
                        {"inline_data": {"mime_type": "image/png", "data": encoded}},
                    ],
                }
            ],
            "generationConfig": {"maxOutputTokens": max_output_tokens},
        }

        response = httpx.post(
            url,
            params={"key": api_key},
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()

        candidates = data.get("candidates") or []
        if not candidates:
            return "[caption generation returned no candidates]"

        parts = candidates[0].get("content", {}).get("parts", [])
        caption = "".join(part.get("text", "") for part in parts).strip()
        return caption or "[caption generation returned empty response]"
    except Exception as error:  # noqa: BLE001 - never let captioning crash the pipeline
        logger.warning("Caption generation failed for %s: %s", image_path, error)
        return f"[caption unavailable: {error}]"
