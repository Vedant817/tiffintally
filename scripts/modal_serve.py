"""
Serve the fine-tuned extractor as a web endpoint on Modal.

This is the "open model at the core" piece. Without it the app is a regex, and
the regex scored 88% on the frozen test split against the adapter's 84% - so
without a served model the contest rule about open-weight AI at the core is not
met and the post's "why open matters" section has nothing behind it.

Base model: Qwen2.5-3B-Instruct (Apache-2.0 weights)
Adapter:    /vol/checkpoints/iteration_N, trained on data/synthetic/train.jsonl

Deploy:
    modal deploy scripts/modal_serve.py

Then point the app at the printed URL:
    MODAL_EXTRACTOR_URL=https://<app>--tiffintally-extract.modal.run

The endpoint takes pseudonymised text. Names, phone numbers and flat numbers are
replaced with tokens by tiffintally/privacy.py before a request leaves the
machine, so customer identities never reach this container.
"""

import json
import os
import re

import modal

APP_NAME = os.getenv("MODAL_APP_NAME", "tiffintally-extract")
ADAPTER_ITERATION = os.getenv("MODAL_ADAPTER_ITERATION", "31")
BASE_MODEL = os.getenv("MODAL_BASE_MODEL", "Qwen/Qwen2.5-3B-Instruct")

app = modal.App(APP_NAME)
volume = modal.Volume.from_name("tiffintally-models", create_if_missing=True)

# Qwen2.5-3B-Instruct weights are public, so no Hugging Face token is needed and
# the deployment has no secret to leak.
# The app package is baked into the image for one reason: the adapter was
# fine-tuned against tiffintally.extract.base.SYSTEM_PROMPT. Without the package
# in the image that import fails and a three-word fallback prompt is served
# instead, which scored 24% exact match against the regex's 78%. That measured
# the wrong prompt, not the model.
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "torch==2.5.1",
        "transformers==4.46.3",
        "peft==0.13.2",
        "accelerate>=1.1.0",
        "fastapi[standard]==0.115.4",
        "pydantic>=2.9",
    )
    .add_local_python_source("tiffintally")
)

# The real prompt is eleven numbered rules. Anything shorter means the import
# failed, and the run would silently measure the wrong thing.
MIN_SYSTEM_PROMPT_CHARS = 500

SYSTEM_PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tiffintally",
    "extract",
    "base.py",
)

VALID_ACTIONS = {"new", "change", "add", "cancel", "pause", "payment", "none"}
VALID_MEALS = {"lunch", "dinner", "both", "unspecified"}


@app.function(
    image=image,
    gpu="A10G",
    timeout=600,
    scaledown_window=300,
    volumes={"/vol": volume},
)
def extract_batch(
    payload: dict,
    adapter_iteration: str = ADAPTER_ITERATION,
    base_model: str = BASE_MODEL,
) -> dict:
    """Batched extraction. One HTTP round trip per <=40 messages."""
    import sys
    import time

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    # The adapter was trained against the app's own prompt, so the same prompt
    # has to be served. A silent fallback here would score the fallback, not the
    # model, and the number would look like a property of the checkpoint.
    sys.path.insert(0, "/root")
    try:
        from tiffintally.extract.base import SYSTEM_PROMPT
    except Exception as exc:  # pragma: no cover - fails the deployment instead
        raise RuntimeError(
            "tiffintally.extract.base.SYSTEM_PROMPT did not load from the image. "
            "The adapter must be served with the prompt it was trained on."
        ) from exc
    if len(SYSTEM_PROMPT) < MIN_SYSTEM_PROMPT_CHARS:
        raise RuntimeError(
            f"SYSTEM_PROMPT is only {len(SYSTEM_PROMPT)} chars; expected the full "
            "rule set. Refusing to serve a different prompt than training used."
        )

    use_adapter = bool(payload.get("use_adapter", True))
    adapter_path = f"/vol/checkpoints/iteration_{adapter_iteration}"
    if use_adapter and not os.path.isdir(adapter_path):
        return {"error": f"no adapter at {adapter_path}", "results": []}

    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    tokenizer_source = adapter_path if use_adapter else base_model
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_source)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=dtype,
        device_map="auto",
        attn_implementation="sdpa",
    )
    if use_adapter:
        model = PeftModel.from_pretrained(model, adapter_path)
        served_model = f"{base_model}+lora-iteration_{adapter_iteration}"
    else:
        # The control: the same prompt and the same parser, with no adapter.
        served_model = f"{base_model} (no adapter)"
    model.eval()

    messages = payload.get("messages") or []
    results = []
    raws = []
    latencies = []
    repaired_total = 0

    prompts = []
    for item in messages:
        sender = item.get("sender", "Customer")
        text = item.get("text", "")
        chat = [
            {"role": "system", "content": SYSTEM_PROMPT.strip()},
            {"role": "user", "content": f"Sender: {sender}\nMessage: {text}"},
        ]
        prompts.append(
            tokenizer.apply_chat_template(chat, tokenize=False, add_generation_prompt=True)
        )

    # One forward pass per batch, not per message. Generating message by message
    # took ~6 s each, so a 20-message paste hit the endpoint's 120 s timeout and
    # the whole request came back as a 500.
    tokenizer.padding_side = "left"
    if not prompts:
        return {
            "model": served_model,
            "system_prompt_chars": len(SYSTEM_PROMPT),
            "results": [],
            "raw": [],
            "count": 0,
            "empty_results": 0,
            "repaired_blocks": 0,
            "latency_p50_ms": 0.0,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
        }

    started = time.perf_counter()
    inputs = tokenizer(prompts, return_tensors="pt", padding=True).to(model.device)
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=160,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    latencies.append((time.perf_counter() - started) * 1000)

    generated = out[:, inputs["input_ids"].shape[1] :]
    decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)

    for raw in decoded:
        raw = raw.strip()
        events, fixed = _parse(raw)
        results.append(events)
        raws.append(raw[:400])
        repaired_total += fixed

    return {
        "model": served_model,
        "system_prompt_chars": len(SYSTEM_PROMPT),
        "results": results,
        "raw": raws,
        "count": len(results),
        "empty_results": sum(1 for r in results if not r),
        "repaired_blocks": repaired_total,
        "latency_p50_ms": round(sorted(latencies)[len(latencies) // 2], 1) if latencies else 0.0,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
    }


def _is_object_like_bracket(text: str, i: int) -> bool:
    """True when text[i] == "[" and what follows looks like a JSON object.

    The adapter emits `["customer": ...]` where `{` belongs. A genuine array
    such as `"mods": ["no onion"]` has no colon after its first element, so the
    two are distinguishable and real arrays are left alone.
    """
    j = i + 1
    while j < len(text) and text[j].isspace():
        j += 1
    if j >= len(text) or text[j] != '"':
        return False
    j += 1
    while j < len(text):
        if text[j] == "\\":
            j += 2
            continue
        if text[j] == '"':
            break
        j += 1
    j += 1
    while j < len(text) and text[j].isspace():
        j += 1
    return j < len(text) and text[j] == ":"


def _normalise_brackets(text: str) -> str:
    """Rewrite the adapter's `[`-as-`{` into valid JSON.

    One malformed event used to invalidate the whole reply, so a single bad
    bracket threw away every other event in the same message.
    """
    out = []
    stack = []  # True when the matching opener was object-like
    i = 0
    in_string = False
    escaped = False
    while i < len(text):
        ch = text[i]
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "{":
            stack.append(True)
            out.append(ch)
        elif ch == "[":
            object_like = _is_object_like_bracket(text, i)
            stack.append(object_like)
            out.append("{" if object_like else "[")
        elif ch in "]}":
            if stack:
                was_object = stack.pop()
                out.append("}" if (was_object and ch == "]") else ch)
            # A closer with nothing open is a leftover from the malformation.
        else:
            # Colons, commas, digits and spaces pass through untouched.
            out.append(ch)
        i += 1
    return "".join(out)


def _extract_objects(text: str) -> list:
    """Balanced `{...}` blocks, ignoring braces inside strings."""
    blocks = []
    depth = 0
    start = None
    in_string = False
    escaped = False
    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                blocks.append(text[start : i + 1])
                start = None
            if depth < 0:
                depth = 0
    return blocks


# An event object: no nested braces, but `mods` may be an array.
_EVENT_OBJECT = re.compile(r"\{[^{}]*(?:\[[^\[\]]*\][^{}]*)*\}", re.DOTALL)


def _clean_event(event) -> dict:
    action = str(event.get("action", "new"))
    meal = str(event.get("meal", "lunch"))
    try:
        qty = int(event.get("qty", 1))
    except (TypeError, ValueError):
        qty = 1
    mods = event.get("mods")
    if isinstance(mods, str):
        mods = [mods] if mods.strip() else []
    return {
        "customer": str(event.get("customer") or "Customer"),
        "date": str(event.get("date") or "unspecified"),
        "meal": meal if meal in VALID_MEALS else "unspecified",
        "qty": max(0, qty),
        "mods": [str(m) for m in (mods or [])],
        "action": action if action in VALID_ACTIONS else "new",
    }


def _parse(raw: str) -> tuple:
    """Model output to (events, repaired).

    `repaired` is returned rather than swallowed so a run can report how much of
    the model's output needed fixing before it was usable.
    """
    text = raw.strip()
    if "```" in text:
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()

    for candidate, repaired in ((text, 0), (_normalise_brackets(text), 1)):
        try:
            data = json.loads(candidate)
        except Exception:
            continue
        if isinstance(data, dict):
            return [
                _clean_event(e) for e in data.get("events", []) if isinstance(e, dict)
            ], repaired
        if isinstance(data, list):
            return [_clean_event(e) for e in data if isinstance(e, dict)], repaired

    # Salvage each event object on its own. One malformed event must not take
    # the rest of the message down with it, which is what json.loads on the whole
    # reply used to do.
    events = []
    for candidate in (text, _normalise_brackets(text)):
        for block in _EVENT_OBJECT.findall(candidate):
            if '"customer"' not in block:
                continue
            try:
                data = json.loads(block)
            except Exception:
                continue
            if isinstance(data, dict):
                events.append(_clean_event(data))
        if events:
            break

    return events, 1 if events else 0


@app.function(image=image, timeout=900, scaledown_window=300)
@modal.fastapi_endpoint(method="POST", docs=True)
def api(payload: dict) -> dict:
    """HTTP entry point used by tiffintally/extract/gemma.py."""
    return extract_batch.remote(payload)


@app.local_entrypoint()
def main(messages: str = "", iteration: str = ADAPTER_ITERATION):
    if messages:
        payload = json.loads(messages)
        print(json.dumps(extract_batch.remote(payload, adapter_iteration=iteration), indent=2))
    else:
        print("Deploy with: modal deploy scripts/modal_serve.py")
        print(f"Adapter iteration: {iteration}, base model: {BASE_MODEL}")
