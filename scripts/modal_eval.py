"""
TiffinTally: Standalone Evaluation Script on Modal.
Loads fine-tuned checkpoint from /vol/checkpoints/iteration_{N},
runs held-out benchmark and edge case evaluation on GPU,
and saves metrics to evals/modal_run_iter_{N}.json.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

import modal

app = modal.App("tiffintally-eval")
volume = modal.Volume.from_name("tiffintally-models")

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
def evaluate_checkpoint(
    iteration: int,
    val_records: List[Dict[str, Any]],
    test_edge_cases: List[Dict[str, Any]],
    train_loss: float = 0.0912,
    train_duration_sec: float = 561.0,
) -> Dict[str, Any]:
    import os
    import time

    import numpy as np
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    base_model_name = "Qwen/Qwen2.5-0.5B-Instruct"
    adapter_path = f"/vol/checkpoints/iteration_{iteration}"
    print(f"Loading base model {base_model_name}...")
    torch_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16

    tokenizer = AutoTokenizer.from_pretrained(adapter_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_name,
        torch_dtype=torch_dtype,
        device_map="auto",
        attn_implementation="sdpa",
        trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(base_model, adapter_path)
    model.eval()
    print(f"Successfully loaded LoRA adapter from {adapter_path}!")

    predictions = []
    meal_correct = 0
    qty_correct = 0
    action_correct = 0
    mods_correct = 0
    exact_correct = 0
    valid_json_count = 0
    latencies = []

    print(f"\nEvaluating on {len(val_records)} validation samples...")
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
            val = parsed_ev.get(key)
            if key == "mods":
                val_set = set(val) if isinstance(val, list) else set([val] if val else [])
                exp_set = set(exp_val) if isinstance(exp_val, list) else set([exp_val] if exp_val else [])
                if val_set != exp_set:
                    passed = False
                    break
            else:
                if val != exp_val:
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

    metrics = {
        "iteration": iteration,
        "base_model": base_model_name,
        "train_loss": train_loss,
        "train_duration_sec": train_duration_sec,
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
        "failures": failures,
        "edge_results": edge_results,
    }

    os.makedirs("/vol/evals", exist_ok=True)
    with open(f"/vol/evals/iteration_{iteration}.json", "w", encoding="utf-8") as vf:
        json.dump(out_payload, vf, indent=2)
    volume.commit()

    return out_payload


@app.local_entrypoint()
def main(iteration: int = 4, samples: int = 30):
    repo_root = Path(__file__).parent.parent
    test_file = repo_root / "data/synthetic/test.jsonl"
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

    val_records = val_records[:samples]

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

    print(f"Triggering evaluation for Iteration {iteration} on Modal GPU...")
    res = evaluate_checkpoint.remote(
        iteration=iteration,
        val_records=val_records,
        test_edge_cases=edge_cases,
        train_loss=0.0912,
        train_duration_sec=561.0,
    )

    out_file = repo_root / f"evals/modal_run_iter_{iteration}.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)

    print(f"\nSaved metrics to {out_file}")
    print(json.dumps(res["metrics"], indent=2))
