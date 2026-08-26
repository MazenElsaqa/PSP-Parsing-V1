from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .config import PipelineConfig
from .ids import document_id
from .models import CanonicalDocument
from .pipeline import compare_table_runs, run_pipeline
from .qa import validate, write_report

app = typer.Typer(help="Structure-preserving PDF parsing experiments with Docling.")
console = Console()
DEFAULT_CONFIG = Path("configs/baseline.yaml")
DEFAULT_OUTPUT = Path("artifacts")


def _run(pdf: Path, config: Path, output: Path) -> Path:
    if not pdf.is_file():
        raise typer.BadParameter(f"PDF not found: {pdf}")
    result = run_pipeline(pdf.resolve(), config.resolve(), output.resolve())
    console.print(f"[bold green]Completed[/]: {result}")
    return result


@app.command()
def inspect(pdf: Annotated[Path, typer.Argument(help="PDF to inspect")]) -> None:
    """Print source identity without running models."""
    from pypdfium2 import PdfDocument

    source = PdfDocument(pdf)
    table = Table(title="PDF inspection")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("File", str(pdf))
    table.add_row("Document ID", document_id(pdf))
    table.add_row("Pages", str(len(source)))
    table.add_row("Size", f"{pdf.stat().st_size:,} bytes")
    console.print(table)


@app.command()
def baseline(
    pdf: Annotated[Path, typer.Argument()],
    config: Annotated[Path, typer.Option()] = DEFAULT_CONFIG,
    output: Annotated[Path, typer.Option()] = DEFAULT_OUTPUT,
) -> None:
    """Run the reproducible Docling baseline."""
    _run(pdf, config, output)


@app.command("extract-images")
def extract_images_command(
    pdf: Annotated[Path, typer.Argument()],
    config: Annotated[Path, typer.Option()] = DEFAULT_CONFIG,
    output: Annotated[Path, typer.Option()] = DEFAULT_OUTPUT,
) -> None:
    """Run parsing and show the image artifact directory."""
    result = _run(pdf, config, output)
    console.print(result / "images")


@app.command("compare-tables")
def compare_tables_command(
    pdf: Annotated[Path, typer.Argument()],
    configs: Annotated[list[Path] | None, typer.Option("--config")] = None,
    output: Annotated[Path, typer.Option()] = DEFAULT_OUTPUT,
) -> None:
    """Run multiple configs and emit structural table metrics."""
    selected = configs or [Path("configs/baseline.yaml"), Path("configs/tables-fast.yaml")]
    runs: list[Path] = []
    for config in selected:
        run_root = output / "experiments" / config.stem
        runs.append(_run(pdf, config, run_root))
    result = output / "experiments" / "table-comparison.json"
    rows = compare_table_runs(runs, result)
    console.print(f"Compared {len(rows)} table results: {result}")


@app.command()
def evaluate(
    document_json: Annotated[Path, typer.Argument()],
    config: Annotated[Path, typer.Option()] = DEFAULT_CONFIG,
) -> None:
    """Re-run deterministic QA over an existing canonical document."""
    document = CanonicalDocument.model_validate_json(document_json.read_text(encoding="utf-8"))
    report = validate(document, PipelineConfig.from_yaml(config))
    destination = document_json.parent / "qa"
    write_report(report, destination)
    console.print(json.dumps(report.metrics, indent=2))
    raise typer.Exit(code=0 if report.passed else 1)


@app.command("run-all")
def run_all(
    pdf: Annotated[Path, typer.Argument()],
    config: Annotated[Path, typer.Option()] = DEFAULT_CONFIG,
    output: Annotated[Path, typer.Option()] = DEFAULT_OUTPUT,
) -> None:
    """Run baseline, normalization, tables, images, chunks, and QA."""
    _run(pdf, config, output)


if __name__ == "__main__":
    app()
