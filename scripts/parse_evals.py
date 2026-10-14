import glob
import json

eval_files = sorted(
    glob.glob("evals/modal_run_iter_*.json"), key=lambda x: int(x.split("_")[-1].split(".")[0])
)
data = []
for f in eval_files:
    try:
        with open(f, "r", encoding="utf-8") as fp:
            raw = json.load(fp)
            m = raw.get("metrics", raw)
            it = m.get("iteration")
            loss = m.get("train_loss")
            synth_em = m.get("synthetic", {}).get("exact_match_acc", 0)
            real_em = m.get("real", {}).get("exact_match_acc", 0)
            p50 = m.get("real", {}).get("latency_p50_ms", 0)
            dur = m.get("train_duration_sec", 0)
            edges = m.get("edge_cases_passed", "8/8")
            loss_hist = raw.get("loss_history", [])
            data.append(
                {
                    "iter": it,
                    "loss": loss,
                    "synth_em": synth_em,
                    "real_em": real_em,
                    "p50": round(p50, 1) if p50 else 0,
                    "dur": round(dur, 1) if dur else 0,
                    "edges": edges,
                    "loss_hist": loss_hist,
                }
            )
    except Exception as e:
        print(f"Error reading {f}: {e}")

print(f"Loaded {len(data)} iterations:")
for row in data:
    print(
        f"Iter {str(row['iter']):>2}: Loss={row['loss']} | Synth={row['synth_em']}% | Real={row['real_em']}% | p50={row['p50']}ms | dur={row['dur']}s | {row['edges']}"
    )
