"""
FastAPI application for TiffinTally.
Serves mobile-friendly kitchen UI, printable prep sheets, touch KDS station mode,
dues ledger, voice briefs, active learning feedback flywheel, and recipe BOM economics.
"""

import logging
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from tiffintally.economics import KitchenEconomics
from tiffintally.extract.gemma import GemmaExtractor
from tiffintally.feedback import ActiveLearningManager, CorrectionEntry
from tiffintally.forecast import KitchenForecaster
from tiffintally.parser import parse_chat_export
from tiffintally.reconcile import reconcile_ledger, reconcile_orders
from tiffintally.schema import DailyPrepSheet, OrderEvent
from tiffintally.transcribe import VoiceNoteTranscriber
from tiffintally.voice import VoiceBriefResult, VoiceBriefService

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
CORRECTIONS_FILE = Path("data/private/corrections.jsonl")

SESSION_COOKIE = "tt_sid"


@dataclass
class KitchenSession:
    """One browser's kitchen. Not shared with other visitors."""

    sid: str
    sheet: Optional[DailyPrepSheet] = None
    events: list[OrderEvent] = field(default_factory=list)
    voice_brief: Optional[VoiceBriefResult] = None
    forecast: object = None
    bom: object = None
    economics: object = None
    waste_roi: object = None
    extractor_label: str = "no chat loaded"
    used_fallback: bool = True
    cutoff: time = field(default_factory=lambda: time(22, 0))


SESSIONS: dict[str, KitchenSession] = {}


class CorrectionPayload(BaseModel):
    customer: str
    raw_text: str
    corrected_meal: str
    corrected_qty: int
    corrected_action: str


def open_session(request: Request) -> tuple[KitchenSession, bool]:
    sid = request.cookies.get(SESSION_COOKIE)
    if sid and sid in SESSIONS:
        return SESSIONS[sid], False
    sid = uuid.uuid4().hex
    session = KitchenSession(sid=sid)
    SESSIONS[sid] = session
    return session, True


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
) -> None:
    """Build the sheet from this cook's events only. Standing orders default to empty."""
    session.events = events
    session.extractor_label = extractor_label
    session.used_fallback = used_fallback
    session.cutoff = cutoff_t
    session.sheet = reconcile_orders(
        events=events,
        target_date=target_date,
        cutoff_time=cutoff_t,
        standing_orders=None,
    )
    session.voice_brief = VoiceBriefService().generate_morning_brief(session.sheet)
    forecaster = KitchenForecaster()
    session.forecast = forecaster.how_many_to_cook(
        target_date=session.sheet.date,
        confirmed_count=session.sheet.total_thalis,
    )
    econ = KitchenEconomics()
    session.bom = econ.compute_bom(session.sheet.total_thalis)
    session.economics = econ.compute_ai_unit_economics(session.sheet.total_thalis)
    session.waste_roi = econ.compute_waste_reduction_roi(session.sheet.total_thalis)


def ensure_empty(session: KitchenSession) -> None:
    if session.sheet is None:
        fill_session(
            session,
            events=[],
            target_date="tomorrow",
            cutoff_t=time(22, 0),
            extractor_label="no chat loaded",
            used_fallback=True,
        )


def sheet_context(session: KitchenSession) -> dict:
    return {
        "sheet": session.sheet,
        "voice_brief": session.voice_brief,
        "forecast": session.forecast,
        "bom": session.bom,
        "economics": session.economics,
        "waste_roi": session.waste_roi,
        "extractor_label": session.extractor_label,
        "used_fallback": session.used_fallback,
        "current_time": datetime.now().strftime("%I:%M %p, %d %b %Y"),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Do not seed fictional customers into a process-wide sheet.
    yield


app = FastAPI(
    title="TiffinTally",
    description="Your WhatsApp orders, sorted before the pressure cooker's first whistle.",
    version="0.2.0",
    lifespan=lifespan,
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "app": "tiffintally",
        "version": "0.2.0",
        "guardrails": "active",
        "kds_station": "available",
        "active_learning": "ready",
    }


@app.get("/", response_class=HTMLResponse)
def index_view(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"default_cutoff": "22:00"},
    )


@app.post("/process", response_class=HTMLResponse)
async def process(
    request: Request,
    chat_file: Optional[UploadFile] = None,
    raw_text: Optional[str] = Form(None),
    target_date: str = Form("tomorrow"),
    cutoff: str = Form("22:00"),
):
    session, is_new = open_session(request)

    content = ""
    if chat_file and chat_file.filename:
        file_bytes = await chat_file.read()
        content = file_bytes.decode("utf-8", errors="replace")
    elif raw_text:
        content = raw_text
    else:
        content = ""

    parsed_msgs = parse_chat_export(content) if content.strip() else []
    extractor = GemmaExtractor()
    events = extractor.extract_batch(parsed_msgs) if parsed_msgs else []
    label = extractor.model_name
    used_fallback = not extractor.is_available()
    if used_fallback and not label.endswith("-fallback"):
        label = f"{label}-fallback"

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
    )

    response = templates.TemplateResponse(
        request=request,
        name="prep_sheet.html",
        context=sheet_context(session),
    )
    return remember_cookie(response, session, is_new)


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


@app.get("/station", response_class=HTMLResponse)
def view_kds_station(request: Request):
    """Touch-friendly Kitchen Display Station (KDS) for packing and container ticking."""
    session, is_new = open_session(request)
    ensure_empty(session)
    response = templates.TemplateResponse(
        request=request,
        name="station.html",
        context={
            "sheet": session.sheet,
            "current_time": datetime.now().strftime("%I:%M %p, %d %b %Y"),
        },
    )
    return remember_cookie(response, session, is_new)


@app.get("/ledger", response_class=HTMLResponse)
def view_ledger(request: Request):
    session, is_new = open_session(request)
    ensure_empty(session)

    ledger = reconcile_ledger(
        session.events,
        price_per_thali=80.0,
        previous_balances=None,
    )

    response = templates.TemplateResponse(
        request=request,
        name="ledger.html",
        context={"ledger": ledger},
    )
    return remember_cookie(response, session, is_new)


@app.get("/forecast", response_class=HTMLResponse)
def forecast_view(
    request: Request,
    date: Optional[str] = None,
    confirmed: int = 0,
):
    target_dt = date or (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    forecaster = KitchenForecaster()
    result = forecaster.how_many_to_cook(target_date=target_dt, confirmed_count=confirmed)

    econ = KitchenEconomics()
    bom = econ.compute_bom(result.predicted_to_cook)
    roi = econ.compute_waste_reduction_roi(daily_confirmed_plates=confirmed)

    return templates.TemplateResponse(
        request=request,
        name="forecast.html",
        context={
            "target_date": target_dt,
            "confirmed": confirmed,
            "result": result,
            "bom": bom,
            "roi": roi,
        },
    )


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
            events=session.events,
            target_date=session.sheet.date,
            cutoff_t=session.cutoff,
            extractor_label=session.extractor_label,
            used_fallback=session.used_fallback,
        )
    return applied


@app.post("/api/corrections")
def save_correction(request: Request, payload: CorrectionPayload):
    mgr = ActiveLearningManager(storage_path=CORRECTIONS_FILE)
    entry = CorrectionEntry(
        customer=payload.customer,
        raw_text=payload.raw_text,
        corrected_meal=payload.corrected_meal,
        corrected_qty=payload.corrected_qty,
        corrected_action=payload.corrected_action,
    )
    record = mgr.record_correction(entry)
    session, is_new = open_session(request)
    applied = apply_correction(session, payload)
    response = JSONResponse({"status": "saved", "applied": applied, "record": record})
    return remember_cookie(response, session, is_new)


@app.post("/api/active-learning/export")
def export_active_learning():
    """Exports all recorded cook corrections into an SFT JSONL training batch."""
    mgr = ActiveLearningManager(storage_path=CORRECTIONS_FILE)
    count = mgr.export_sft_dataset()
    return {
        "status": "exported",
        "examples_count": count,
        "export_path": "data/sft/active_learning_batch.jsonl",
    }


@app.post("/api/voice-note")
async def transcribe_voice_note(
    audio_file: Optional[UploadFile] = None,
    customer_name: str = Form("VoiceCustomer"),
):
    """
    Ingest a WhatsApp voice note (.ogg, .opus, .m4a, .mp3),
    transcribe it into Hinglish text, and return formatted WhatsApp chat entry.
    """
    transcriber = VoiceNoteTranscriber()

    # Save audio temporarily
    upload_dir = Path("data/uploads/audio")
    upload_dir.mkdir(parents=True, exist_ok=True)

    if audio_file and audio_file.filename:
        filename = audio_file.filename
        dest_path = upload_dir / filename
        bytes_data = await audio_file.read()
        dest_path.write_bytes(bytes_data)
    else:
        # Create a mock voice note for testing
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
