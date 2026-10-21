"""CLI contract tests: `tiffintally export-sft` reads the durable correction store."""

import json

from typer.testing import CliRunner

from tiffintally.cli import app
from tiffintally.db import get_connection, init_db, persist_correction

runner = CliRunner()


def _persist_two(db_path):
    """Record one correction each for two kitchens into the SQLite store."""
    persist_correction(
        kitchen_id="kitchen_a",
        customer="Ravi",
        raw_text="kal lunch 2 nahi 3",
        corrected_meal="lunch",
        corrected_qty=3,
        corrected_action="change",
        db_path=db_path,
    )
    persist_correction(
        kitchen_id="kitchen_b",
        customer="Neha",
        raw_text="dinner cancel aunty",
        corrected_meal="dinner",
        corrected_qty=0,
        corrected_action="cancel",
        db_path=db_path,
    )


def test_export_sft_reads_the_sqlite_store(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TIFFINTALLY_DEMO_MODE", raising=False)
    monkeypatch.setenv("TIFFINTALLY_PERSIST", "1")
    db_path = tmp_path / "kitchens.db"
    monkeypatch.setenv("TIFFINTALLY_DB_PATH", str(db_path))
    init_db(db_path)

    # the web app's write path: corrections land in SQLite, one per kitchen
    _persist_two(db_path)
    with get_connection(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) c FROM corrections").fetchone()["c"] == 2

    out = tmp_path / "batch.jsonl"
    result = runner.invoke(app, ["export-sft", "--output", str(out)])
    assert result.exit_code == 0
    assert "Exported 2" in result.output

    records = [json.loads(line) for line in out.read_text(encoding="utf-8").strip().splitlines()]
    user_texts = {r["messages"][1]["content"] for r in records}
    assert user_texts == {"kal lunch 2 nahi 3", "dinner cancel aunty"}


def test_export_sft_still_reads_the_legacy_shared_file(tmp_path, monkeypatch):
    """Corrections recorded by older builds live in one shared JSONL; they still export."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TIFFINTALLY_PERSIST", raising=False)
    monkeypatch.delenv("TIFFINTALLY_DEMO_MODE", raising=False)

    legacy = tmp_path / "data" / "private" / "corrections.jsonl"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(
        json.dumps(
            {
                "customer": "C009",
                "raw_text": "kal lunch 9",
                "corrected_meal": "lunch",
                "corrected_qty": 9,
                "corrected_action": "new",
                "timestamp": "2026-10-01T10:00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out = tmp_path / "batch.jsonl"
    result = runner.invoke(app, ["export-sft", "--output", str(out)])
    assert result.exit_code == 0
    assert "Exported 1" in result.output
    assert (
        json.loads(out.read_text(encoding="utf-8").strip())["messages"][1]["content"]
        == "kal lunch 9"
    )
    # with persistence off, the export must not conjure a database to read
    assert not (tmp_path / "data" / "tiffintally.db").exists()


def test_export_sft_combines_sqlite_and_legacy_without_duplication(tmp_path, monkeypatch):
    """The same correction recorded in both stores exports once, not twice."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TIFFINTALLY_DEMO_MODE", raising=False)
    monkeypatch.setenv("TIFFINTALLY_PERSIST", "1")
    db_path = tmp_path / "kitchens.db"
    monkeypatch.setenv("TIFFINTALLY_DB_PATH", str(db_path))
    init_db(db_path)

    _persist_two(db_path)
    with get_connection(db_path) as conn:
        stored = conn.execute("SELECT customer, raw_text FROM corrections").fetchone()

    # an old leftover file that also holds the same pair plus one extra correction
    legacy = tmp_path / "data" / "private" / "corrections.jsonl"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(
        json.dumps(
            {
                "customer": stored["customer"],
                "raw_text": stored["raw_text"],
                "corrected_meal": "lunch",
                "corrected_qty": 3,
                "corrected_action": "change",
            }
        )
        + "\n"
        + json.dumps(
            {
                "customer": "C010",
                "raw_text": "only legacy row",
                "corrected_meal": "dinner",
                "corrected_qty": 1,
                "corrected_action": "new",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out = tmp_path / "batch.jsonl"
    result = runner.invoke(app, ["export-sft", "--output", str(out)])
    assert result.exit_code == 0
    # two SQLite rows, one overlapping the legacy file, one legacy-only: 3 unique pairs
    records = [json.loads(line) for line in out.read_text(encoding="utf-8").strip().splitlines()]
    assert "Exported 3" in result.output
    user_texts = {r["messages"][1]["content"] for r in records}
    assert "only legacy row" in user_texts and len(user_texts) == 3
    # every kitchen's correction is in the training batch, which is the CLI's
    # explicit job: the per-kitchen web export is the one that must stay separate
    assert any("kal lunch 2 nahi 3" in text for text in user_texts)
