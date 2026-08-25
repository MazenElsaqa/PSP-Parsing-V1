PDF ?= data/input/instrumentation-and-control-engineering.pdf
CONFIG ?= configs/baseline.yaml

.PHONY: install inspect baseline tables evaluate test lint typecheck notebook
install:
	uv sync --all-extras
inspect:
	uv run psp-parse inspect $(PDF)
baseline:
	uv run psp-parse baseline $(PDF) --config $(CONFIG)
tables:
	uv run psp-parse compare-tables $(PDF)
evaluate:
	uv run psp-parse evaluate artifacts/$$(uv run python -c "from pathlib import Path; from psp_parsing.ids import document_id; print(document_id(Path('$(PDF)')))")/document.json --config $(CONFIG)
test:
	uv run pytest
lint:
	uv run ruff check .
typecheck:
	uv run mypy
notebook:
	uv run jupyter lab
