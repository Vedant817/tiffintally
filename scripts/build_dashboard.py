"""
Render the saved run artifacts as one self-contained HTML dashboard.

Charts are inline SVG so the file opens from disk with no network and no chart
library. Every number is read from evals/runs/<ts>/*.json; nothing is recomputed
here, so the page cannot drift from the artifact it cites.

Usage:
    uv run python scripts/build_dashboard.py
    uv run python scripts/build_dashboard.py --run evals/runs/20261015_175344
"""

import argparse
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "evals" / "runs"
OUT = ROOT / "evals" / "dashboard.html"

FIELDS = [
    ("meal", "Meal"),
    ("qty", "Quantity"),
    ("action", "Action"),
    ("mods", "Dietary mods"),
]

COLORS = {
    "regex": "#64748b",
    "base": "#f59e0b",
    "lora": "#2563eb",
}


def latest(pattern: str):
    matches = sorted(RUNS.glob(pattern))
    return matches[-1] if matches else None


def esc(text) -> str:
    return html.escape(str(text), quote=True)


def bar(value: float, color: str, max_value: float = 1.0, width: int = 220) -> str:
    filled = max(0.0, min(1.0, value / max_value if max_value else 0.0)) * width
    pct = value * 100
    return (
        f'<svg class="bar" width="{width + 58}" height="18" role="img" '
        f'aria-label="{pct:.1f} percent">'
        f'<rect x="0" y="4" width="{width}" height="10" rx="5" fill="#e2e8f0"/>'
        f'<rect x="0" y="4" width="{filled:.1f}" height="10" rx="5" fill="{color}"/>'
        f'<text x="{width + 8}" y="14" font-size="12" fill="#334155" '
        f'font-family="ui-monospace,Menlo,monospace">{pct:.1f}</text>'
        f"</svg>"
    )


def grouped_bars(named: list, colors: list) -> str:
    """Horizontal grouped bars: one group per field, one bar per extractor."""
    if not named:
        return ""
    groups = []
    for key, label in FIELDS:
        cells = []
        for (name, score), color in zip(named, colors):
            value = score.get("per_field", {}).get(key, 0.0)
            cells.append(
                f'<div class="barrow"><span class="barlabel">{esc(name)}</span>'
                f"{bar(value, color)}</div>"
            )
        groups.append(
            f'<div class="group"><div class="glabel">{esc(label)}</div>' + "".join(cells) + "</div>"
        )
    legend = "".join(
        f'<span class="key"><i style="background:{c}"></i>{esc(n)}</span>'
        for (n, _s), c in zip(named, colors)
    )
    return f'<div class="legend">{legend}</div>' + "".join(groups)


def donut(slices: list) -> str:
    """Donut of win counts. `slices` is [(label, value, color)]."""
    total = sum(v for _l, v, _c in slices) or 1
    r, stroke = 54, 22
    circumference = 2 * 3.14159 * r
    offset = 0.0
    parts = []
    for label, value, color in slices:
        length = circumference * value / total
        parts.append(
            f'<circle class="seg" r="{r}" cx="80" cy="80" fill="none" stroke="{color}" '
            f'stroke-width="{stroke}" stroke-dasharray="{length:.2f} '
            f'{circumference - length:.2f}" stroke-dashoffset="{-offset:.2f}" '
            f'transform="rotate(-90 80 80)"><title>{esc(label)}: {value}</title></circle>'
        )
        offset += length
    centre = (
        f'<text x="80" y="76" text-anchor="middle" font-size="26" font-weight="700" '
        f'fill="#0f172a">{sum(v for _l, v, _c in slices)}</text>'
        f'<text x="80" y="96" text-anchor="middle" font-size="11" fill="#64748b">'
        f"rows they differ on</text>"
    )
    return f'<svg viewBox="0 0 160 160" width="160" height="160">{"".join(parts)}{centre}</svg>'


def score_table(columns: list) -> str:
    head = "".join(f"<th>{esc(name)}</th>" for name, _v in columns)
    last = len(columns) - 1
    exact = "".join(
        '<td class="{cls}">{val:.1f}%</td>'.format(
            cls="hl" if i == last else "", val=v["exact_match"] * 100
        )
        for i, (_n, v) in enumerate(columns)
    )
    field_rows = ""
    for key, label in FIELDS:
        cells = "".join(
            '<td class="{cls}">{val:.3f}</td>'.format(
                cls="hl" if i == last else "", val=v["per_field"][key]
            )
            for i, (_n, v) in enumerate(columns)
        )
        field_rows += f"<tr><th>{esc(label)}</th>{cells}</tr>"
    return (
        f'<table class="grid"><thead><tr><th>Field</th>{head}</tr></thead>'
        f'<tbody><tr class="strong"><th>Exact match</th>{exact}</tr>{field_rows}</tbody></table>'
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default=None, help="run directory under evals/runs")
    args = parser.parse_args()

    run_dir = Path(args.run) if args.run else latest("*")
    if run_dir is None or not run_dir.exists():
        print("no saved run found")
        return 1

    h2h_path = run_dir / "head_to_head.json"
    summary_path = run_dir / "summary.json"

    if not h2h_path.exists():
        h2h_path = latest("*/head_to_head.json")
    if not summary_path.exists():
        summary_path = latest("*/summary.json")

    if h2h_path is None and summary_path is None:
        print("no run artifacts found; run scripts/head_to_head.py first")
        return 1

    h2h = json.loads(h2h_path.read_text(encoding="utf-8")) if h2h_path else {}
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path else {}

    rows = h2h.get("dataset_rows") or summary.get("extractors", {}).get("gemma_synthetic", {}).get(
        "num_samples", 0
    )
    regex_score = h2h.get("regex") or {}
    base_score = h2h.get("base_model_no_adapter") or {}
    lora_score = h2h.get("open_model") or {}
    winners = h2h.get("winner_counts", {})
    disagreements = h2h.get("disagreements", [])

    columns = []
    if regex_score:
        columns.append(("Regex (on device)", regex_score))
    if base_score:
        columns.append(("Qwen2.5-3B, no adapter", base_score))
    if lora_score:
        columns.append(("Qwen2.5-3B + LoRA", lora_score))

    series, colors = [], []
    if regex_score:
        series.append("regex")
        colors.append(COLORS["regex"])
    if base_score:
        series.append("no adapter")
        colors.append(COLORS["base"])
    if lora_score:
        series.append("+ LoRA")
        colors.append(COLORS["lora"])

    values_for_bars = []
    for i, _c in enumerate(columns):
        values_for_bars.append(regex_score if i == 0 else (base_score if i == 1 else lora_score))
    named = [(n, v) for n, v in zip(series, values_for_bars) if v]

    model_rows = ""
    for entry in disagreements[:14]:
        winner = entry["winner"]
        badge = "model" if winner == "model" else "regex"
        g = entry["gold"]
        model_rows += (
            f'<tr><td class="msg">{esc(entry["text"])}</td>'
            f"<td><code>{esc(g['meal'])}</code> {g['qty']} <code>{esc(g['action'])}</code>"
            f"{(' ' + esc(', '.join(g['mods']))) if g['mods'] else ''}</td>"
            f'<td class="{badge}">{"open model" if winner == "model" else "regex"}</td></tr>'
        )

    delta = ""
    if regex_score and lora_score:
        diff = (lora_score["exact_match"] - regex_score["exact_match"]) * 100
        delta = f"{diff:+.1f}"

    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TiffinTally — measured results</title>
<style>
  :root {{
    --ink:#0f172a; --muted:#64748b; --line:#e2e8f0; --bg:#f8fafc;
    --regex:{COLORS["regex"]}; --base:{COLORS["base"]}; --lora:{COLORS["lora"]};
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }}
  .wrap {{ max-width:1120px; margin:0 auto; padding:32px 20px 64px; }}
  h1 {{ font-size:1.7rem; margin:0 0 4px; letter-spacing:-.02em; }}
  h2 {{ font-size:1.05rem; margin:0 0 14px; letter-spacing:.01em; }}
  .sub {{ color:var(--muted); margin:0 0 4px; }}
  .paths {{ color:var(--muted); font:12px/1.7 ui-monospace,Menlo,monospace;
    background:#fff; border:1px solid var(--line); border-radius:8px;
    padding:10px 12px; margin:16px 0 24px; overflow-x:auto; }}
  .paths b {{ color:var(--ink); font-weight:600; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr));
    gap:12px; margin-bottom:24px; }}
  .card {{ background:#fff; border:1px solid var(--line); border-radius:10px;
    padding:14px 16px; }}
  .card .k {{ font-size:.72rem; letter-spacing:.08em; text-transform:uppercase;
    color:var(--muted); }}
  .card .v {{ font-size:1.9rem; font-weight:700; margin-top:2px; }}
  .card .d {{ font-size:.8rem; color:var(--muted); }}
  .good {{ color:var(--lora); }} .bad {{ color:#b91c1c; }}
  .panel {{ background:#fff; border:1px solid var(--line); border-radius:12px;
    padding:20px 22px; margin-bottom:20px; }}
  table {{ width:100%; border-collapse:collapse; font-size:.9rem; }}
  th, td {{ text-align:left; padding:7px 10px; border-bottom:1px solid var(--line); }}
  thead th {{ font-size:.72rem; letter-spacing:.06em; text-transform:uppercase;
    color:var(--muted); }}
  td.hl {{ background:#eff6ff; font-weight:600; }}
  tr.strong td.hl {{ font-weight:700; }}
  .grid tbody th {{ font-weight:500; color:var(--muted); width:34%; }}
  .legend {{ display:flex; gap:16px; flex-wrap:wrap; margin-bottom:14px; font-size:.85rem; }}
  .key {{ display:inline-flex; align-items:center; gap:6px; color:var(--muted); }}
  .key i {{ width:10px; height:10px; border-radius:2px; display:inline-block; }}
  .group {{ display:grid; grid-template-columns:140px 1fr; gap:4px 12px;
    padding:9px 0; border-top:1px solid var(--line); }}
  .glabel {{ font-weight:600; font-size:.9rem; }}
  .barrow {{ display:flex; align-items:center; gap:10px; }}
  .barlabel {{ font:12px ui-monospace,Menlo,monospace; color:var(--muted); width:78px; }}
  .bar {{ display:block; }}
  .split {{ display:grid; grid-template-columns:180px 1fr; gap:24px; align-items:start; }}
  .msg {{ max-width:320px; }}
  code {{ font:12px ui-monospace,Menlo,monospace; background:#f1f5f9;
    padding:1px 5px; border-radius:4px; }}
  .model {{ color:var(--lora); font-weight:600; }}
  .regex {{ color:var(--regex); font-weight:600; }}
  .note {{ background:#fffbeb; border:1px solid #fde68a; border-radius:8px;
    padding:12px 14px; font-size:.86rem; color:#78350f; }}
  .foot {{ color:var(--muted); font-size:.8rem; margin-top:24px; }}
</style></head>
<body><div class="wrap">

<h1>TiffinTally — what the open model actually scored</h1>
<p class="sub">Frozen test split, {
        rows
    } labelled messages, measured against the served endpoint on Modal.</p>

<div class="paths">
  <b>head to head</b> {
        esc(h2h_path.as_posix().replace(str(ROOT) + "/", "") if h2h_path else "not run")
    }<br>
  <b>eval suite</b> {
        esc(summary_path.as_posix().replace(str(ROOT) + "/", "") if summary_path else "not run")
    }<br>
  <b>model</b> {
        esc(
            h2h.get(
                "model",
                summary.get("extractors", {})
                .get("gemma_synthetic", {})
                .get("model_name", "unknown"),
            )
        )
    }
  on {esc(h2h.get("gpu", ""))}<br>
  <b>measured</b> {esc(h2h.get("date_ist", ""))}
</div>

<div class="cards">
  <div class="card"><div class="k">Open model, exact match</div>
    <div class="v">{
        esc(f"{lora_score.get('exact_match', 0) * 100:.1f}%" if lora_score else "NOT RUN")
    }</div>
    <div class="d">{esc(h2h.get("model", "Qwen2.5-3B + LoRA"))}</div></div>
  <div class="card"><div class="k">Regex, exact match</div>
    <div class="v">{
        esc(f"{regex_score.get('exact_match', 0) * 100:.1f}%" if regex_score else "NOT RUN")
    }</div>
    <div class="d">on device, no model call</div></div>
  <div class="card"><div class="k">Difference</div>
    <div class="v {"good" if delta.startswith("+") else "bad"}">{esc(delta or "n/a")}</div>
    <div class="d">percentage points, exact match</div></div>
  <div class="card"><div class="k">Rows where they differ</div>
    <div class="v">{esc(str(len(disagreements)))}</div>
    <div class="d">{esc(str(winners.get("model", 0)))} model · {
        esc(str(winners.get("regex", 0)))
    } regex</div></div>
</div>

<div class="panel">
  <h2>Field accuracy</h2>
  {score_table(columns) if columns else "<p>No extractor run recorded.</p>"}
</div>

<div class="panel">
  <h2>Same numbers, drawn</h2>
  {grouped_bars(named, colors)}
</div>

<div class="panel">
  <h2>Where they disagree</h2>
  <div class="split">
    {
        donut(
            [
                ("Open model", winners.get("model", 0), COLORS["lora"]),
                ("Regex", winners.get("regex", 0), COLORS["regex"]),
            ]
        )
    }
    <div>
      <table>
        <thead><tr><th>Message</th><th>Expected</th><th>Right</th></tr></thead>
        <tbody>{model_rows or '<tr><td colspan="3">No disagreements in this run.</td></tr>'}</tbody>
      </table>
    </div>
  </div>
</div>

<div class="panel">
  <h2>Read this before quoting a number</h2>
  <div class="note">
    <p style="margin:0 0 8px">Every figure above is on the <b>frozen synthetic split</b>
    (<code>data/synthetic/test.jsonl</code>). No cook has supplied real messages yet, so the
    held-out section of the eval report reads <code>NOT RUN</code> and stays that way until
    real messages are collected.</p>
    <p style="margin:0">The "no adapter" column is the same model on the same prompt with the
    fine-tune removed. It is the control: the base model scores
    {esc(f"{base_score.get('exact_match', 0) * 100:.1f}%" if base_score else "n/a")},
    the adapter lifts it to
    {esc(f"{lora_score.get('exact_match', 0) * 100:.1f}%" if lora_score else "n/a")}.
    That gap is the fine-tune's contribution, measured rather than asserted.</p>
  </div>
</div>

<p class="foot">Generated by <code>scripts/build_dashboard.py</code> from the run artifacts listed
above. Nothing on this page is recomputed from the model.</p>

</div></body></html>"""

    OUT.write_text(doc, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
