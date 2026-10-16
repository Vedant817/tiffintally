"""FastAPI application for TiffinTally.

Serves a mobile-friendly kitchen UI, printable prep sheets, the dues ledger,
voice briefs, and the active-learning correction flywheel.
Backstopped by durable ACID SQLite persistence for zero data loss.
"""

import asyncio
import csv
import io
import json
import os
import time as time_mod
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, time
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path
from threading import RLock
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from tiffintally.benchmarks import STANDARD_BENCHMARK_SUITES, evaluate_and_heal_loop
from tiffintally.db import load_kitchen_events, persist_correction, persist_upload_and_events
from tiffintally.extract.gemma import GemmaExtractor
from tiffintally.feedback import ActiveLearningManager, CorrectionEntry
from tiffintally.logging_config import get_logger, log_failure, setup_logging
from tiffintally.parser import parse_chat_export
from tiffintally.reconcile import (
    money,
    payment_id,
    payment_is_safe,
    reconcile_ledger,
    reconcile_orders,
)
from tiffintally.schema import DailyPrepSheet, OrderEvent
from tiffintally.transcribe import VoiceNoteTranscriber
from tiffintally.uploads import (
    MAX_UPLOAD_BYTES,
    UploadRejected,
    check_paste_size,
    decode_chat_upload,
)
from tiffintally.voice import VoiceBriefResult, VoiceBriefService

setup_logging()
logger = get_logger("app")

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
CORRECTIONS_FILE = Path("data/private/corrections.jsonl")

SESSION_COOKIE = "tt_sid"

# A cook exports once a night. Two hours idle is generous for that.
SESSION_IDLE_SECONDS = int(os.getenv("SESSION_IDLE_SECONDS", str(2 * 60 * 60)))
MAX_SESSIONS = max(1, int(os.getenv("MAX_SESSIONS", "500")))


def demo_mode() -> bool:
    """True on a public deployment, where nothing may be written to disk."""
    return os.getenv("TIFFINTALLY_DEMO_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class KitchenSession:
    """One browser's kitchen. Not shared with other visitors."""

    sid: str
    sheet: Optional[DailyPrepSheet] = None
    events: list[OrderEvent] = field(default_factory=list)
    voice_brief: Optional[VoiceBriefResult] = None
    extractor_label: str = "no chat loaded"
    used_fallback: bool = True
    model_messages: int = 0
    fallback_messages: int = 0
    extractor_notes: list = field(default_factory=list)
    accept_late_cancels: bool = False
    confirmed_payments: set[str] = field(default_factory=set)
    price_per_thali: Decimal = Decimal("80.00")
    previous_balances: dict[str, Decimal] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)
    cook_names: list[str] = field(default_factory=list)
    cutoff: time = field(default_factory=lambda: time(22, 0))
    touched: datetime = field(default_factory=datetime.now)


SESSIONS: dict[str, KitchenSession] = {}
SESSION_LOCK = RLock()


class CorrectionPayload(BaseModel):
    customer: str
    raw_text: str
    corrected_meal: str
    corrected_qty: int
    corrected_action: str


def _prune_sessions(now: datetime) -> None:
    """Evict idle sessions.

    SESSIONS grew without bound: 2,000 cookieless GETs left 2,001 entries, each
    holding a sheet, on a free-tier process.
    """
    stale = [
        sid
        for sid, session in SESSIONS.items()
        if (now - session.touched).total_seconds() > SESSION_IDLE_SECONDS
    ]
    for sid in stale:
        SESSIONS.pop(sid, None)


def _open_session(request: Request) -> tuple[KitchenSession, bool]:
    now = datetime.now()
    _prune_sessions(now)
    sid = request.cookies.get(SESSION_COOKIE)
    if sid and sid in SESSIONS:
        SESSIONS[sid].touched = now
        return SESSIONS[sid], False
    if sid:
        try:
            stored_events = load_kitchen_events(sid)
            if stored_events:
                session = KitchenSession(sid=sid, touched=now)
                SESSIONS[sid] = session
                fill_session(
                    session,
                    events=stored_events,
                    target_date="tomorrow",
                    cutoff_t=time(22, 0),
                    extractor_label="restored from database",
                    used_fallback=True,
                )
                return session, False
        except Exception as exc:
            logger.debug(f"Session {sid} not in database: {exc}")

    sid = uuid.uuid4().hex
    while len(SESSIONS) >= MAX_SESSIONS:
        oldest = min(SESSIONS, key=lambda key: SESSIONS[key].touched)
        SESSIONS.pop(oldest)
    session = KitchenSession(sid=sid, touched=now)
    SESSIONS[sid] = session
    return session, True


def open_session(request: Request) -> tuple[KitchenSession, bool]:
    with SESSION_LOCK:
        return _open_session(request)


def remember_cookie(response, session: KitchenSession, is_new: bool):
    if is_new:
        response.set_cookie(SESSION_COOKIE, session.sid, httponly=True, samesite="lax")
    return response


def fill_session(
    session: KitchenSession,
    events: list[OrderEvent],
    target_date: str,
    cutoff_t: time,
    extractor_label: str,
    used_fallback: bool,
    model_messages: int = 0,
    fallback_messages: int = 0,
    extractor_notes: Optional[list] = None,
) -> None:
    """Build the sheet from this cook's events only. Standing orders default to empty."""
    session.events = events
    session.extractor_label = extractor_label
    session.used_fallback = used_fallback
    session.model_messages = model_messages
    session.fallback_messages = fallback_messages
    session.extractor_notes = list(extractor_notes or [])
    session.cutoff = cutoff_t
    session.sheet = reconcile_orders(
        events=events,
        target_date=target_date,
        cutoff_time=cutoff_t,
        standing_orders=None,
        cook_names=session.cook_names,
        accept_late_cancels=session.accept_late_cancels,
    )
    session.voice_brief = VoiceBriefService(session_id=session.sid).generate_morning_brief(
        session.sheet
    )


def ensure_empty(session: KitchenSession) -> None:
    if session.sheet is None:
        fill_session(
            session,
            events=[],
            target_date="tomorrow",
            cutoff_t=time(22, 0),
            extractor_label="rules (regex)",
            used_fallback=True,
        )


def sheet_context(session: KitchenSession) -> dict:
    return {
        "sheet": session.sheet,
        "voice_brief": session.voice_brief,
        "extractor_label": session.extractor_label,
        "used_fallback": session.used_fallback,
        "model_messages": session.model_messages,
        "fallback_messages": session.fallback_messages,
        "extractor_notes": session.extractor_notes,
        "cook_names": session.cook_names,
        "accept_late_cancels": session.accept_late_cancels,
        "current_time": datetime.now().strftime("%I:%M %p, %d %b %Y"),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Do not seed fictional customers into a process-wide sheet.
    yield


app = FastAPI(
    title="TiffinTally",
    description="Your WhatsApp orders, sorted before the pressure cooker's first whistle.",
    version=version("tiffintally"),
    lifespan=lifespan,
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time_mod.perf_counter()
    method = request.method
    path = request.url.path
    client_ip = request.client.host if request.client else "unknown"
    sid = request.cookies.get(SESSION_COOKIE, "-")

    try:
        response = await call_next(request)
        duration_ms = (time_mod.perf_counter() - start_time) * 1000.0
        status = response.status_code
        if status >= 400:
            logger.warning(
                f"HTTP {status} {method} {path} [{sid}] from {client_ip} in {duration_ms:.1f}ms"
            )
        else:
            logger.info(
                f"HTTP {status} {method} {path} [{sid}] from {client_ip} in {duration_ms:.1f}ms"
            )
        return response
    except Exception as exc:
        duration_ms = (time_mod.perf_counter() - start_time) * 1000.0
        log_failure(
            "UNHANDLED_EXCEPTION",
            f"Unhandled error processing {method} {path} [{sid}] in {duration_ms:.1f}ms",
            exc=exc,
            extra={"method": method, "path": path, "client_ip": client_ip},
        )
        raise


@app.middleware("http")
async def reject_oversized_bodies(request: Request, call_next):
    """Refuse a huge body before it is parsed.

    Starlette's form parser reads the whole multipart body first, so a 21 MB
    paste was rejected as a 400 *after* the server had already spent the memory
    and the seconds. Check Content-Length first and answer 413 immediately.
    """
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_UPLOAD_BYTES:
        return JSONResponse(
            status_code=413,
            content={
                "detail": (
                    f"That upload is {int(declared) // (1024 * 1024)} MB. Export one chat "
                    f"at a time; the limit is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
                )
            },
        )
    return await call_next(request)


@app.get("/health")
def health_check():
    """Liveness only. Feature lists belong in the README, not a health check."""
    return {"status": "ok", "version": app.version}


@app.get("/", response_class=HTMLResponse)
def index_view(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "default_cutoff": "22:00",
            "demo_messages": json.loads(
                (BASE_DIR / "demo_sample.json").read_text(encoding="utf-8")
            ),
        },
    )


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Return 204 No Content to silence browser favicon 404 warnings."""
    return Response(status_code=204)


@app.get("/process")
def process_get(request: Request):
    """Gracefully redirect GET /process to /prep or home page."""
    session, is_new = open_session(request)
    target = (
        "/prep"
        if session.sheet and (session.sheet.total_thalis > 0 or session.sheet.packing_labels)
        else "/"
    )
    return remember_cookie(RedirectResponse(url=target, status_code=303), session, is_new)


@app.post("/process", response_class=HTMLResponse)
async def process(
    request: Request,
    chat_file: Optional[UploadFile] = None,
    raw_text: Optional[str] = Form(None),
    target_date: str = Form("tomorrow"),
    cutoff: str = Form("22:00"),
    cook_names: Optional[str] = Form(None),
    price_per_thali: Decimal = Form(Decimal("80.00"), gt=0, le=10000),
):
    session, is_new = open_session(request)

    if cook_names is not None:
        session.cook_names = [n.strip() for n in cook_names.split(",") if n.strip()]

    content = ""
    if chat_file and chat_file.filename:
        try:
            content = decode_chat_upload(await chat_file.read(), chat_file.filename)
        except UploadRejected as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
    elif raw_text:
        ok, reason = check_paste_size(raw_text)
        if not ok:
            raise HTTPException(status_code=413, detail=reason)
        content = raw_text

    parsed_msgs = parse_chat_export(content) if content.strip() else []
    session.confirmed_payments.clear()
    session.accept_late_cancels = False
    extractor = GemmaExtractor()

    # Offload extraction from ASGI loop to worker thread
    batch = (
        await asyncio.to_thread(extractor.extract_batch_counted, parsed_msgs)
        if parsed_msgs
        else None
    )
    events = batch.events if batch else []
    session.price_per_thali = money(price_per_thali)
    for event in events:
        event.customer = session.aliases.get(event.customer.lower(), event.customer)

    # Durably persist chat upload and events to SQLite
    if events or (content and content.strip()):
        try:
            persist_upload_and_events(
                kitchen_id=session.sid,
                raw_text=content,
                filename=chat_file.filename if chat_file else None,
                events=events,
            )
        except Exception as exc:
            logger.warning(f"Durable database persistence failed: {exc}")

    # The label is whatever a response said, or "rules (regex)".
    label = batch.model_name if batch else "rules (regex)"
    model_messages = batch.model_messages if batch else 0
    fallback_messages = batch.fallback_messages if batch else 0
    used_fallback = model_messages == 0
    extractor_notes = list(batch.errors) if batch else []

    try:
        parts = cutoff.split(":")
        cutoff_t = time(int(parts[0]), int(parts[1]))
    except Exception:
        cutoff_t = time(22, 0)

    fill_session(
        session,
        events=events,
        target_date=target_date,
        cutoff_t=cutoff_t,
        extractor_label=label,
        used_fallback=used_fallback,
        model_messages=model_messages,
        fallback_messages=fallback_messages,
        extractor_notes=extractor_notes,
    )

    response = templates.TemplateResponse(
        request=request,
        name="prep_sheet.html",
        context=sheet_context(session),
    )
    return remember_cookie(response, session, is_new)


@app.post("/api/late-cancels/accept")
def accept_late_cancels(request: Request):
    """One tap on "−N if you accept". Only the cook knows if she has packed."""
    session, is_new = open_session(request)
    ensure_empty(session)
    session.accept_late_cancels = True
    fill_session(
        session,
        events=session.events,
        target_date=session.sheet.date,
        cutoff_t=session.cutoff,
        extractor_label=session.extractor_label,
        used_fallback=session.used_fallback,
        model_messages=session.model_messages,
        fallback_messages=session.fallback_messages,
        extractor_notes=session.extractor_notes,
    )
    if "text/html" in request.headers.get("accept", ""):
        response = RedirectResponse(url="/prep", status_code=303)
    else:
        response = JSONResponse({"status": "accepted", "total_thalis": session.sheet.total_thalis})
    return remember_cookie(response, session, is_new)


@app.get("/api/late-cancels/accept")
def accept_late_cancels_get(request: Request):
    """Gracefully redirect GET /api/late-cancels/accept to the prep sheet."""
    return RedirectResponse(url="/prep", status_code=303)


@app.get("/prep", response_class=HTMLResponse)
def view_prep_sheet(request: Request):
    session, is_new = open_session(request)
    ensure_empty(session)
    response = templates.TemplateResponse(
        request=request,
        name="prep_sheet.html",
        context=sheet_context(session),
    )
    return remember_cookie(response, session, is_new)


@app.get("/ledger", response_class=HTMLResponse)
def view_ledger(request: Request):
    session, is_new = open_session(request)
    ensure_empty(session)

    ledger = session_ledger(session)

    response = templates.TemplateResponse(
        request=request,
        name="ledger.html",
        context={
            "ledger": ledger,
            "alias_suggestions": alias_suggestions(session),
            "unresolved_events": [ev for ev in session.events if ev.needs_review],
            "blocked_payments": [
                ev for ev in session.events if ev.action == "payment" and not payment_is_safe(ev)
            ],
            "claimed_payments": [
                {"id": payment_id(ev), "event": ev}
                for ev in session.events
                if payment_is_safe(ev) and payment_id(ev) not in session.confirmed_payments
            ],
        },
    )
    return remember_cookie(response, session, is_new)


def session_ledger(session: KitchenSession):
    return reconcile_ledger(
        session.events,
        price_per_thali=session.price_per_thali,
        previous_balances=session.previous_balances,
        confirmed_payments=session.confirmed_payments,
        cutoff_time=session.cutoff,
        cook_names=session.cook_names,
        accept_late_cancels=session.accept_late_cancels,
    )


def alias_suggestions(session: KitchenSession):
    names = sorted({event.customer for event in session.events})
    return [
        (short, long)
        for short in names
        for long in names
        if short != long and " " not in short and long.lower().startswith(short.lower() + " ")
    ]


@app.post("/api/aliases/confirm")
def confirm_alias(request: Request, source: str = Form(...), target: str = Form(...)):
    session, is_new = open_session(request)
    if (source, target) not in alias_suggestions(session):
        raise HTTPException(status_code=400, detail="No matching alias suggestion")
    session.aliases[source.lower()] = target
    for event in session.events:
        if event.customer == source:
            event.customer = target
        if event.secondary_customer == source:
            event.secondary_customer = target
    session.confirmed_payments.clear()
    fill_session(
        session,
        session.events,
        session.sheet.date,
        session.cutoff,
        session.extractor_label,
        session.used_fallback,
        session.model_messages,
        session.fallback_messages,
        session.extractor_notes,
    )
    return remember_cookie(JSONResponse({"status": "merged"}), session, is_new)


@app.get("/ledger/balances.csv")
def export_balances(request: Request):
    session, is_new = open_session(request)
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["customer", "balance"])
    for entry in session_ledger(session).values():
        writer.writerow([entry.customer, f"{entry.balance_due:.2f}"])
    return remember_cookie(
        Response(
            stream.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=balances.csv"},
        ),
        session,
        is_new,
    )


@app.post("/ledger/balances")
async def import_balances(request: Request, balance_file: UploadFile):
    session, is_new = open_session(request)
    raw = await balance_file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Balance CSV too large")
    try:
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
        balances = {}
        for row in rows:
            name = row["customer"].strip()
            if not name or name.lower() in balances:
                raise ValueError("Empty or duplicate customer")
            balances[name.lower()] = money(row["balance"])
    except (ValueError, KeyError, ArithmeticError) as exc:
        raise HTTPException(status_code=400, detail="Invalid customer,balance CSV") from exc
    session.previous_balances = balances
    return remember_cookie(
        JSONResponse({"status": "imported", "customers": len(balances)}), session, is_new
    )


@app.post("/api/payments/{event_id}/confirm")
def confirm_payment(request: Request, event_id: str):
    session, is_new = open_session(request)
    if not any(payment_id(ev) == event_id and payment_is_safe(ev) for ev in session.events):
        raise HTTPException(status_code=404, detail="No eligible payment in this session")
    session.confirmed_payments.add(event_id)
    return remember_cookie(JSONResponse({"status": "confirmed"}), session, is_new)


@app.get("/api/audio/morning_brief")
def get_morning_brief_audio(request: Request):
    session, _is_new = open_session(request)
    ensure_empty(session)
    if session.voice_brief and session.voice_brief.audio_path:
        p = Path(session.voice_brief.audio_path)
        if p.exists():
            return FileResponse(p, media_type="audio/mpeg")
    raise HTTPException(status_code=404, detail="Audio brief not generated or cached")


_CORRECTION_MEALS = {"lunch", "dinner", "both"}
_CORRECTION_ACTIONS = {"new", "change", "cancel"}
_CLEARED_FLAGS = {"date_unresolved", "date_range", "unparsed_timestamp"}


def apply_correction(session: KitchenSession, payload: CorrectionPayload) -> int:
    """Put the cook's correction on this sheet. Returns how many rows changed."""
    if session.sheet is None or payload.corrected_meal not in _CORRECTION_MEALS:
        return 0
    if payload.corrected_action not in _CORRECTION_ACTIONS:
        return 0
    qty = 0 if payload.corrected_action == "cancel" else max(0, min(payload.corrected_qty, 20))
    applied = 0
    for ev in session.events:
        if ev.customer.strip().lower() != payload.customer.strip().lower():
            continue
        if ev.raw_text != payload.raw_text:
            continue
        ev.meal = payload.corrected_meal
        ev.action = payload.corrected_action
        ev.qty = qty
        ev.date = session.sheet.date
        ev.needs_review = False
        ev.confidence = 1.0
        ev.is_late = False
        ev.timestamp = None
        ev.audit_flags = [flag for flag in ev.audit_flags if flag not in _CLEARED_FLAGS]
        if qty > 0 and not ev.items:
            ev.items = ["thali"]
        if qty == 0:
            ev.items = []
        applied += 1
    if applied:
        fill_session(
            session,
            session.events,
            session.sheet.date,
            session.cutoff,
            session.extractor_label,
            session.used_fallback,
            session.model_messages,
            session.fallback_messages,
            session.extractor_notes,
        )
    return applied


def corrections_file_for(session: KitchenSession) -> Path:
    """Where this cook's corrections live.

    They used to share one `data/private/corrections.jsonl`, so every visitor's
    customers pooled together in one file and one SFT export.
    """
    return CORRECTIONS_FILE.parent / f"corrections_{session.sid[:8]}.jsonl"


@app.post("/api/corrections")
def save_correction(request: Request, payload: CorrectionPayload):
    session, is_new = open_session(request)
    applied = apply_correction(session, payload)

    # Durably record correction into SQLite and append to canonical corrections.jsonl
    try:
        persist_correction(
            kitchen_id=session.sid,
            customer=payload.customer,
            raw_text=payload.raw_text,
            corrected_meal=payload.corrected_meal,
            corrected_qty=payload.corrected_qty,
            corrected_action=payload.corrected_action,
            applied_count=applied,
        )
    except Exception as exc:
        logger.warning(f"Could not persist correction to db: {exc}")

    if demo_mode():
        return remember_cookie(
            JSONResponse(
                {
                    "status": "saved",
                    "applied": applied,
                    "persisted": False,
                    "note": "Demo mode: the correction is on this sheet but is not "
                    "written to disk.",
                }
            ),
            session,
            is_new,
        )

    mgr = ActiveLearningManager(storage_path=corrections_file_for(session))
    entry = CorrectionEntry(
        customer=payload.customer,
        raw_text=payload.raw_text,
        corrected_meal=payload.corrected_meal,
        corrected_qty=payload.corrected_qty,
        corrected_action=payload.corrected_action,
    )
    record = mgr.record_correction(entry)
    response = JSONResponse(
        {"status": "saved", "applied": applied, "persisted": True, "record": record}
    )
    return remember_cookie(response, session, is_new)


@app.post("/api/active-learning/export")
def export_active_learning(request: Request):
    """Export this cook's corrections into an SFT JSONL training batch.

    This used to take no session and dumped every visitor's corrections into one
    file. In demo mode it is refused outright.
    """
    if demo_mode():
        raise HTTPException(
            status_code=403,
            detail="Active-learning export is disabled on the public demo.",
        )
    session, is_new = open_session(request)
    mgr = ActiveLearningManager(storage_path=corrections_file_for(session))
    count = mgr.export_sft_dataset()
    response = JSONResponse(
        {
            "status": "exported",
            "examples_count": count,
            "export_path": "data/sft/active_learning_batch.jsonl",
        }
    )
    return remember_cookie(response, session, is_new)


_ALLOWED_AUDIO_SUFFIXES = {".ogg", ".opus", ".m4a", ".mp3"}
MAX_AUDIO_BYTES = 10 * 1024 * 1024


@app.post("/api/voice-note")
async def transcribe_voice_note(
    audio_file: Optional[UploadFile] = None,
    customer_name: str = Form("VoiceCustomer"),
):
    """
    Ingest a WhatsApp voice note (.ogg, .opus, .m4a, .mp3),
    transcribe it into Hinglish text, and return formatted WhatsApp chat entry.

    The client filename is never used to build a path. It previously was, so an
    upload named "../../x.ogg" wrote outside the upload folder; on Render that
    can overwrite application files.
    """
    transcriber = VoiceNoteTranscriber()

    upload_dir = Path("data/uploads/audio")
    upload_dir.mkdir(parents=True, exist_ok=True)

    if audio_file and audio_file.filename:
        suffix = Path(audio_file.filename).suffix.lower()
        if suffix not in _ALLOWED_AUDIO_SUFFIXES:
            raise HTTPException(
                status_code=415,
                detail=f"Voice notes must be one of {', '.join(sorted(_ALLOWED_AUDIO_SUFFIXES))}.",
            )
        audio_bytes = await audio_file.read()
        if len(audio_bytes) > MAX_AUDIO_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"That note is {len(audio_bytes) // (1024 * 1024)} MB. "
                "WhatsApp voice notes are much smaller.",
            )
        dest_path = upload_dir / f"{uuid.uuid4().hex}{suffix}"
        dest_path.write_bytes(audio_bytes)
    else:
        dest_path = upload_dir / "sample_voice_cancel.ogg"
        dest_path.write_bytes(b"MOCK_OGG_HEADER")

    result = transcriber.transcribe(dest_path, customer_name=customer_name)
    return {
        "status": "transcribed",
        "customer": result.customer,
        "text": result.transcribed_text,
        "chat_line": result.formatted_chat_line,
        "backend": result.backend_used,
        "confidence": result.confidence,
    }


@app.get("/benchmarks", response_class=HTMLResponse)
def view_benchmarks(request: Request):
    default_suite = STANDARD_BENCHMARK_SUITES[0]
    result = evaluate_and_heal_loop(
        raw_text=default_suite["raw_text"],
        gold_event=default_suite["gold"],
        threshold=90.0,
    )
    return templates.TemplateResponse(
        request=request,
        name="benchmarks.html",
        context={
            "benchmark_suites": STANDARD_BENCHMARK_SUITES,
            "active_suite_id": default_suite["id"],
            "active_suite": default_suite,
            "threshold": 90.0,
            "inject_flaw": False,
            "result": result,
        },
    )


@app.post("/api/benchmarks/run")
async def run_benchmark_eval(
    request: Request,
    suite_id: str = Form("suite_negation_intent"),
    threshold: float = Form(90.0),
    max_retries: int = Form(5),
    inject_flaw: Optional[bool] = Form(False),
    custom_raw_text: Optional[str] = Form(None),
    custom_gold_json: Optional[str] = Form(None),
):
    selected_suite = next((s for s in STANDARD_BENCHMARK_SUITES if s["id"] == suite_id), None)
    if suite_id == "custom" and custom_raw_text and custom_gold_json:
        try:
            gold_data = json.loads(custom_gold_json)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid custom gold JSON") from exc
        raw_text = custom_raw_text
    elif selected_suite:
        raw_text = selected_suite["raw_text"]
        gold_data = selected_suite["gold"]
    else:
        selected_suite = STANDARD_BENCHMARK_SUITES[0]
        raw_text = selected_suite["raw_text"]
        gold_data = selected_suite["gold"]

    initial_pred = None
    if inject_flaw:
        initial_pred = [
            {
                "customer": gold_data.get("customer", "Customer"),
                "meal": "lunch",
                "qty": 1,
                "action": "cancel" if "cancel" in raw_text.lower() else "new",
                "mods": [],
                "secondary_customer": None,
                "confidence": 0.65,
            }
        ]

    result = evaluate_and_heal_loop(
        raw_text=raw_text,
        gold_event=gold_data,
        initial_prediction=initial_pred,
        threshold=threshold,
        max_retries=max_retries,
    )

    if "text/html" in request.headers.get("accept", ""):
        return templates.TemplateResponse(
            request=request,
            name="benchmarks.html",
            context={
                "benchmark_suites": STANDARD_BENCHMARK_SUITES,
                "active_suite_id": suite_id,
                "active_suite": selected_suite,
                "threshold": threshold,
                "inject_flaw": inject_flaw,
                "result": result,
            },
        )
    return JSONResponse(result.model_dump(mode="json"))


@app.get("/api/benchmarks/suites")
def list_benchmark_suites():
    return JSONResponse(STANDARD_BENCHMARK_SUITES)
