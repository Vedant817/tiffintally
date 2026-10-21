"""
Active Learning & Cook Correction Feedback Flywheel.
Records kitchen operator manual corrections and formats them into
supervised fine-tuning (SFT) training pairs for the next LoRA iteration.
"""

import contextlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel

CORRECTIONS_FILE = Path("data/private/corrections.jsonl")
ACTIVE_SFT_EXPORT = Path("data/sft/active_learning_batch.jsonl")

SYSTEM_PROMPT = """You are TiffinTally, an AI kitchen assistant. Given a raw WhatsApp order message, extract a JSON object with:
- customer: string
- meal: "lunch", "dinner", or "both"
- qty: integer (0 if canceled)
- action: "new", "change", or "cancel"
- date: "today", "tomorrow", or "date_str"
- special_instructions: optional string
Output only the JSON object."""


class CorrectionEntry(BaseModel):
    customer: str
    raw_text: str
    corrected_meal: str
    corrected_qty: int
    corrected_action: str
    special_instructions: Optional[str] = None
    timestamp: Optional[str] = None


class ActiveLearningManager:
    def __init__(self, storage_path: Path = CORRECTIONS_FILE):
        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def record_correction(self, entry: CorrectionEntry) -> dict:
        """Record a human cook's correction to the private corrections log."""
        if not entry.timestamp:
            entry.timestamp = datetime.now().isoformat()

        record = entry.model_dump()
        with open(self.storage_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return record

    def load_corrections(self) -> List[CorrectionEntry]:
        """Load all recorded corrections."""
        if not self.storage_path.exists():
            return []

        entries = []
        with open(self.storage_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entries.append(CorrectionEntry(**data))
                except Exception:
                    continue
        return entries

    def export_sft_dataset(self, output_path: Optional[Path] = None) -> int:
        """
        Convert recorded corrections into SFT ChatML training examples.
        Returns count of exported examples.

        The batch is written to a temp file in the output directory and renamed
        once complete, so a half-written export never replaces a good one.
        """
        return write_sft_dataset(self.load_corrections(), output_path or ACTIVE_SFT_EXPORT)


def write_sft_dataset(corrections: List[CorrectionEntry], out_file: Path) -> int:
    """
    Write SFT ChatML training examples for these corrections.
    Returns the number of exported examples.

    Duplicate (customer, raw_text) pairs within and across batches export once:
    a correction reorder or re-collection must not duplicate training rows.
    The batch is written to a temp file in the output directory and renamed
    once complete, so a half-written export never replaces a good one.
    """
    out_file.parent.mkdir(parents=True, exist_ok=True)

    if not corrections:
        return 0

    seen_inputs = set()
    count = 0

    tmp_path: Optional[Path] = None
    try:
        fd, tmp_name = tempfile.mkstemp(dir=out_file.parent, prefix=out_file.name, suffix=".tmp")
        tmp_path = Path(tmp_name)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            for c in corrections:
                key = (c.customer.lower(), c.raw_text.strip().lower())
                if key in seen_inputs:
                    continue
                seen_inputs.add(key)

                assistant_output = {
                    "customer": c.customer,
                    "meal": c.corrected_meal,
                    "qty": c.corrected_qty,
                    "action": c.corrected_action,
                    "date": "tomorrow",
                    "special_instructions": c.special_instructions,
                }

                sft_example = {
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": c.raw_text},
                        {
                            "role": "assistant",
                            "content": json.dumps(assistant_output, ensure_ascii=False),
                        },
                    ]
                }
                out.write(json.dumps(sft_example, ensure_ascii=False) + "\n")
                count += 1
        os.replace(tmp_path, out_file)
        # the file is now out_file; the cleanup below must not touch it
        tmp_path = None
    finally:
        if tmp_path is not None:
            with contextlib.suppress(OSError):
                tmp_path.unlink()

    return count
