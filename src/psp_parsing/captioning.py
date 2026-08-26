"""AI-generated captions for extracted figures/pictures.

Uses the Vercel AI Gateway (OpenAI-compatible Chat Completions API) with a
vision-capable model. Captions are generated once per unique image hash by
the caller (see images.py) -- this module only knows how to caption a single
image file and never decides on its own whether an image is a duplicate.
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_AI_GATEWAY_BASE_URL = "https://ai-gateway.vercel.sh/v1"

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


def _build_client() -> Any:
    # Imported lazily so environments that never call the captioner (e.g.
    # unit tests, or PipelineConfig.captions.enabled=False) don't need the
    # `openai` package installed or an API key configured.
    from openai import OpenAI

    api_key = os.environ.get("AI_GATEWAY_API_KEY")
    if not api_key:
        raise RuntimeError(
            "AI_GATEWAY_API_KEY is not set. Add it to the project environment "
            "variables before enabling captions.enabled in the pipeline config."
        )
    return OpenAI(api_key=api_key, base_url=_AI_GATEWAY_BASE_URL)


def generate_caption_for_image(
    image_path: Path,
    context: dict[str, Any] | None = None,
    model: str = "openai/gpt-4o-mini",
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
        client = _build_client()
        encoded = _encode_image_base64(image_path)

        response = client.chat.completions.create(
            model=model,
            max_tokens=max_output_tokens,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{encoded}"
                            },
                        },
                    ],
                },
            ],
        )
        caption = (response.choices[0].message.content or "").strip()
        return caption or "[caption generation returned empty response]"
    except Exception as error:  # noqa: BLE001 - never let captioning crash the pipeline
        logger.warning("Caption generation failed for %s: %s", image_path, error)
        return f"[caption unavailable: {error}]"
