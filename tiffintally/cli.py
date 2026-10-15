"""
TiffinTally CLI application.
Commands:
- tiffintally serve: Run the FastAPI web application
- tiffintally parse <file>: Parse WhatsApp export and display prep sheet
- tiffintally export-sft: Export human cook corrections into ChatML SFT training batch
- tiffintally eval: Run honest empirical evaluations and write a run report
"""

from pathlib import Path
from typing import Optional

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="TiffinTally: WhatsApp Tiffin Order Reconciliation & Kitchen Intelligence")
eval_app = typer.Typer(help="Run empirical evaluations and benchmarks")
app.add_typer(eval_app, name="eval")

console = Console()


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Bind host"),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
):
    """Start the TiffinTally web server."""
    console.print(f"[bold green]Starting TiffinTally on http://{host}:{port}[/bold green]")
    uvicorn.run("tiffintally.app:app", host=host, port=port, reload=reload)


@app.command()
def parse(
    file_path: Path = typer.Argument(..., help="Path to WhatsApp chat export (.txt)"),
    date: str = typer.Option("tomorrow", "--date", "-d", help="Target prep date"),
):
    """Parse an exported WhatsApp chat file and generate the prep sheet."""
    from tiffintally.extract.gemma import GemmaExtractor
    from tiffintally.parser import parse_chat_export
    from tiffintally.reconcile import reconcile_orders

    if not file_path.exists():
        console.print(f"[red]Error: File {file_path} not found.[/red]")
        raise typer.Exit(1)

    content = file_path.read_text(encoding="utf-8")
    messages = parse_chat_export(content)
    console.print(f"[green]Parsed {len(messages)} messages from {file_path.name}[/green]")

    extractor = GemmaExtractor()
    all_events = []

    for msg in messages:
        if not msg.is_system and not msg.is_media and msg.text:
            res = extractor.extract_from_text(msg.text, sender=msg.sender)
            all_events.extend(res.events)

    sheet = reconcile_orders(all_events, target_date=date)

    table = Table(title=f"Daily Prep Sheet: {sheet.date}")
    table.add_column("Customer", style="cyan")
    table.add_column("Meal", style="magenta")
    table.add_column("Qty", justify="right", style="green")
    table.add_column("Modifications", style="yellow")

    for label in sheet.packing_labels:
        table.add_row(
            label.customer,
            label.meal,
            str(label.qty),
            ", ".join(label.mods) if label.mods else "-",
        )

    console.print(table)
    console.print(
        f"[bold]Total Thalis to Cook: {sheet.total_thalis}[/bold] (Lunch: {sheet.total_lunch}, Dinner: {sheet.total_dinner})"
    )


@app.command("export-sft")
def export_sft(
    output_path: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSONL path"),
):
    """Export recorded cook corrections into an SFT JSONL training batch."""
    from tiffintally.feedback import ActiveLearningManager

    mgr = ActiveLearningManager()
    count = mgr.export_sft_dataset(output_path=output_path)
    console.print(
        f"[bold green]Exported {count} active learning examples to SFT dataset![/bold green]"
    )


@eval_app.callback(invoke_without_command=True)
def eval_default(ctx: typer.Context):
    """Run the suite when no subcommand is given, so `eval` is never "Missing command"."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(eval_all)


@eval_app.command("all")
def eval_all():
    """Run the eval suite. Writes evals/runs/<ts>/ only. Never touches RESULTS.md."""
    from tiffintally.eval import run_full_evaluation_suite

    console.print("[bold yellow]Running comprehensive TiffinTally evaluations...[/bold yellow]")
    results = run_full_evaluation_suite()
    console.print(
        f"[bold green]Evaluations complete.[/bold green] Run directory: {results['run_dir']}"
    )
    console.print(f"Report: [cyan]{results['report_path']}[/cyan]")
    console.print(
        "[dim]RESULTS.md is hand-written from these runs and is never regenerated here.[/dim]"
    )


if __name__ == "__main__":
    app()
