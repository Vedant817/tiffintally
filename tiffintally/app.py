"""
FastAPI application for TiffinTally.
Serves mobile-friendly kitchen UI, printable prep sheets, dues ledger, voice briefs,
active learning corrections, and production kitchen economics & BOM calculator.
"""

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from tiffintally.economics import KitchenEconomics
from tiffintally.extract.gemma import GemmaExtractor
from tiffintally.forecast import KitchenForecaster
from tiffintally.parser import parse_chat_export
from tiffintally.reconcile import reconcile_ledger, reconcile_orders
from tiffintally.schema import DailyPrepSheet, OrderEvent
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


def get_default_demo_events() -> list[OrderEvent]:
    """Provide realistic initial demo batch so app is immediately usable on startup."""
    from tiffintally.extract.base import heuristic_extract

    demo_chat = """12/10/26, 10:14 pm - Ravi: kal lunch 2, dinner skip
12/10/26, 10:15 pm - Priya: kal lunch 1, aaj roti nahi extra rice dena please
12/10/26, 10:18 pm - Sneha: kal lunch cancel aunty, team lunch hai
12/10/26, 10:20 pm - Karan: Kal lunch 1 plate. Aur meri roommate Tanvi ke liye bhi ek lunch add kar dena
12/10/26, 10:24 pm - Vikram: ₹1500 GPay kiya aunty check kar lo
12/10/26, 10:30 pm - Ananya: earlier ordered 1, please change it to 3 thalis for dinner tomorrow
12/10/26, 10:35 pm - Rohan: thank you aunty khana mast tha!
12/10/26, 10:40 pm - Pooja: कल दो थाली दोपहर को भेजना, बिना प्याज के
12/10/26, 10:55 pm - Amit: Sunday off please, going home
12/10/26, 11:15 pm - Deepak: kal lunch 2 add karo please late message aunty"""

    messages = parse_chat_export(demo_chat)
    events = []
    for msg in messages:
        if not msg.is_system and not msg.is_media and msg.text:
            extracted = heuristic_extract(msg.text, sender=msg.sender)
            for ev in extracted:
                ev.timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                events.append(ev)
    return events


def init_default_data():
    global CURRENT_SHEET, CURRENT_EVENTS, CURRENT_VOICE_BRIEF, CURRENT_FORECAST
    global CURRENT_BOM, CURRENT_ECONOMICS, CURRENT_WASTE_ROI

    CURRENT_EVENTS = get_default_demo_events()
    CURRENT_SHEET = reconcile_orders(
        CURRENT_EVENTS, target_date="Tomorrow", cutoff_time=time(23, 0)
    )

    voice_service = VoiceBriefService()
    CURRENT_VOICE_BRIEF = voice_service.generate_morning_brief(CURRENT_SHEET)

    forecaster = KitchenForecaster()
    CURRENT_FORECAST = forecaster.how_many_to_cook(
        target_date="tomorrow", confirmed_count=CURRENT_SHEET.total_thalis
    )

    econ = KitchenEconomics()
    cook_count = CURRENT_FORECAST.predicted_to_cook if CURRENT_FORECAST else CURRENT_SHEET.total_thalis
    CURRENT_BOM = econ.compute_bom(cook_count)
    CURRENT_ECONOMICS = econ.compute_ai_unit_economics(daily_messages=max(20, len(CURRENT_EVENTS)))
    CURRENT_WASTE_ROI = econ.compute_waste_reduction_roi(daily_confirmed_plates=CURRENT_SHEET.total_thalis)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_default_data()
    yield


app = FastAPI(title="TiffinTally", version="0.2.0", lifespan=lifespan)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/health")
def health():
    return {"status": "ok", "app": "tiffintally", "version": "0.2.0", "guardrails": "active"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})


@app.post("/process", response_class=HTMLResponse)
async def process(
    request: Request,
    raw_text: Optional[str] = Form(None),
    chat_file: Optional[UploadFile] = None,
    target_date: str = Form("tomorrow"),
):
    global CURRENT_SHEET, CURRENT_EVENTS, CURRENT_VOICE_BRIEF, CURRENT_FORECAST
    global CURRENT_BOM, CURRENT_ECONOMICS, CURRENT_WASTE_ROI

    content = ""
    if chat_file and chat_file.filename:
        file_bytes = await chat_file.read()
        content = file_bytes.decode("utf-8", errors="ignore")
    elif raw_text and raw_text.strip():
        content = raw_text

    if not content.strip():
        content = "Ravi: kal lunch 1"

    messages = parse_chat_export(content)
    extractor = GemmaExtractor()
    extracted_events: list[OrderEvent] = []

    for msg in messages:
        if not msg.is_system and not msg.is_media and msg.text:
            res = extractor.extract_from_text(msg.text, sender=msg.sender)
            for ev in res.events:
                ev.timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                extracted_events.append(ev)

    CURRENT_EVENTS = extracted_events
    CURRENT_SHEET = reconcile_orders(
        CURRENT_EVENTS, target_date=target_date, cutoff_time=time(23, 0)
    )

    voice_service = VoiceBriefService()
    CURRENT_VOICE_BRIEF = voice_service.generate_morning_brief(CURRENT_SHEET, force_refresh=True)

    forecaster = KitchenForecaster()
    CURRENT_FORECAST = forecaster.how_many_to_cook(
        target_date=target_date, confirmed_count=CURRENT_SHEET.total_thalis
    )

    econ = KitchenEconomics()
    cook_count = CURRENT_FORECAST.predicted_to_cook if CURRENT_FORECAST else CURRENT_SHEET.total_thalis
    CURRENT_BOM = econ.compute_bom(cook_count)
    CURRENT_ECONOMICS = econ.compute_ai_unit_economics(daily_messages=max(20, len(CURRENT_EVENTS)))
    CURRENT_WASTE_ROI = econ.compute_waste_reduction_roi(daily_confirmed_plates=CURRENT_SHEET.total_thalis)

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
    global CURRENT_SHEET, CURRENT_VOICE_BRIEF, CURRENT_FORECAST
    global CURRENT_BOM, CURRENT_ECONOMICS, CURRENT_WASTE_ROI
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
    CORRECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now().isoformat(),
        "customer": payload.customer,
        "raw_text": payload.raw_text,
        "corrected_meal": payload.corrected_meal,
        "corrected_qty": payload.corrected_qty,
        "corrected_action": payload.corrected_action,
        "corrected": {
            "meal": payload.corrected_meal,
            "qty": payload.corrected_qty,
            "action": payload.corrected_action,
        },
    }
    with open(CORRECTIONS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {"status": "saved", "record": record}
