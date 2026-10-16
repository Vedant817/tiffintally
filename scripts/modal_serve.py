"""
Serve the fine-tuned extractor as a web endpoint on Modal.

This is an experiment, not the product's default extractor. The product default
is the Gemini API path; see EXTRACTOR_BACKEND in tiffintally/extract/gemma.py.

LICENCE. Base model: Qwen/Qwen2.5-3B-Instruct. Its Hugging Face metadata reports
`license: other`, `license_name: qwen-research`, and the licence text is
"FOR NON-COMMERCIAL PURPOSES ONLY", with a duty to display "Built with Qwen" on
derived models. An earlier version of this file called the weights Apache-2.0;
that was wrong. Do not put this adapter on a paid product without a commercial
licence from Alibaba, and keep the "Built with Qwen" notice wherever the adapter
is described.

Adapter:    /vol/checkpoints/iteration_N, trained on data/synthetic/train.jsonl
            Held on a private Modal volume. It is not published anywhere a judge
            can fetch it, so "reproducible" is not a claim this repo makes yet.

Built with Qwen.

Deploy:
    modal secret create tiffintally-extract-token   # one-time, interactive
    modal deploy scripts/modal_serve.py

The endpoint requires `Authorization: Bearer <token>` on every call and answers
401 without it. The token lives in a Modal secret; it is never in this file.

Then point the app at the printed URL and the same token, both from the
environment only. There is no default URL in the code on purpose: a hard-coded
one left a paid GPU endpoint reachable by anyone who read the repo.
    MODAL_EXTRACTOR_URL=https://<app>--<fn>.modal.run
    MODAL_EXTRACTOR_TOKEN=<same value as the Modal secret>

The endpoint takes pseudonymised text. Names, phone numbers and flat numbers are
replaced with tokens by tiffintally/privacy.py before a request leaves the
machine, so customer identities never reach this container.
"""

import json
import os
import re

import modal
from fastapi import Header

APP_NAME = os.getenv("MODAL_APP_NAME", "tiffintally-extract")
ADAPTER_ITERATION = os.getenv("MODAL_ADAPTER_ITERATION", "31")
BASE_MODEL = os.getenv("MODAL_BASE_MODEL", "Qwen/Qwen2.5-3B-Instruct")

# The bearer token, created once with `modal secret create tiffintally-extract-token`.
TOKEN_SECRET = modal.Secret.from_name("tiffintally-extract-token")

app = modal.App(APP_NAME)
volume = modal.Volume.from_name("tiffintally-models", create_if_missing=True)

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

# ------------------------------------------------------------------ #
# Weights are loaded once per container, not once per request.
#
# Module-level globals persist across invocations inside one warm
# container, so a plain dict cache is enough to get load-once behaviour.
#
# This is deliberately not an @app.cls parameterized class. On Modal
# 1.6.1 `app.cls` is the decorator and `modal.cls` is a package submodule,
# so the class form raised "TypeError: 'module' object is not callable"
# at import and took the whole test suite's collection with it.
# @app.function is stable across versions.
# ------------------------------------------------------------------ #

_MODELS: dict = {}


def _get_model(use_adapter: bool) -> dict:
    """The loaded weights for this container, loading them at most once."""
    if use_adapter in _MODELS:
        return _MODELS[use_adapter]

    import sys

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    sys.path.insert(0, "/root")
    from tiffintally.extract.base import SYSTEM_PROMPT

    # The adapter was trained against the app's own prompt, so the same prompt
    # has to be served. A silent fallback would score the fallback rather than
    # the model, and the number would look like a property of the checkpoint.
    if len(SYSTEM_PROMPT) < MIN_SYSTEM_PROMPT_CHARS:
        raise RuntimeError(
            f"SYSTEM_PROMPT is only {len(SYSTEM_PROMPT)} chars; expected the full "
            "rule set. Refusing to serve a different prompt than training used."
        )

    adapter_path = f"/vol/checkpoints/iteration_{ADAPTER_ITERATION}"
    if use_adapter and not os.path.isdir(adapter_path):
        raise RuntimeError(
            f"no adapter at {adapter_path}. Train and save it to the volume first, "
            "or pass use_adapter=false for the no-adapter control."
        )

    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    tokenizer_source = adapter_path if use_adapter else BASE_MODEL

    tokenizer = AutoTokenizer.from_pretrained(tokenizer_source)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    # One forward pass per batch. Generating message by message took about 6 s
    # each, so a 20-message paste hit the endpoint timeout and came back a 500.
    tokenizer.padding_side = "left"

    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=dtype,
        device_map="auto",
        attn_implementation="sdpa",
    )
    if use_adapter:
        model = PeftModel.from_pretrained(model, adapter_path)
        served_model = f"{BASE_MODEL}+lora-iteration_{ADAPTER_ITERATION}"
    else:
        # The control: same prompt, same parser, no adapter.
        served_model = f"{BASE_MODEL} (no adapter)"
    model.eval()

    _MODELS[use_adapter] = {
        "model": model,
        "tokenizer": tokenizer,
        "system_prompt": SYSTEM_PROMPT,
        "served_model": served_model,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
    }
    return _MODELS[use_adapter]


def _generate(loaded: dict, prompts: list) -> list:
    """Batched greedy decode. One forward pass for the whole batch."""
    import torch

    model = loaded["model"]
    tokenizer = loaded["tokenizer"]
    inputs = tokenizer(prompts, return_tensors="pt", padding=True).to(model.device)
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=160,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    generated = out[:, inputs["input_ids"].shape[1] :]
    return [text.strip() for text in tokenizer.batch_decode(generated, skip_special_tokens=True)]


def check_bearer(headers) -> None:
    """401 unless the request carries the token from the Modal secret.

    The endpoint costs GPU credit per call. An unauthenticated one lets anyone
    who reads the repo run inference on the owner's account.
    """
    import secrets as _secrets

    from fastapi import HTTPException

    expected = os.environ.get("TIFFINTALLY_EXTRACT_TOKEN", "")
    provided = ""
    if headers:
        raw = headers.get("authorization") or headers.get("Authorization") or ""
        if raw.lower().startswith("bearer "):
            provided = raw[7:].strip()

    if not expected:
        # 503, not 401: the deployment is misconfigured rather than the caller
        # being wrong. Either way this is not retryable, and tiffintally/extract/
        # gemma.py treats 401/403 as terminal so it stops instead of spending a
        # second GPU call re-sending a token that can never be accepted.
        raise HTTPException(
            status_code=503,
            detail=(
                "TIFFINTALLY_EXTRACT_TOKEN is not set on the deployment. Create "
                "the Modal secret 'tiffintally-extract-token' and redeploy; the "
                "endpoint must not run unauthenticated."
            ),
        )
    if not provided or not _secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=401,
            detail="unauthorized: send Authorization: Bearer <token>",
        )


def _build_payload(messages: list, system_prompt: str, tokenizer) -> list:
    prompts = []
    for item in messages:
        chat = [
            {"role": "system", "content": system_prompt.strip()},
            {
                "role": "user",
                "content": f"Sender: {item.get('sender', 'Customer')}\n"
                f"Message: {item.get('text', '')}",
            },
        ]
        prompts.append(
            tokenizer.apply_chat_template(chat, tokenize=False, add_generation_prompt=True)
        )
    return prompts


@app.function(
    image=image,
    gpu="A10G",
    timeout=900,
    scaledown_window=300,
    volumes={"/vol": volume},
    secrets=[TOKEN_SECRET],
)
@modal.fastapi_endpoint(method="POST", docs=False)
def api(payload: dict, authorization: str = Header(default="")) -> dict:
    """Authenticated batched extraction. One HTTP round trip per <=40 messages.

    `Header` is not decoration. Modal builds the route from this signature, and
    a bare `authorization: str = ""` becomes a *query* parameter, so the token
    would arrive as `?authorization=...` and be written to Modal's access logs.
    Declaring it as a header keeps the secret out of the URL.
    """
    import time

    check_bearer({"authorization": authorization})

    messages = payload.get("messages") or []
    use_adapter = bool(payload.get("use_adapter", True))
    loaded = _get_model(use_adapter)

    empty = {
        "model": loaded["served_model"],
        "system_prompt_chars": len(loaded["system_prompt"]),
        "results": [],
        "raw": [],
        "count": 0,
        "empty_results": 0,
        "repaired_blocks": 0,
        "latency_p50_ms": 0.0,
        "gpu": loaded["gpu"],
    }
    if not messages:
        return empty

    prompts = _build_payload(messages, loaded["system_prompt"], loaded["tokenizer"])
    started = time.perf_counter()
    decoded = _generate(loaded, prompts)
    elapsed_ms = (time.perf_counter() - started) * 1000

    results, raws, repaired_total = [], [], 0
    for raw in decoded:
        events, fixed = _parse(raw)
        results.append(events)
        raws.append(raw[:400])
        repaired_total += fixed

    return {
        "model": loaded["served_model"],
        "system_prompt_chars": len(loaded["system_prompt"]),
        "results": results,
        "raw": raws,
        "count": len(results),
        "empty_results": sum(1 for r in results if not r),
        "repaired_blocks": repaired_total,
        "latency_p50_ms": round(elapsed_ms, 1),
        "gpu": loaded["gpu"],
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
    from tiffintally.model_validation import clean_model_event

    return clean_model_event(event)


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
            try:
                data = json.loads(block)
            except Exception:
                continue
            if isinstance(data, dict):
                events.append(_clean_event(data))
        if events:
            break

    return events, 1 if events else 0


@app.local_entrypoint()
def main():
    print("This app serves over HTTP only. Deploy with:")
    print("    modal secret create tiffintally-extract-token")
    print("    modal deploy scripts/modal_serve.py")
    print()
    print(f"Adapter iteration: {ADAPTER_ITERATION}, base model: {BASE_MODEL}")
    print("Licence: the Qwen2.5-3B base is non-commercial (qwen-research).")
    print("Built with Qwen.")
