# PSP Parsing V1

Structure-preserving PDF parsing lab built around [Docling](https://docling-project.github.io/docling/). It extracts text, heading hierarchy, lists, tables, images, provenance, and OCR-related content, then validates the result without claiming unmeasured accuracy.

## What this version does

- Preserves every extracted element in a canonical Pydantic schema.
- Keeps page number, bounding box, reading order, parent/children, and heading level.
- Separates repeated headers and footers from body content without deleting raw output.
- Exports tables as canonical JSON plus HTML and CSV previews.
- Exports pictures using page-aware stable IDs and classifies their type and complexity.
- Produces deterministic QA checks, an HTML report, and hierarchy-aware chunks for a later embeddings phase.

## Setup

Python 3.11–3.13 and `uv` are supported.

```bash
uv sync --all-extras
```

The supplied PDF is already local at `data/input/instrumentation-and-control-engineering.pdf`. PDFs and generated artifacts are intentionally ignored by Git.

## Learn in this order

Launch Jupyter with `uv run jupyter lab`, then follow:

1. `01_explore_pdf.ipynb` — inspect pages and raw text before using a model.
2. `02_docling_baseline.ipynb` — run Docling and inspect canonical hierarchy.
3. `03_table_experiments.ipynb` — compare accurate and fast table structure modes.
4. `04_images_and_ocr.ipynb` — review image IDs, classes, complexity, and metadata.
5. `05_qa_and_gold_set.ipynb` — interpret QA and create a manually verified gold set.

## CLI

```bash
# Lightweight inspection; no model download
uv run psp-parse inspect data/input/instrumentation-and-control-engineering.pdf

# Full structure-first baseline
uv run psp-parse baseline data/input/instrumentation-and-control-engineering.pdf \
  --config configs/baseline.yaml

# Compare TableFormer accurate vs fast settings
uv run psp-parse compare-tables data/input/instrumentation-and-control-engineering.pdf

# Re-evaluate an existing canonical result
uv run psp-parse evaluate artifacts/doc_<hash>/document.json

# Complete workflow under an explicit name
uv run psp-parse run-all data/input/instrumentation-and-control-engineering.pdf
```

Run `uv run psp-parse --help` or `uv run psp-parse COMMAND --help` for all options.

## Artifact contract

Each run is written under `artifacts/<document_id>/`:

```text
manifest.json                 versions, config, timing, status, errors
document.json                 canonical document tree
elements.jsonl                one canonical element per line
chunks.jsonl                  section-aware chunks for future embeddings
raw/docling.json              untouched Docling JSON
raw/docling.md                untouched Docling Markdown
raw/conversion.json           conversion diagnostics
tables/index.json             table inventory
tables/*.{json,html,csv}      lossless schema plus review formats
images/index.json             image inventory
images/*.png                  page-aware image files
images/*.json                 classification and provenance sidecars
qa/report.json                machine-readable checks
qa/report.html                human-readable report
```

Canonical IDs look like `doc_<hash>_p016_tbl_001` and `doc_<hash>_p008_img_001`. The hash ties assets to the exact input bytes; page and ordinal make each asset traceable.

## Accuracy, correctly measured

Automatic QA checks page count, unique IDs, parent links, reading order, heading jumps, page provenance, and minimum extracted text. These checks detect structural failures but are not extraction accuracy.

To measure accuracy, copy `configs/gold-sample.example.json`, transcribe representative pages from the PDF, and evaluate text CER/WER, heading attachment, list nesting, reading-order pairs, and table cell structure against that gold data. CSV is only a review format because merged cells cannot be represented safely; JSON is canonical.

## Development

```bash
make test
make lint
make typecheck
```

The next phase should consume `chunks.jsonl`, choose an embedding model, and store vectors with the original document ID, heading path, pages, and element IDs so retrieval remains auditable.
