"""
TiffinTally: Distributed SLM Fine-Tuning & Evaluation on Modal GPU.
Uses Qwen/Qwen2.5-0.5B-Instruct + LoRA with PyTorch 2.4 SDPA on NVIDIA A10G.
Supports iterative improvement loops with persistent Volume caching.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

import modal

app = modal.App("tiffintally-finetune")
volume = modal.Volume.from_name("tiffintally-models", create_if_missing=True)

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "torch>=2.4.0",
    "transformers==4.46.3",
    "peft==0.13.2",
    "accelerate>=0.34.0",
    "datasets>=3.0.0",
    "bitsandbytes>=0.43.0",
    "scikit-learn>=1.5.0",
    "pydantic>=2.0.0",
)


@app.function(
    image=image,
    gpu="A10G",
    timeout=600,
    volumes={"/vol": volume},
)
def run_finetune_job(
    train_records: List[Dict[str, Any]],
    val_records: List[Dict[str, Any]],
    test_edge_cases: List[Dict[str, Any]],
    hyperparams: Dict[str, Any],
) -> Dict[str, Any]:
    import os
    import time

    import numpy as np
    import torch
    from datasets import Dataset
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForSeq2Seq,
        Trainer,
        TrainingArguments,
    )

    iteration = hyperparams.get("iteration", 4)
    base_model_name = hyperparams.get("base_model_name", "Qwen/Qwen2.5-0.5B-Instruct")
    num_epochs = hyperparams.get("num_epochs", 2)
    lr = hyperparams.get("learning_rate", 1.5e-4)
    lora_r = hyperparams.get("lora_r", 16)
    lora_alpha = hyperparams.get("lora_alpha", 32)
    lora_dropout = hyperparams.get("lora_dropout", 0.05)
    batch_size = hyperparams.get("batch_size", 4)
    grad_accum = hyperparams.get("grad_accum", 4)
    max_seq_len = hyperparams.get("max_seq_len", 768)

    print("\n=======================================================")
    print(f"🚀 Starting TiffinTally Iteration {iteration} on Modal (A10G GPU)")
    print(f"Base Model: {base_model_name} | Epochs: {num_epochs} | LR: {lr}")
    print(
        f"LoRA: r={lora_r}, alpha={lora_alpha} | Train size: {len(train_records)} | Val size: {len(val_records)}"
    )
    print("=======================================================\n")

    tokenizer = AutoTokenizer.from_pretrained(base_model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 1. Format ChatML dataset with label masking (only train on assistant tokens)
    train_dataset = Dataset.from_list(train_records)

    def tokenize_fn(examples):
        input_ids_list = []
        attention_mask_list = []
        labels_list = []

        for messages in examples["messages"]:
            prompt_messages = [m for m in messages if m["role"] in ("system", "user")]
            prompt_text = tokenizer.apply_chat_template(
                prompt_messages, tokenize=False, add_generation_prompt=True
            )
            full_text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=False
            )

            prompt_tokenized = tokenizer(
                prompt_text,
                truncation=True,
                max_length=max_seq_len,
                add_special_tokens=False,
            )
            full_tokenized = tokenizer(
                full_text,
                truncation=True,
                max_length=max_seq_len,
                add_special_tokens=False,
            )

            prompt_len = len(prompt_tokenized["input_ids"])
            full_ids = full_tokenized["input_ids"]
            full_mask = full_tokenized["attention_mask"]

            labels = [-100] * prompt_len + full_ids[prompt_len:]
            active_labels = [token_id for token_id in labels if token_id != -100]
            if not active_labels:
                raise ValueError(
                    f"Label truncation failure: 0 active tokens in row! prompt_len={prompt_len}, "
                    f"full_len={len(full_ids)}, max_seq_len={max_seq_len}. "
                    "Assistant tokens were completely truncated!"
                )

            input_ids_list.append(full_ids)
            attention_mask_list.append(full_mask)
            labels_list.append(labels)

        return {
            "input_ids": input_ids_list,
            "attention_mask": attention_mask_list,
            "labels": labels_list,
        }

    train_tokenized = train_dataset.map(tokenize_fn, batched=True, remove_columns=["messages"])

    # 2. Setup LoRA
    torch_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_name,
        torch_dtype=torch_dtype,
        attn_implementation="sdpa",
        device_map="auto",
        trust_remote_code=True,
    )

    peft_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=lora_r,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        bias="none",
    )
    model = get_peft_model(base_model, peft_config)
    model.print_trainable_parameters()

    output_dir = f"/tmp/checkpoints/run_{iteration}"
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        learning_rate=lr,
        lr_scheduler_type="cosine",
        warmup_steps=15,
        logging_steps=5,
        save_strategy="no",
        eval_strategy="no",
        fp16=(torch_dtype == torch.float16),
        bf16=(torch_dtype == torch.bfloat16),
        report_to="none",
        logging_dir=f"/tmp/logs/run_{iteration}",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_tokenized,
        data_collator=DataCollatorForSeq2Seq(tokenizer, pad_to_multiple_of=8),
    )

    t_train_start = time.time()
    train_result = trainer.train()
    train_duration = time.time() - t_train_start

    # Extract loss history
    loss_history = []
    for log_entry in trainer.state.log_history:
        if "loss" in log_entry:
            loss_history.append(
                {"step": log_entry.get("step"), "loss": round(log_entry.get("loss"), 4)}
            )

    final_train_loss = round(train_result.training_loss, 4)
    print(f"Training completed in {train_duration:.1f}s | Final Train Loss: {final_train_loss}")

    # Save adapter to persistent volume
    persist_path = f"/vol/checkpoints/iteration_{iteration}"
    model.save_pretrained(persist_path)
    tokenizer.save_pretrained(persist_path)
    volume.commit()
    print(f"Saved LoRA weights to persistent volume at {persist_path}")

    # 3. Post-Training Evaluation on Validation Set
    model.eval()
    print("\nRunning inference evaluation on held-out validation set...")

    predictions = []
    meal_correct = 0
    qty_correct = 0
    action_correct = 0
    mods_correct = 0
    exact_correct = 0
    valid_json_count = 0
    latencies = []

    for item in val_records:
        user_msg = next((m["content"] for m in item["messages"] if m["role"] == "user"), "")
        ground_truth_str = next(
            (m["content"] for m in item["messages"] if m["role"] == "assistant"), "{}"
        )

        try:
            gt_data = json.loads(ground_truth_str)
            if isinstance(gt_data, dict):
                gt_events = gt_data.get("events", [])
            elif isinstance(gt_data, list):
                gt_events = gt_data
            else:
                gt_events = []
            gt_event = gt_events[0] if gt_events else {}
        except Exception:
            gt_event = {}

        eval_prompt = [
            {"role": "system", "content": item["messages"][0]["content"]},
            {"role": "user", "content": user_msg},
        ]
        input_text = tokenizer.apply_chat_template(
            eval_prompt, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(input_text, return_tensors="pt").to(model.device)

        t0 = time.perf_counter()
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=180,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
        dt_ms = (time.perf_counter() - t0) * 1000
        latencies.append(dt_ms)

        gen_tokens = outputs[0][inputs["input_ids"].shape[1] :]
        pred_text = tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()

        pred_event = {}
        is_valid_json = False
        try:
            clean_pred = pred_text
            if "```json" in clean_pred:
                clean_pred = clean_pred.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_pred:
                clean_pred = clean_pred.split("```")[1].split("```")[0].strip()

            parsed = json.loads(clean_pred)
            if isinstance(parsed, dict):
                pred_events = parsed.get("events", [])
            elif isinstance(parsed, list):
                pred_events = parsed
            else:
                pred_events = []

            if pred_events and isinstance(pred_events[0], dict):
                pred_event = pred_events[0]
                is_valid_json = True
        except Exception:
            is_valid_json = False

        if is_valid_json:
            valid_json_count += 1

        m_ok = pred_event.get("meal") == gt_event.get("meal")
        q_ok = pred_event.get("qty") == gt_event.get("qty")
        a_ok = pred_event.get("action") == gt_event.get("action")
        pred_mods = set(pred_event.get("mods") or [])
        gt_mods = set(gt_event.get("mods") or [])
        mods_ok = pred_mods == gt_mods

        exact_ok = m_ok and q_ok and a_ok and mods_ok and is_valid_json

        if m_ok:
            meal_correct += 1
        if q_ok:
            qty_correct += 1
        if a_ok:
            action_correct += 1
        if mods_ok:
            mods_correct += 1
        if exact_ok:
            exact_correct += 1

        predictions.append(
            {
                "user_input": user_msg,
                "ground_truth": gt_event,
                "predicted": pred_event,
                "is_valid_json": is_valid_json,
                "exact_match": exact_ok,
                "latency_ms": round(dt_ms, 2),
                "raw_output": pred_text[:200],
            }
        )

    n_val = max(1, len(val_records))
    exact_match_acc = round((exact_correct / n_val) * 100, 1)
    meal_f1 = round(meal_correct / n_val, 3)
    qty_f1 = round(qty_correct / n_val, 3)
    action_f1 = round(action_correct / n_val, 3)
    mods_f1 = round(mods_correct / n_val, 3)
    json_validity = round((valid_json_count / n_val) * 100, 1)
    p50_latency = round(float(np.percentile(latencies, 50)), 2)
    p95_latency = round(float(np.percentile(latencies, 95)), 2)

    # 4. Domain-specific Edge Case Testing
    print("\nTesting critical domain edge cases...")
    edge_results = []
    for ec in test_edge_cases:
        prompt = [
            {"role": "system", "content": val_records[0]["messages"][0]["content"]},
            {"role": "user", "content": f"Sender: {ec['sender']}\nMessage: {ec['text']}"},
        ]
        in_str = tokenizer.apply_chat_template(
            prompt, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(in_str, return_tensors="pt").to(model.device)
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=180,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
        out_tokens = outputs[0][inputs["input_ids"].shape[1] :]
        out_text = tokenizer.decode(out_tokens, skip_special_tokens=True).strip()

        parsed_ev = {}
        try:
            cl = out_text
            if "```json" in cl:
                cl = cl.split("```json")[1].split("```")[0].strip()
            elif "```" in cl:
                cl = cl.split("```")[1].split("```")[0].strip()
            parsed_data = json.loads(cl)
            if isinstance(parsed_data, dict):
                ev_list = parsed_data.get("events", [])
            elif isinstance(parsed_data, list):
                ev_list = parsed_data
            else:
                ev_list = []
            parsed_ev = ev_list[0] if ev_list and isinstance(ev_list[0], dict) else {}
        except Exception:
            pass

        passed = True
        for key, exp_val in ec.get("expected", {}).items():
            if key == "mods":
                if set(parsed_ev.get("mods") or []) != set(exp_val or []):
                    passed = False
                    break
            elif parsed_ev.get(key) != exp_val:
                passed = False
                break

        edge_results.append(
            {
                "name": ec.get("name"),
                "input": ec.get("text"),
                "expected": ec.get("expected"),
                "predicted": parsed_ev,
                "passed": passed,
                "raw_output": out_text[:180],
            }
        )

    # Metrics bundle
    metrics = {
        "iteration": iteration,
        "base_model": base_model_name,
        "train_loss": final_train_loss,
        "train_duration_sec": round(train_duration, 1),
        "exact_match_acc": exact_match_acc,
        "meal_f1": meal_f1,
        "quantity_f1": qty_f1,
        "action_f1": action_f1,
        "mods_f1": mods_f1,
        "json_validity_pct": json_validity,
        "latency_p50_ms": p50_latency,
        "latency_p95_ms": p95_latency,
        "total_val_samples": len(val_records),
    }

    failures = [p for p in predictions if not p["exact_match"]][:10]

    out_payload = {
        "metrics": metrics,
        "loss_history": loss_history,
        "failures": failures,
        "edge_results": edge_results,
    }

    os.makedirs("/vol/evals", exist_ok=True)
    with open(f"/vol/evals/iteration_{iteration}.json", "w", encoding="utf-8") as vf:
        json.dump(out_payload, vf, indent=2)
    volume.commit()

    return out_payload


@app.local_entrypoint()
def main(
    iteration: int = 4,
    epochs: int = 2,
    lr: float = 1.5e-4,
    lora_r: int = 16,
    batch_size: int = 4,
):
    """Local runner that prepares datasets and dispatches fine-tuning to Modal GPU."""
    repo_root = Path(__file__).parent.parent
    train_file = repo_root / "data/synthetic/tinker_sft_train.jsonl"
    test_file = repo_root / "data/synthetic/test.jsonl"

    train_records = []
    if train_file.exists():
        with open(train_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    train_records.append(json.loads(line))

    from tiffintally.extract.base import SYSTEM_PROMPT

    val_records = []
    if test_file.exists():
        with open(test_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    raw_text = item.get("raw_text") or item.get("text", "")
                    sender = item.get("sender") or item.get("customer", "Customer")
                    gold = item.get("gold") or {}
                    if not gold:
                        gold = {
                            "customer": sender,
                            "date": item.get("date", "tomorrow"),
                            "meal": item.get("meal", "lunch"),
                            "qty": item.get("qty", 1),
                            "items": item.get("items", ["thali"]),
                            "mods": item.get("mods", []),
                            "action": item.get("action", "new"),
                        }
                    val_records.append(
                        {
                            "messages": [
                                {"role": "system", "content": SYSTEM_PROMPT.strip()},
                                {
                                    "role": "user",
                                    "content": f"Sender: {sender}\nMessage: {raw_text}",
                                },
                                {
                                    "role": "assistant",
                                    "content": json.dumps({"events": [gold]}),
                                },
                            ]
                        }
                    )

    val_records = val_records[:20]

    edge_cases = [
        {
            "name": "cancellation_with_reason",
            "sender": "Ravi",
            "text": "kal lunch cancel aunty, team lunch hai office me",
            "expected": {"meal": "lunch", "action": "cancel", "qty": 0},
        },
        {
            "name": "dietary_modification",
            "sender": "Pooja",
            "text": "bina pyaaz ke do thali bhejo lunch me",
            "expected": {"meal": "lunch", "qty": 2, "mods": ["no onion"], "action": "new"},
        },
        {
            "name": "roommate_order_split",
            "sender": "Karan",
            "text": "kal lunch ek plate aur roommate Priya ke liye bhi ek",
            "expected": {"meal": "lunch", "action": "new"},
        },
        {
            "name": "standing_order_pause",
            "sender": "Amit",
            "text": "Sunday off please, going home for weekend",
            "expected": {"action": "pause", "qty": 0},
        },
        {
            "name": "pure_chitchat_compliment",
            "sender": "Sneha",
            "text": "thank you aunty, khana bahut mast tha!",
            "expected": {"action": "none", "qty": 0},
        },
    ]

    hyperparams = {
        "iteration": iteration,
        "base_model_name": "Qwen/Qwen2.5-0.5B-Instruct",
        "num_epochs": epochs,
        "learning_rate": lr,
        "lora_r": lora_r,
        "lora_alpha": lora_r * 2,
        "batch_size": batch_size,
        "grad_accum": 4,
        "max_seq_len": 768,
    }

    print(
        f"Triggering Modal fine-tuning with {len(train_records)} train & {len(val_records)} val records..."
    )
    result = run_finetune_job.remote(
        train_records=train_records,
        val_records=val_records,
        test_edge_cases=edge_cases,
        hyperparams=hyperparams,
    )

    out_file = repo_root / f"evals/modal_run_iter_{iteration}.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print("\n=======================================================")
    print(f"🎉 Modal Iteration {iteration} Run Complete!")
    print(f"Metrics saved to {out_file}")
    print(json.dumps(result["metrics"], indent=2))
    print("=======================================================\n")
