"""
Evaluate a saved fine-tuned checkpoint from Modal Volume (/vol/checkpoints/iteration_X)
across both Real Customer WhatsApp (data/private/real_test.jsonl) and Synthetic Held-Out test set.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

import modal

app = modal.App("tiffintally-eval-checkpoint")
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
def run_eval_job(
    iteration: int,
    synthetic_records: List[Dict[str, Any]],
    real_records: List[Dict[str, Any]],
    test_edge_cases: List[Dict[str, Any]],
) -> Dict[str, Any]:
    import os
    import time

    import numpy as np
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    checkpoint_dir = f"/vol/checkpoints/iteration_{iteration}"
    if not os.path.exists(checkpoint_dir):
        raise FileNotFoundError(f"Checkpoint directory {checkpoint_dir} does not exist!")

    print(f"\nLoading model & adapter from {checkpoint_dir} on A10G...")
    base_model_name = "Qwen/Qwen2.5-0.5B-Instruct"
    tokenizer = AutoTokenizer.from_pretrained(checkpoint_dir, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    torch_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_name,
        torch_dtype=torch_dtype,
        attn_implementation="sdpa",
        device_map="auto",
        trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(base_model, checkpoint_dir)
    model.eval()

    def evaluate_split(records: List[Dict[str, Any]], split_name: str) -> Dict[str, Any]:
        print(f"Evaluating {split_name} ({len(records)} samples)...")
        predictions = []
        meal_correct = 0
        qty_correct = 0
        action_correct = 0
        mods_correct = 0
        exact_correct = 0
        valid_json_count = 0
        latencies = []

        for item in records:
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
                    max_new_tokens=96,
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

            meal_match = pred_event.get("meal") == gt_event.get("meal")
            qty_match = pred_event.get("qty") == gt_event.get("qty")
            action_match = pred_event.get("action") == gt_event.get("action")
            mods_match = set(pred_event.get("mods") or []) == set(gt_event.get("mods") or [])

            if meal_match:
                meal_correct += 1
            if qty_match:
                qty_correct += 1
            if action_match:
                action_correct += 1
            if mods_match:
                mods_correct += 1

            exact_ok = meal_match and qty_match and action_match
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

        n_samples = max(1, len(records))
        em_acc = round((exact_correct / n_samples) * 100, 1)
        m_f1 = round(meal_correct / n_samples, 3)
        q_f1 = round(qty_correct / n_samples, 3)
        a_f1 = round(action_correct / n_samples, 3)
        mod_f1 = round(mods_correct / n_samples, 3)
        j_val = round((valid_json_count / n_samples) * 100, 1)
        p50 = round(float(np.percentile(latencies, 50)), 2) if latencies else 0.0
        p95 = round(float(np.percentile(latencies, 95)), 2) if latencies else 0.0

        failures = [p for p in predictions if not p["exact_match"]]

        return {
            "summary": {
                "dataset_name": split_name,
                "num_samples": n_samples,
                "exact_match_acc": em_acc,
                "meal_f1": m_f1,
                "quantity_f1": q_f1,
                "action_f1": a_f1,
                "mods_f1": mod_f1,
                "json_validity_pct": j_val,
                "latency_p50_ms": p50,
                "latency_p95_ms": p95,
                "failure_count": len(failures),
            },
            "failures": failures,
        }

    synthetic_eval = evaluate_split(synthetic_records, "Synthetic Test Split")
    real_eval = evaluate_split(real_records, "Real Customer WhatsApp")

    print("\nTesting domain edge cases...")
    edge_results = []
    sys_prompt = synthetic_records[0]["messages"][0]["content"] if synthetic_records else ""
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

    metrics = {
        "iteration": iteration,
        "base_model": base_model_name,
        "synthetic": synthetic_eval["summary"],
        "real": real_eval["summary"],
        "edge_cases_passed": f"{sum(1 for e in edge_results if e['passed'])}/{len(edge_results)}",
    }

    out_payload = {
        "metrics": metrics,
        "synthetic_failures": synthetic_eval["failures"][:10],
        "real_failures": real_eval["failures"],
        "edge_results": edge_results,
    }

    os.makedirs("/vol/evals", exist_ok=True)
    with open(f"/vol/evals/iteration_{iteration}.json", "w", encoding="utf-8") as vf:
        json.dump(out_payload, vf, indent=2)
    volume.commit()

    return out_payload


@app.local_entrypoint()
def main(iteration: int = 6):
    repo_root = Path(__file__).parent.parent
    test_file = repo_root / "data/synthetic/test.jsonl"
    real_test_file = repo_root / "data/private/real_test.jsonl"

    from tiffintally.extract.base import SYSTEM_PROMPT

    synthetic_records = []
    if test_file.exists():
        with open(test_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    raw_text = item.get("raw_text") or item.get("text", "")
                    sender = item.get("sender") or item.get("customer", "Customer")
                    gold = item.get("gold") or {}
                    synthetic_records.append(
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
    synthetic_records = synthetic_records[:30]

    real_records = []
    if real_test_file.exists():
        with open(real_test_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    sender = item.get("sender", "Customer")
                    raw_text = item.get("text", "")
                    gold = item.get("gold", {})
                    real_records.append(
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

    print(
        f"\nSubmitting evaluation job for Checkpoint Iteration {iteration} to Modal GPU (A10G)..."
    )
    result = run_eval_job.remote(
        iteration=iteration,
        synthetic_records=synthetic_records,
        real_records=real_records,
        test_edge_cases=edge_cases,
    )

    out_file = repo_root / f"evals/modal_run_iter_{iteration}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print("\n=======================================================")
    print(f"🎉 Modal Checkpoint Iteration {iteration} Dual-Benchmark Complete!")
    print("=======================================================")
    print("📊 METRICS SUMMARY:")
    print(json.dumps(result["metrics"], indent=2))
    print(f"\nSaved local evaluation record to {out_file}")


if __name__ == "__main__":
    main()
