"""Unit tests for Active Learning and correction feedback flywheel."""

import json

from tiffintally.feedback import ActiveLearningManager, CorrectionEntry


def test_record_and_export_corrections(tmp_path):
    corr_file = tmp_path / "corrections.jsonl"
    sft_export = tmp_path / "sft_train.jsonl"

    mgr = ActiveLearningManager(storage_path=corr_file)

    # Record 2 corrections (one duplicated)
    entry1 = CorrectionEntry(
        customer="Ravi",
        raw_text="kal lunch cancel aunty, team outing",
        corrected_meal="lunch",
        corrected_qty=0,
        corrected_action="cancel",
    )
    entry2 = CorrectionEntry(
        customer="Pooja",
        raw_text="2 nahi 3 thali dinner",
        corrected_meal="dinner",
        corrected_qty=3,
        corrected_action="change",
        special_instructions="no onion",
    )
    # Duplicate of entry1
    entry3 = CorrectionEntry(
        customer="Ravi",
        raw_text="kal lunch cancel aunty, team outing",
        corrected_meal="lunch",
        corrected_qty=0,
        corrected_action="cancel",
    )

    mgr.record_correction(entry1)
    mgr.record_correction(entry2)
    mgr.record_correction(entry3)

    loaded = mgr.load_corrections()
    assert len(loaded) == 3

    # Export deduplicated SFT dataset
    exported_count = mgr.export_sft_dataset(output_path=sft_export)
    assert exported_count == 2
    assert sft_export.exists()

    lines = sft_export.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    # Parse JSON structure of first and second lines
    records = [json.loads(line) for line in lines]
    assert records[0]["messages"][1]["content"] == "kal lunch cancel aunty, team outing"
    assistant_0 = json.loads(records[0]["messages"][2]["content"])
    assert assistant_0["action"] == "cancel"
    assert assistant_0["qty"] == 0

    assert records[1]["messages"][1]["content"] == "2 nahi 3 thali dinner"
    assistant_1 = json.loads(records[1]["messages"][2]["content"])
    assert assistant_1["action"] == "change"
    assert assistant_1["qty"] == 3
    assert assistant_1["special_instructions"] == "no onion"
