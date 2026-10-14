"""
FastAPI application for TiffinTally.
Serves mobile-friendly kitchen UI, printable prep sheets, touch KDS station mode,
dues ledger, voice briefs, active learning feedback flywheel, and recipe BOM economics.
"""

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
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

# In-memory session state for single-cook kitchen workflow
CURRENT_SHEET: Optional[DailyPrepSheet] = None
CURRENT_EVENTS: list[OrderEvent] = []
CURRENT_VOICE_BRIEF: Optional[VoiceBriefResult] = None
CURRENT_FORECAST = None
CURRENT_BOM = None
CURRENT_ECONOMICS = None
CURRENT_WASTE_ROI = None


class CorrectionPayload(BaseModel):
    customer: str
    raw_text: str
    corrected_meal: str
    corrected_qty: int
    corrected_action: str


def init_default_data():
    """Seed sample Pune customer chat for instant demo experience."""
    global CURRENT_SHEET, CURRENT_EVENTS, CURRENT_VOICE_BRIEF, CURRENT_FORECAST, CURRENT_BOM, CURRENT_ECONOMICS, CURRENT_WASTE_ROI
    demo_raw = """12/10/26, 9:30 pm - Priya: Kal lunch 1 thali, roti nahi rice please
12/10/26, 9:45 pm - Rahul: Kal lunch cancel aunty, office me party hai
12/10/26, 10:14 pm - Vikram: kal 2 nahi 3 thali dinner bhejo, roommate aa gaya
12/10/26, 10:30 pm - Amit: Kal lunch me bina pyaaz lahsun ke 1 thali
12/10/26, 10:45 pm - Sneha: Kal lunch and dinner dono 1-1 thali
12/10/26, 11:15 pm - Rohan: Kal lunch 2 thali extra spicy
"""
    parsed_msgs = parse_chat_export(demo_raw)
    extractor = GemmaExtractor()
    CURRENT_EVENTS = extractor.extract_batch(parsed_msgs)

    # Reconcile into prep sheet
    CURRENT_SHEET = reconcile_orders(
        events=CURRENT_EVENTS,
        target_date="tomorrow",
        cutoff_time=time(22, 0),
        standing_orders={"priya": 1, "rahul": 1, "vikram": 2, "amit": 1, "sneha": 1},
    )

    # Generate audio brief
    voice_service = VoiceBriefService()
    CURRENT_VOICE_BRIEF = voice_service.generate_morning_brief(CURRENT_SHEET)

    # Kitchen forecast
    forecaster = KitchenForecaster()
    CURRENT_FORECAST = forecaster.how_many_to_cook(
        target_date=(datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d"),
        confirmed_count=CURRENT_SHEET.total_thalis,
    )

    # Kitchen Economics and Grocery BOM
    econ = KitchenEconomics()
    CURRENT_BOM = econ.compute_bom(CURRENT_SHEET.total_thalis)
    CURRENT_ECONOMICS = econ.compute_ai_unit_economics(CURRENT_SHEET.total_thalis)
    CURRENT_WASTE_ROI = econ.compute_waste_reduction_roi(CURRENT_SHEET.total_thalis)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_default_data()
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
    global CURRENT_SHEET, CURRENT_EVENTS, CURRENT_VOICE_BRIEF, CURRENT_FORECAST, CURRENT_BOM, CURRENT_ECONOMICS, CURRENT_WASTE_ROI

    content = ""
    if chat_file and chat_file.filename:
        file_bytes = await chat_file.read()
        content = file_bytes.decode("utf-8", errors="replace")
    elif raw_text:
        content = raw_text
    else:
        content = "12/10/26, 10:14 pm - Ravi: kal lunch 2, dinner skip"

    parsed_msgs = parse_chat_export(content)
    extractor = GemmaExtractor()
    CURRENT_EVENTS = extractor.extract_batch(parsed_msgs)

    # Parse cutoff time
    try:
        parts = cutoff.split(":")
        cutoff_t = time(int(parts[0]), int(parts[1]))
    except Exception:
        cutoff_t = time(22, 0)

    CURRENT_SHEET = reconcile_orders(
        events=CURRENT_EVENTS,
        target_date=target_date,
        cutoff_time=cutoff_t,
        standing_orders={"priya": 1, "rahul": 1, "vikram": 2, "amit": 1, "sneha": 1},
    )

    voice_service = VoiceBriefService()
    CURRENT_VOICE_BRIEF = voice_service.generate_morning_brief(CURRENT_SHEET)

    forecaster = KitchenForecaster()
    CURRENT_FORECAST = forecaster.how_many_to_cook(
        target_date=(datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d"),
        confirmed_count=CURRENT_SHEET.total_thalis,
    )

    econ = KitchenEconomics()
    CURRENT_BOM = econ.compute_bom(CURRENT_SHEET.total_thalis)
    CURRENT_ECONOMICS = econ.compute_ai_unit_economics(CURRENT_SHEET.total_thalis)
    CURRENT_WASTE_ROI = econ.compute_waste_reduction_roi(CURRENT_SHEET.total_thalis)

    return templates.TemplateResponse(
        request=request,
        name="prep_sheet.html",
        context={
            "sheet": CURRENT_SHEET,
            "voice_brief": CURRENT_VOICE_BRIEF,
            "forecast": CURRENT_FORECAST,
            "bom": CURRENT_BOM,
            "economics": CURRENT_ECONOMICS,
            "waste_roi": CURRENT_WASTE_ROI,
            "current_time": datetime.now().strftime("%I:%M %p, %d %b %Y"),
        },
    )


@app.get("/prep", response_class=HTMLResponse)
def view_prep_sheet(request: Request):
    global CURRENT_SHEET, CURRENT_VOICE_BRIEF, CURRENT_FORECAST, CURRENT_BOM, CURRENT_ECONOMICS, CURRENT_WASTE_ROI
    if not CURRENT_SHEET:
        init_default_data()

    return templates.TemplateResponse(
        request=request,
        name="prep_sheet.html",
        context={
            "sheet": CURRENT_SHEET,
            "voice_brief": CURRENT_VOICE_BRIEF,
            "forecast": CURRENT_FORECAST,
            "bom": CURRENT_BOM,
            "economics": CURRENT_ECONOMICS,
            "waste_roi": CURRENT_WASTE_ROI,
            "current_time": datetime.now().strftime("%I:%M %p, %d %b %Y"),
        },
    )


@app.get("/station", response_class=HTMLResponse)
def view_kds_station(request: Request):
    """Touch-friendly Kitchen Display Station (KDS) for packing and container ticking."""
    global CURRENT_SHEET
    if not CURRENT_SHEET:
        init_default_data()

    return templates.TemplateResponse(
        request=request,
        name="station.html",
        context={
            "sheet": CURRENT_SHEET,
            "current_time": datetime.now().strftime("%I:%M %p, %d %b %Y"),
        },
    )


@app.get("/ledger", response_class=HTMLResponse)
def view_ledger(request: Request):
    global CURRENT_EVENTS
    if not CURRENT_EVENTS:
        init_default_data()

    ledger = reconcile_ledger(
        CURRENT_EVENTS,
        price_per_thali=80.0,
        previous_balances={"ravi": 400.0, "priya": 240.0, "vikram": 1500.0},
    )

    return templates.TemplateResponse(
        request=request,
        name="ledger.html",
        context={"ledger": ledger},
    )


@app.get("/forecast", response_class=HTMLResponse)
def forecast_view(
    request: Request,
    date: Optional[str] = None,
    confirmed: int = 40,
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
def get_morning_brief_audio():
    global CURRENT_VOICE_BRIEF
    if CURRENT_VOICE_BRIEF and CURRENT_VOICE_BRIEF.audio_path:
        p = Path(CURRENT_VOICE_BRIEF.audio_path)
        if p.exists():
            return FileResponse(p, media_type="audio/mpeg")
    raise HTTPException(status_code=404, detail="Audio brief not generated or cached")


@app.post("/api/corrections")
def save_correction(payload: CorrectionPayload):
    mgr = ActiveLearningManager(storage_path=CORRECTIONS_FILE)
    entry = CorrectionEntry(
        customer=payload.customer,
        raw_text=payload.raw_text,
        corrected_meal=payload.corrected_meal,
        corrected_qty=payload.corrected_qty,
        corrected_action=payload.corrected_action,
    )
    record = mgr.record_correction(entry)
    return {"status": "saved", "record": record}


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
