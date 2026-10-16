"""
TiffinTally: Distributed SLM Fine-Tuning & Multi-Benchmark Evaluation on Modal GPU.
Uses a Qwen2.5 Instruct checkpoint plus LoRA on an NVIDIA A10G.
The default base model is Qwen/Qwen2.5-3B-Instruct.
Evaluates the template-disjoint synthetic test split only.
data/private/real_test.jsonl is not scored: its texts overlap training.
Scoring uses the shared strict/lenient event-set definitions; saved historical scores used a different definition.
Supports iterative improvement loops with persistent Volume caching (/vol/checkpoints/).
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

import modal

app = modal.App("tiffintally-finetune")
volume = modal.Volume.from_name("tiffintally-models", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch>=2.4.0",
        "transformers==4.46.3",
        "peft==0.13.2",
        "accelerate>=0.34.0",
        "datasets>=3.0.0",
        "bitsandbytes>=0.43.0",
        "scikit-learn>=1.5.0",
        "pydantic>=2.0.0",
    )
    .add_local_python_source("tiffintally")
    .add_local_dir("data/vocab", remote_path="/root/data/vocab")
)


@app.function(
    image=image,
    gpu="A10G",
    timeout=1200,
    volumes={"/vol": volume},
)
def run_finetune_job(
    train_records: List[Dict[str, Any]],
    synthetic_val_records: List[Dict[str, Any]],
    real_val_records: List[Dict[str, Any]],
    test_edge_cases: List[Dict[str, Any]],
    hyperparams: Dict[str, Any],
) -> Dict[str, Any]:
    import torch
    from datasets import Dataset
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForSeq2Seq,
        Trainer,
        TrainingArguments,
        set_seed,
    )

    iteration = hyperparams.get("iteration", 12)
    set_seed(hyperparams.get("seed", 271))
    base_model_name = hyperparams.get("base_model_name", "Qwen/Qwen2.5-0.5B-Instruct")
    num_epochs = hyperparams.get("num_epochs", 2)
    lr = hyperparams.get("learning_rate", 1.5e-4)
    lora_r = hyperparams.get("lora_r", 32)
    lora_alpha = hyperparams.get("lora_alpha", 64)
    lora_dropout = hyperparams.get("lora_dropout", 0.05)
    batch_size = hyperparams.get("batch_size", 4)
    grad_accum = hyperparams.get("grad_accum", 4)
    max_seq_len = hyperparams.get("max_seq_len", 768)
    target_modules = hyperparams.get(
        "target_modules",
        ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    lr_scheduler_type = hyperparams.get("lr_scheduler_type", "cosine")
    weight_decay = hyperparams.get("weight_decay", 0.0)
    warmup_steps = hyperparams.get("warmup_steps", 15)

    print("\n=======================================================")
    print(f"🚀 Starting TiffinTally Iteration {iteration} on Modal (A10G GPU)")
    print(f"Base Model: {base_model_name} | Epochs: {num_epochs} | LR: {lr}")
    print(
        f"LoRA: r={lora_r}, alpha={lora_alpha}, dropout={lora_dropout} | Modules: {len(target_modules)}"
    )
    print(
        f"Schedule: {lr_scheduler_type} | Weight Decay: {weight_decay} | Warmup: {warmup_steps} | Train size: {len(train_records)}"
    )
    print(
        f"Val sizes: Synthetic={len(synthetic_val_records)} | Real Held-Out={len(real_val_records)}"
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
                    f"full_len={len(full_ids)}, max_seq_len={max_seq_len}."
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
        target_modules=target_modules,
        bias="none",
    )
    model = get_peft_model(base_model, peft_config)
    model.print_trainable_parameters()
    if hasattr(base_model, "gradient_checkpointing_enable"):
        base_model.gradient_checkpointing_enable()
        model.enable_input_require_grads()

    output_dir = f"/tmp/checkpoints/run_{iteration}"
    training_args = TrainingArguments(
        seed=hyperparams.get("seed", 271),
        data_seed=hyperparams.get("seed", 271),
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        learning_rate=lr,
        lr_scheduler_type=lr_scheduler_type,
        weight_decay=weight_decay,
        warmup_steps=warmup_steps,
        logging_steps=10,
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
    os.makedirs(persist_path, exist_ok=True)
    model.save_pretrained(persist_path)
    tokenizer.save_pretrained(persist_path)
    volume.commit()
    print(f"Saved LoRA weights to persistent volume at {persist_path}")

    # 3. High-Throughput Batched Evaluation Engine
    model.eval()

    def evaluate_split(records: List[Dict[str, Any]], split_name: str) -> Dict[str, Any]:
        from tiffintally.model_validation import clean_model_event
        from tiffintally.scoring import score_events, summarize

        predictions = []
        tokenizer.padding_side = "left"
        for index, item in enumerate(records):
            user_msg = next(m["content"] for m in item["messages"] if m["role"] == "user")
            target = next(m["content"] for m in item["messages"] if m["role"] == "assistant")
            gold = json.loads(target)["events"]
            prompt = tokenizer.apply_chat_template(
                item["messages"][:2], tokenize=False, add_generation_prompt=True
            )
            inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
            started = time.perf_counter()
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=256,
                    do_sample=False,
                    pad_token_id=tokenizer.pad_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                )
            latency = (time.perf_counter() - started) * 1000
            raw = tokenizer.decode(
                outputs[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True
            ).strip()
            parse_ok = True
            try:
                doc = json.loads(raw)
                parsed = doc["events"] if isinstance(doc, dict) else doc
                if not isinstance(parsed, list):
                    raise ValueError("No event list")
                parsed = [clean_model_event(row) for row in parsed]
            except (ValueError, TypeError, KeyError):
                parsed, parse_ok = [], False
            predictions.append(
                dict(
                    id=item.get("id", f"{split_name}_{index}"),
                    template_id=item.get("template_id", f"unknown_{index}"),
                    text=user_msg,
                    raw_output=raw,
                    parsed=parsed,
                    gold=gold,
                    parse_ok=parse_ok,
                    latency_ms=latency,
                    **score_events(parsed, gold, parse_ok=parse_ok),
                )
            )
        return {
            "summary": summarize(predictions),
            "predictions": predictions,
            "failures": [row for row in predictions if not row["strict_ok"]],
        }

    # Evaluate Synthetic Test Split
    synthetic_eval = evaluate_split(synthetic_val_records, "Synthetic Test Split")
    # Evaluate Real Gold WhatsApp Held-Out Split
    if real_val_records:
        real_eval = evaluate_split(real_val_records, "Held-out file passed by the caller")
    else:
        real_eval = {
            "summary": {
                "dataset_name": "real customer messages",
                "num_samples": 0,
                "strict": None,
                "status": "not_run",
                "reason": hyperparams.get(
                    "real_eval_note",
                    "No verified cook-labelled set was passed.",
                ),
            },
            "failures": [],
        }

    # Historical edge diagnostics are not held-out evaluation.
    test_edge_cases = []
    # 4. Domain-specific Edge Case Testing
    print("\nTesting critical domain edge cases...")
    edge_results = []
    sys_prompt = synthetic_val_records[0]["messages"][0]["content"] if synthetic_val_records else ""
    for ec in test_edge_cases:
        prompt = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"Sender: {ec['sender']}\nMessage: {ec['text']}"},
        ]
        in_str = tokenizer.apply_chat_template(prompt, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(in_str, return_tensors="pt").to(model.device)
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=96,
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
            ev_list = (
                parsed_data.get("events", [])
                if isinstance(parsed_data, dict)
                else (parsed_data if isinstance(parsed_data, list) else [])
            )
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

    # Master metrics bundle
    metrics = {
        "iteration": iteration,
        "base_model": base_model_name,
        "split": "synthetic template-disjoint held-out",
        "real_customer_eval": "not_run",
        "train_loss": final_train_loss,
        "train_duration_sec": round(train_duration, 1),
        "synthetic": synthetic_eval["summary"],
        "real": real_eval["summary"],
        "edge_cases_status": "RETIRED: training diagnostics, not held-out evidence",
    }

    out_payload = {
        "metrics": metrics,
        "loss_history": loss_history,
        "synthetic_predictions": synthetic_eval["predictions"],
        "synthetic_failures": synthetic_eval["failures"],
        "real_failures": real_eval["failures"],
        "edge_results": edge_results,
    }

    os.makedirs("/vol/evals", exist_ok=True)
    with open(f"/vol/evals/iteration_{iteration}.json", "w", encoding="utf-8") as vf:
        json.dump(out_payload, vf, indent=2)
    volume.commit()

    return out_payload


@app.local_entrypoint()
def main(
    iteration: int = 12,
    epochs: int = 2,
    lr: float = 1.5e-4,
    lora_r: int = 32,
    lora_alpha: int = 64,
    lora_dropout: float = 0.05,
    batch_size: int = 4,
    grad_accum: int = 4,
    target_modules: str = "all",
    lr_scheduler: str = "cosine",
    weight_decay: float = 0.0,
    warmup_steps: int = 15,
    base_model: str = "Qwen/Qwen2.5-3B-Instruct",
    max_seq_len: int = 1024,
    seed: int = 271,
    train_path: str = "",
):
    """Local runner that prepares datasets and dispatches fine-tuning to Modal GPU."""
    repo_root = Path(__file__).parent.parent
    from tiffintally.gpu_budget import require_training_approval

    require_training_approval()
    train_file = (
        Path(train_path) if train_path else repo_root / "data/synthetic/tinker_sft_train.jsonl"
    )
    if not train_file.is_file():
        raise FileNotFoundError("Reviewed training dataset missing; refusing to train")
    test_file = repo_root / "data/synthetic/test.jsonl"

    from tiffintally.extract.base import SYSTEM_PROMPT

    train_records = []
    if train_file.exists():
        with open(train_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    train_records.append(json.loads(line))

    synthetic_val_records = []
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
                    synthetic_val_records.append(
                        {
                            "id": item["id"],
                            "template_id": item["template_id"],
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
                            ],
                        }
                    )

    # data/private/real_test.jsonl overlaps the training text. It is not scored.
    real_val_records = []

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
            "name": "lexical_three_with_mods",
            "sender": "Shreya",
            "text": "bina pyaaz ke teen thali bhejo lunch me",
            "expected": {"meal": "lunch", "qty": 3, "mods": ["no onion"], "action": "new"},
        },
        {
            "name": "roommate_order_split",
            "sender": "Karan",
            "text": "kal lunch ek plate aur roommate Priya ke liye bhi ek",
            "expected": {"secondary_customer": "Priya", "meal": "lunch", "qty": 1, "action": "new"},
        },
        {
            "name": "standing_order_pause",
            "sender": "Sneha",
            "text": "Sunday off please, going home for weekend",
            "expected": {"meal": "both", "qty": 0, "action": "pause"},
        },
        {
            "name": "pure_chitchat_compliment",
            "sender": "Divya",
            "text": "thank you aunty, khana bahut mast tha!",
            "expected": {"meal": "unspecified", "qty": 0, "action": "none"},
        },
        {
            "name": "delivery_timing_disambiguation",
            "sender": "Amitabh",
            "text": "Send dinner tonight by 8:30 pm sharp, 1 thali less spicy",
            "expected": {"meal": "dinner", "qty": 1, "action": "new"},
        },
        {
            "name": "devanagari_mixed_order",
            "sender": "Geeta",
            "text": "कल दोपहर एक थाली, बिना मिर्ची की",
            "expected": {"meal": "lunch", "qty": 1, "action": "new"},
        },
    ]

    if target_modules == "attn_only":
        tm_list = ["q_proj", "v_proj"]
    else:
        tm_list = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]

    hyperparams = {
        "seed": seed,
        "iteration": iteration,
        "base_model_name": base_model,
        "real_eval_note": (
            "Skipped data/private/real_test.jsonl. 36 of its 50 texts are in the "
            "training file, so it is not a held-out cook set."
        ),
        "num_epochs": epochs,
        "learning_rate": lr,
        "lora_r": lora_r,
        "lora_alpha": lora_alpha,
        "lora_dropout": lora_dropout,
        "batch_size": batch_size,
        "grad_accum": grad_accum,
        "target_modules": tm_list,
        "lr_scheduler_type": lr_scheduler,
        "weight_decay": weight_decay,
        "warmup_steps": warmup_steps,
        "max_seq_len": max_seq_len,
    }

    print(f"\nSubmitting fine-tuning job for Iteration {iteration} to Modal GPU (A10G)...")
    result = run_finetune_job.remote(
        train_records=train_records,
        synthetic_val_records=synthetic_val_records,
        real_val_records=real_val_records,
        test_edge_cases=edge_cases,
        hyperparams=hyperparams,
    )

    out_file = repo_root / f"evals/modal_run_iter_{iteration}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print("\n=======================================================")
    print(f"🎉 Modal Fine-Tuning & Dual-Benchmark Iteration {iteration} Complete!")
    print("=======================================================")
    print("📊 METRICS SUMMARY:")
    print(json.dumps(result["metrics"], indent=2))
    print(f"\nSaved local evaluation record to {out_file}")


if __name__ == "__main__":
    main()
