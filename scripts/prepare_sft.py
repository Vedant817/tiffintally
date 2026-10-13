"""
Prepare ChatML SFT dataset for Tinker fine-tuning (Qwen 2.5 format).
Uses SYSTEM_PROMPT from tiffintally.extract.base with schema aligned to {"events": [...]}.
"""

import json
from pathlib import Path

from tiffintally.extract.base import SYSTEM_PROMPT

INPUT_TRAIN = Path("data/synthetic/train.jsonl")
OUTPUT_SFT = Path("data/synthetic/tinker_sft_train.jsonl")


def build_sft_dataset():
    if not INPUT_TRAIN.exists():
        print(f"Error: {INPUT_TRAIN} not found. Run scripts/gen_synthetic.py first.")
        return

    records = []
    with open(INPUT_TRAIN, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    sft_rows = []
    for r in records:
        sender = r["sender"]
        text = r.get("raw_text") or r.get("text", "")
        gold_data = r["gold"]

        user_content = f"Sender: {sender}\nMessage: {text}"
        assistant_content = json.dumps({"events": [gold_data]}, ensure_ascii=False)

        sft_entry = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.strip()},
                {"role": "user", "content": user_content},
                {"role": "assistant", "content": assistant_content},
            ]
        }
        sft_rows.append(sft_entry)

    OUTPUT_SFT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_SFT, "w", encoding="utf-8") as f:
        for row in sft_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Successfully generated {len(sft_rows)} SFT ChatML records at {OUTPUT_SFT}")


if __name__ == "__main__":
    build_sft_dataset()
