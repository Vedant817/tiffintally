"""Blind human event-set labelling and pre-score holdout freezing. No model calls."""

import hashlib
import json
import random
from pathlib import Path

import typer

from tiffintally.datasets import load_dataset
from tiffintally.model_validation import clean_model_event
from tiffintally.parser import parse_chat_export
from tiffintally.scoring import canonical_mods

app = typer.Typer()


@app.command()
def label(
    input_file: Path = typer.Option(..., "--input"),
    provenance: Path = typer.Option(..., "--provenance"),
    output: Path = typer.Option(Path("data/private/human_label_pool.jsonl"), "--output"),
):
    """Author complete gold event sets blind, before splitting or running models."""
    if output.exists():
        raise typer.BadParameter("Output exists; refusing to overwrite labels")
    if "private" not in output.parts:
        raise typer.BadParameter("Raw human messages must stay under an ignored private path")
    metadata = json.loads(provenance.read_text(encoding="utf-8"))
    raw = input_file.read_text(encoding="utf-8")
    if input_file.suffix == ".jsonl":
        messages = [json.loads(line) for line in raw.splitlines() if line]
    else:
        messages = [
            dict(sender=message.sender, text=message.text, timestamp=message.timestamp.isoformat())
            for message in parse_chat_export(raw)
            if not message.is_media and not message.is_system
        ]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        for index, message in enumerate(messages):
            text = message.get("raw_text") or message.get("text")
            typer.echo(f"{message['sender']}: {text}")
            typer.echo(
                "Enter a JSON list of ALL gold events. Required: date, meal, qty, action. "
                "Use canonical mods, payment_amount, secondary_customer and secondary_qty where applicable. "
                "Do not inspect any model output."
            )
            while True:
                try:
                    gold = json.loads(typer.prompt("Gold events"))
                    if not isinstance(gold, list) or not gold:
                        raise ValueError("Provide an explicit none event for chit-chat")
                    for event in gold:
                        checked = clean_model_event(event)
                        if (
                            checked.get("invalid")
                            or not event.get("date")
                            or canonical_mods(event.get("mods", [])) is None
                        ):
                            raise ValueError(
                                "Invalid fields, missing authored date or noncanonical mods"
                            )
                    break
                except (ValueError, TypeError) as exc:
                    typer.echo(str(exc))
            record = dict(
                id=f"human_{index:05}",
                sender=message["sender"],
                text=text,
                message_timestamp=message.get("timestamp"),
                gold=gold,
                provenance=metadata,
            )
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
    typer.echo("Saved private label pool. Complete independent review before freezing and scoring.")


@app.command()
def freeze(input_file: Path = typer.Option(..., "--input"), dev_count: int = 40, seed: int = 271):
    """Split verified labels before scoring. Refuse any overwrite of the test or freeze."""
    rows = load_dataset(input_file, private=True)
    if not 0 < dev_count < len(rows):
        raise typer.BadParameter("Development count must leave held-out rows")
    directory = input_file.parent
    paths = [
        directory / "real_dev.jsonl",
        directory / "real_test.jsonl",
        directory / "real_test.freeze.json",
    ]
    if any(path.exists() for path in paths):
        raise typer.BadParameter("A split or freeze already exists; refusing to overwrite")
    random.Random(seed).shuffle(rows)
    report = dict(seed=seed, source_sha256=hashlib.sha256(input_file.read_bytes()).hexdigest())
    for path, selected in zip(paths[:2], (rows[:dev_count], rows[dev_count:])):
        content = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in selected)
        path.write_text(content, encoding="utf-8", newline="\n")
        report[path.name] = dict(
            n=len(selected), sha256=hashlib.sha256(content.encode()).hexdigest()
        )
    paths[2].write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    typer.echo("Frozen private development and test splits. Never edit labels after scoring.")


if __name__ == "__main__":
    app()
