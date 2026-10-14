"""
Automated Campaign Orchestrator for Multi-Iteration Fine-Tuning & Dual-Benchmark Evaluation.
Runs empirical iterations on Modal GPU (A10G), verifies convergence, logs metrics to JSON,
and updates telemetry records.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
EVALS_DIR = REPO_ROOT / "evals"
EVALS_DIR.mkdir(parents=True, exist_ok=True)

# Master Hyperparameter Sweep Registry (Iterations 12 to 31)
ITERATION_SPECS = {
    12: {
        "title": "Data Scaling (N=1,280 ChatML rows, regional code-switching & ASR noise)",
        "epochs": 2,
        "lr": 1.5e-4,
        "lora_r": 32,
        "lora_alpha": 64,
        "lora_dropout": 0.05,
        "batch_size": 4,
        "grad_accum": 4,
        "target_modules": "all",
        "lr_scheduler": "cosine",
        "weight_decay": 0.0,
    },
    13: {
        "title": "Weight Decay Regularization (wd=0.01)",
        "epochs": 2,
        "lr": 1.5e-4,
        "lora_r": 32,
        "lora_alpha": 64,
        "lora_dropout": 0.05,
        "batch_size": 4,
        "grad_accum": 4,
        "target_modules": "all",
        "lr_scheduler": "cosine",
        "weight_decay": 0.01,
    },
    14: {
        "title": "Zero LoRA Dropout Ablation (p_drop=0.0)",
        "epochs": 2,
        "lr": 1.5e-4,
        "lora_r": 32,
        "lora_alpha": 64,
        "lora_dropout": 0.0,
        "batch_size": 4,
        "grad_accum": 4,
        "target_modules": "all",
        "lr_scheduler": "cosine",
        "weight_decay": 0.0,
    },
    15: {
        "title": "Attention-Only Target Modules (q_proj, v_proj only - 4.4M params)",
        "epochs": 2,
        "lr": 1.5e-4,
        "lora_r": 32,
        "lora_alpha": 64,
        "lora_dropout": 0.05,
        "batch_size": 4,
        "grad_accum": 4,
        "target_modules": "attn_only",
        "lr_scheduler": "cosine",
        "weight_decay": 0.0,
    },
    16: {
        "title": "High Capacity LoRA Scaling (r=64, alpha=128)",
        "epochs": 2,
        "lr": 1.5e-4,
        "lora_r": 64,
        "lora_alpha": 128,
        "lora_dropout": 0.05,
        "batch_size": 4,
        "grad_accum": 4,
        "target_modules": "all",
        "lr_scheduler": "cosine",
        "weight_decay": 0.0,
    },
    17: {
        "title": "Edge Lightweight LoRA Footprint (r=8, alpha=16 - 4.4M params)",
        "epochs": 2,
        "lr": 1.5e-4,
        "lora_r": 8,
        "lora_alpha": 16,
        "lora_dropout": 0.05,
        "batch_size": 4,
        "grad_accum": 4,
        "target_modules": "all",
        "lr_scheduler": "cosine",
        "weight_decay": 0.0,
    },
    18: {
        "title": "High Alpha-to-Rank Ratio (alpha/r = 4.0: r=16, alpha=64)",
        "epochs": 2,
        "lr": 1.5e-4,
        "lora_r": 16,
        "lora_alpha": 64,
        "lora_dropout": 0.05,
        "batch_size": 4,
        "grad_accum": 4,
        "target_modules": "all",
        "lr_scheduler": "cosine",
        "weight_decay": 0.0,
    },
    19: {
        "title": "Conservative Learning Rate Sensitivity (lr=8.0e-5)",
        "epochs": 2,
        "lr": 8.0e-5,
        "lora_r": 32,
        "lora_alpha": 64,
        "lora_dropout": 0.05,
        "batch_size": 4,
        "grad_accum": 4,
        "target_modules": "all",
        "lr_scheduler": "cosine",
        "weight_decay": 0.0,
    },
    20: {
        "title": "Aggressive Learning Rate Boundary (lr=3.0e-4)",
        "epochs": 2,
        "lr": 3.0e-4,
        "lora_r": 32,
        "lora_alpha": 64,
        "lora_dropout": 0.05,
        "batch_size": 4,
        "grad_accum": 4,
        "target_modules": "all",
        "lr_scheduler": "cosine",
        "weight_decay": 0.0,
    },
    21: {
        "title": "Linear Learning Rate Decay Schedule",
        "epochs": 2,
        "lr": 1.5e-4,
        "lora_r": 32,
        "lora_alpha": 64,
        "lora_dropout": 0.05,
        "batch_size": 4,
        "grad_accum": 4,
        "target_modules": "all",
        "lr_scheduler": "linear",
        "weight_decay": 0.0,
    },
    22: {
        "title": "Batch Scaling & Physical Batch Size Study (batch_size=8, accum=2)",
        "epochs": 2,
        "lr": 1.5e-4,
        "lora_r": 32,
        "lora_alpha": 64,
        "lora_dropout": 0.05,
        "batch_size": 8,
        "grad_accum": 2,
        "target_modules": "all",
        "lr_scheduler": "cosine",
        "weight_decay": 0.0,
    },
    23: {
        "title": "3-Epoch Full Convergence Sweep (240 steps)",
        "epochs": 3,
        "lr": 1.5e-4,
        "lora_r": 32,
        "lora_alpha": 64,
        "lora_dropout": 0.05,
        "batch_size": 4,
        "grad_accum": 4,
        "target_modules": "all",
        "lr_scheduler": "cosine",
        "weight_decay": 0.0,
    },
    24: {
        "title": "Regularized Champion Run (wd=0.01, p_drop=0.0, r=32)",
        "epochs": 2,
        "lr": 1.5e-4,
        "lora_r": 32,
        "lora_alpha": 64,
        "lora_dropout": 0.0,
        "batch_size": 4,
        "grad_accum": 4,
        "target_modules": "all",
        "lr_scheduler": "cosine",
        "weight_decay": 0.01,
    },
    25: {
        "title": "3-Epoch Regularized Optimal Champion (wd=0.01, r=32, lr=1.5e-4)",
        "epochs": 3,
        "lr": 1.5e-4,
        "lora_r": 32,
        "lora_alpha": 64,
        "lora_dropout": 0.05,
        "batch_size": 4,
        "grad_accum": 4,
        "target_modules": "all",
        "lr_scheduler": "cosine",
        "weight_decay": 0.01,
    },
}


def run_iteration(iteration: int) -> bool:
    if iteration not in ITERATION_SPECS:
        print(f"Iteration {iteration} not found in registry.")
        return False

    spec = ITERATION_SPECS[iteration]
    print(f"\n=======================================================")
    print(f"🚀 LAUNCHING ITERATION {iteration}: {spec['title']}")
    print(f"Hyperparameters: {spec}")
    print("=======================================================\n")

    cmd = [
        "uv",
        "run",
        "modal",
        "run",
        "scripts/modal_finetune.py",
        f"--iteration={iteration}",
        f"--epochs={spec['epochs']}",
        f"--lr={spec['lr']}",
        f"--lora-r={spec['lora_r']}",
        f"--lora-alpha={spec['lora_alpha']}",
        f"--lora-dropout={spec['lora_dropout']}",
        f"--batch-size={spec['batch_size']}",
        f"--grad-accum={spec['grad_accum']}",
        f"--target-modules={spec['target_modules']}",
        f"--lr-scheduler={spec['lr_scheduler']}",
        f"--weight-decay={spec['weight_decay']}",
    ]

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env)
    if result.returncode != 0:
        print(f"❌ Iteration {iteration} failed with return code {result.returncode}")
        return False

    eval_file = EVALS_DIR / f"modal_run_iter_{iteration}.json"
    if eval_file.exists():
        with open(eval_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"\n✅ Iteration {iteration} Success!")
        print("Metrics Summary:")
        print(json.dumps(data.get("metrics", {}), indent=2))
        return True
    else:
        print(f"⚠️ Warning: Output eval file {eval_file} was not found.")
        return False


def main():
    parser = argparse.ArgumentParser(description="Run fine-tuning iterations on Modal")
    parser.add_argument("--iter", type=int, help="Single iteration to run")
    parser.add_argument("--start", type=int, default=12, help="Start iteration")
    parser.add_argument("--end", type=int, default=25, help="End iteration")
    args = parser.parse_args()

    if args.iter:
        run_iteration(args.iter)
    else:
        for it in range(args.start, args.end + 1):
            if it in ITERATION_SPECS:
                success = run_iteration(it)
                if not success:
                    print(f"Stopping campaign at iteration {it} due to failure.")
                    break


if __name__ == "__main__":
    main()
