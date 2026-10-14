"""
Active Learning & Cook Correction Feedback Flywheel.
Records kitchen operator manual corrections and formats them into
supervised fine-tuning (SFT) training pairs for the next LoRA iteration.
"""

import json
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
        """
        out_file = output_path or ACTIVE_SFT_EXPORT
        out_file.parent.mkdir(parents=True, exist_ok=True)

        corrections = self.load_corrections()
        if not corrections:
            return 0

        seen_inputs = set()
        count = 0

        with open(out_file, "w", encoding="utf-8") as out:
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
                        {"role": "assistant", "content": json.dumps(assistant_output, ensure_ascii=False)},
                    ]
                }
                out.write(json.dumps(sft_example, ensure_ascii=False) + "\n")
                count += 1

        return count
