"""Tests for FastAPI web application endpoints."""

from fastapi.testclient import TestClient

from tiffintally.app import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["app"] == "tiffintally"


def test_index_page():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "TiffinTally" in resp.text
    assert "Order Intake & Extraction" in resp.text


def test_prep_sheet_view():
    resp = client.get("/prep")
    assert resp.status_code == 200
    assert "Kitchen Prep Sheet" in resp.text
    assert "Packing Labels" in resp.text


def test_ledger_view():
    resp = client.get("/ledger")
    assert resp.status_code == 200
    assert "Customer Dues Ledger" in resp.text
    assert "Never auto-sends" in resp.text or "Strict Outbound Messaging" in resp.text


def test_forecast_page():
    resp = client.get("/forecast?confirmed=35")
    assert resp.status_code == 200
    assert "Kitchen Cook Forecast" in resp.text
    assert "PREDICTED TO COOK" in resp.text


def test_process_chat_post():
    demo_raw = "12/10/26, 10:14 pm - Ravi: kal lunch 2, dinner skip\n12/10/26, 10:15 pm - Priya: kal lunch cancel"
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
