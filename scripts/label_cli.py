"""
Interactive labeling CLI for human labeling of real WhatsApp tiffin messages.
Saves labeled gold data to data/private/real_test.jsonl.
"""

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(help="TiffinTally Human Labeling CLI")
console = Console()

OUTPUT_PATH = Path("data/private/real_test.jsonl")


@app.command()
def label(
    input_file: Optional[Path] = typer.Option(
        None, "--input", "-i", help="Path to raw text or jsonl with unlabelled messages"
    ),
):
    """Interactively label WhatsApp messages for the holdout evaluation set."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    existing_count = 0
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            existing_count = sum(1 for line in f if line.strip())

    console.print(
        Panel(
            f"[bold green]TiffinTally Human Labeling CLI[/bold green]\n"
            f"Target: [cyan]{OUTPUT_PATH}[/cyan]\n"
            f"Existing labeled rows: [yellow]{existing_count}[/yellow]\n"
            f"Press Ctrl+C or type 'quit' anytime to save and exit.",
            title="Setup",
        )
    )

    messages_to_label = []
    if input_file and input_file.exists():
        with open(input_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        messages_to_label.append(data.get("text", line.strip()))
                    except json.JSONDecodeError:
                        messages_to_label.append(line.strip())
    else:
        console.print("[dim]No input file specified. Entering interactive entry mode.[/dim]")

    idx = existing_count + 1
    while True:
        try:
            if messages_to_label:
                if not messages_to_label:
                    console.print(
                        "[bold green]All messages from input file completed![/bold green]"
                    )
                    break
                text = messages_to_label.pop(0)
                console.print(f"\n[bold cyan]Message #{idx}:[/bold cyan] [white]{text}[/white]")
            else:
                text = typer.prompt(f"\nEnter message #{idx} (or 'quit')")
                if text.lower() == "quit":
                    break

            sender = typer.prompt("Customer Name", default="Customer")
            meal = typer.prompt("Meal (lunch/dinner/both/unspecified)", default="lunch")
            qty = int(typer.prompt("Quantity", default="1"))
            action = typer.prompt("Action (new/change/cancel/pause/payment/none)", default="new")
            mods_raw = typer.prompt("Mods (comma-separated, or empty)", default="")
            mods = [m.strip() for m in mods_raw.split(",") if m.strip()]

            payment_amount = None
            if action == "payment":
                p_val = typer.prompt("Payment amount in INR", default="0")
                try:
                    payment_amount = float(p_val)
                except ValueError:
                    payment_amount = None

            record = {
                "id": f"real_{idx:03d}",
                "sender": sender,
                "text": text,
                "is_synthetic": False,
                "gold": {
                    "customer": sender,
                    "date": "tomorrow",
                    "meal": meal,
                    "qty": qty,
                    "items": ["thali"] if qty > 0 else [],
                    "mods": mods,
                    "action": action,
                    "payment_amount": payment_amount,
                    "confidence": 1.0,
                },
            }

            with open(OUTPUT_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

            console.print(f"[green]Saved #{idx} to {OUTPUT_PATH}[/green]")
            idx += 1

        except (KeyboardInterrupt, typer.Abort):
            console.print("\n[yellow]Labeling paused. Progress saved.[/yellow]")
            break


if __name__ == "__main__":
    app()
