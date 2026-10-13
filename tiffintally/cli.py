"""
TiffinTally CLI application.
Commands:
- tiffintally serve: Run the FastAPI web application
- tiffintally parse <file>: Parse WhatsApp export and display prep sheet
- tiffintally forecast: Run TabPFN kitchen forecast
- tiffintally eval: Run honest empirical evaluations
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


@app.command()
def forecast(
    date: Optional[str] = typer.Option(None, "--date", "-d", help="Target date (YYYY-MM-DD)"),
    confirmed: int = typer.Option(40, "--confirmed", "-c", help="Confirmed orders count"),
):
    """Predict plates to cook using TabPFN regression."""
    from tiffintally.forecast import KitchenForecaster

    forecaster = KitchenForecaster()
    res = forecaster.how_many_to_cook(target_date=date, confirmed_count=confirmed)

    console.print(f"[bold cyan]Kitchen Forecast for {res.target_date}[/bold cyan]")
    console.print(f"Confirmed Orders: [green]{res.confirmed_orders}[/green]")
    console.print(
        f"Predicted to Cook: [bold yellow]{res.predicted_to_cook}[/bold yellow] (Buffer: +{res.recommended_buffer})"
    )
    console.print(f"Model: [blue]{res.model_used}[/blue]")
    console.print(f"[dim]{res.explanation}[/dim]")


@eval_app.command("all")
def eval_all():
    """Run all benchmarks: Gemma, Tinker, Held-out Real data, and TabPFN."""
    from tiffintally.eval import run_full_evaluation_suite

    console.print("[bold yellow]Running comprehensive TiffinTally evaluations...[/bold yellow]")
    results = run_full_evaluation_suite()
    console.print("[bold green]Evaluations complete! Summary written to RESULTS.md[/bold green]")
    console.print(f"Run directory: [cyan]evals/runs/{results['run_timestamp']}/[/cyan]")


if __name__ == "__main__":
    app()
