"""Integration tests for FastAPI kitchen routes and endpoints."""

from starlette.testclient import TestClient

from tiffintally.app import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["app"] == "tiffintally"
    assert data["guardrails"] == "active"
    assert data["kds_station"] == "available"
    assert data["active_learning"] == "ready"


def test_index_view():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "TiffinTally" in resp.text
    assert "WhatsApp" in resp.text


def test_prep_sheet_view():
    resp = client.get("/prep")
    assert resp.status_code == 200
    assert "Kitchen Prep Sheet" in resp.text
    assert "Packing Labels" in resp.text


def test_station_view():
    resp = client.get("/station")
    assert resp.status_code == 200
    assert "Kitchen Display Station" in resp.text
    assert "PACKING COMPLETION" in resp.text
    assert "Pack" in resp.text


def test_ledger_view():
    resp = client.get("/ledger")
    assert resp.status_code == 200
    assert "Customer Dues Ledger" in resp.text
    assert "Balance Due" in resp.text


def test_forecast_view():
    resp = client.get("/forecast?confirmed=35")
    assert resp.status_code == 200
    assert "Kitchen Cook Forecast" in resp.text
    assert "SYNTHETIC-HISTORY SUGGESTION" in resp.text
    assert "Not a cook instruction" in resp.text


def test_process_chat_post():
    from datetime import datetime

    sent = datetime.now().replace(hour=20, minute=14, second=0, microsecond=0)
    stamp = sent.strftime("%d/%m/%y, %I:%M %p").lower()
    demo_raw = f"{stamp} - Ravi: kal lunch 2, dinner skip\n{stamp} - Priya: kal lunch cancel"
    resp = client.post("/process", data={"raw_text": demo_raw, "target_date": "tomorrow"})
    assert resp.status_code == 200
    assert "Kitchen Prep Sheet" in resp.text
    assert "Ravi" in resp.text


def test_save_correction_api(tmp_path, monkeypatch):
    test_corr_path = tmp_path / "test_corrections.jsonl"
    import tiffintally.app as app_module

    monkeypatch.setattr(app_module, "CORRECTIONS_FILE", test_corr_path)

    payload = {
        "customer": "Ravi",
        "raw_text": "kal lunch 2 nahi 3",
        "corrected_meal": "lunch",
        "corrected_qty": 3,
        "corrected_action": "change",
    }
    resp = client.post("/api/corrections", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "saved"
    assert test_corr_path.exists()
    content = test_corr_path.read_text(encoding="utf-8")
    assert "Ravi" in content
    assert '"corrected_qty": 3' in content


def test_active_learning_export_api(tmp_path, monkeypatch):
    test_corr_path = tmp_path / "test_corrections.jsonl"
    test_sft_export = tmp_path / "active_learning_batch.jsonl"
    import tiffintally.app as app_module
    import tiffintally.feedback as feedback_module

    monkeypatch.setattr(app_module, "CORRECTIONS_FILE", test_corr_path)
    monkeypatch.setattr(feedback_module, "ACTIVE_SFT_EXPORT", test_sft_export)

    # First save a correction
    client.post(
        "/api/corrections",
        json={
            "customer": "Sonia",
            "raw_text": "kal lunch cancel aunty",
            "corrected_meal": "lunch",
            "corrected_qty": 0,
            "corrected_action": "cancel",
        },
    )

    resp = client.post("/api/active-learning/export")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "exported"
    assert data["examples_count"] >= 1


def test_voice_note_api():
    resp = client.post(
        "/api/voice-note",
        data={"customer_name": "Deepak"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "transcribed"
    assert data["customer"] == "Deepak"
    assert "Deepak" in data["chat_line"]
