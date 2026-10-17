"""Form, ledger, CSV and benchmark checks from the functional audit."""

import csv
import io

from tiffintally.app import app
from tiffintally.uploads import MAX_UPLOAD_BYTES


def test_home_form_asks_for_cutoff_and_cook_names():
    from starlette.testclient import TestClient

    page = TestClient(app).get("/")
    assert page.status_code == 200
    assert 'name="cutoff"' in page.text
    assert 'value="22:00"' in page.text
    assert 'name="cook_names"' in page.text


def test_cook_lines_are_skipped_when_her_name_is_given():
    from starlette.testclient import TestClient

    raw = "\n".join(
        [
            "17/10/26, 8:00 pm - Ravi: kal lunch 2",
            "17/10/26, 8:01 pm - Aunty: ok kal lunch 2 done",
        ]
    )
    cook = TestClient(app)
    named = cook.post(
        "/process",
        data={"raw_text": raw, "target_date": "tomorrow", "cook_names": "Aunty"},
    )
    assert named.status_code == 200
    assert "were not counted as orders" in named.text
    skipped = named.text
    unnamed = TestClient(app).post(
        "/process",
        data={"raw_text": raw, "target_date": "tomorrow"},
    )
    assert "were not counted as orders" not in unnamed.text
    assert "TOTAL THALIS" in skipped


def test_html_balance_import_redirects_and_keeps_casing():
    from starlette.testclient import TestClient

    cook = TestClient(app)
    csv = "customer,balance\nPriya Sharma,120\n"
    html = cook.post(
        "/ledger/balances",
        files={"balance_file": ("balances.csv", csv, "text/csv")},
        headers={"accept": "text/html"},
        follow_redirects=False,
    )
    assert html.status_code == 303
    assert html.headers["location"] == "/ledger"
    page = cook.get("/ledger")
    assert "Priya Sharma" in page.text
    assert "Imported opening balances" in page.text

    api = TestClient(app)
    machine = api.post(
        "/ledger/balances",
        files={"balance_file": ("balances.csv", csv, "text/csv")},
        headers={"accept": "application/json"},
    )
    assert machine.status_code == 200
    assert machine.json()["customers"] == 1


def test_html_alias_confirm_redirects():
    from starlette.testclient import TestClient

    raw = "\n".join(
        [
            "17/10/26, 8:00 pm - Ravi: kal lunch 1",
            "17/10/26, 8:05 pm - Ravi Sharma: kal lunch 1",
        ]
    )
    cook = TestClient(app)
    assert (
        cook.post("/process", data={"raw_text": raw, "target_date": "tomorrow"}).status_code == 200
    )
    html = cook.post(
        "/api/aliases/confirm",
        data={"source": "Ravi", "target": "Ravi Sharma"},
        headers={"accept": "text/html"},
        follow_redirects=False,
    )
    assert html.status_code == 303
    assert html.headers["location"] == "/ledger"
    page = cook.get("/ledger")
    assert "Merged Ravi into Ravi Sharma." in page.text

    other = TestClient(app)
    other.post("/process", data={"raw_text": raw, "target_date": "tomorrow"})
    api = other.post(
        "/api/aliases/confirm",
        data={"source": "Ravi", "target": "Ravi Sharma"},
        headers={"accept": "application/json"},
    )
    assert api.status_code == 200
    assert api.json()["status"] == "merged"


def test_csv_export_prefixes_formula_cells():
    from starlette.testclient import TestClient

    sender = '=HYPERLINK("http://x","y")'
    raw = f"17/10/26, 8:00 pm - {sender}: kal lunch 1"
    cook = TestClient(app)
    cook.post("/process", data={"raw_text": raw, "target_date": "tomorrow"})
    exported = cook.get("/ledger/balances.csv")
    assert exported.status_code == 200
    rows = list(csv.reader(io.StringIO(exported.text)))
    assert rows[1][0].startswith("'=")
    assert "HYPERLINK" in rows[1][0]


def test_paste_between_one_and_two_megabytes_is_accepted():
    from starlette.testclient import TestClient

    body = "17/10/26, 8:00 pm - Ravi: kal lunch 1\n" + ("x" * (int(1.2 * 1024 * 1024)))
    assert len(body.encode()) < MAX_UPLOAD_BYTES
    resp = TestClient(app).post("/process", data={"raw_text": body, "target_date": "tomorrow"})
    assert resp.status_code == 200
    assert "Kitchen Prep Sheet" in resp.text


def test_custom_gold_list_of_numbers_is_400():
    from starlette.testclient import TestClient

    resp = TestClient(app).post(
        "/api/benchmarks/run",
        data={
            "suite_id": "custom",
            "custom_raw_text": "kal lunch 1",
            "custom_gold_json": "[1, 2]",
        },
    )
    assert resp.status_code == 400


def test_docs_are_hidden_unless_debug(monkeypatch):
    from starlette.testclient import TestClient

    monkeypatch.delenv("TIFFINTALLY_DEBUG", raising=False)
    # The app was constructed at import with debug off.
    client = TestClient(app)
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_security_headers_and_secure_cookie():
    from starlette.testclient import TestClient

    client = TestClient(app)
    page = client.get("/health")
    assert page.headers["x-frame-options"] == "DENY"
    assert page.headers["x-content-type-options"] == "nosniff"
    assert page.headers["referrer-policy"] == "same-origin"
    assert "content-security-policy-report-only" in page.headers
    assert "strict-transport-security" not in page.headers

    secured = client.get("/health", headers={"x-forwarded-proto": "https"})
    assert secured.headers["strict-transport-security"].startswith("max-age=")
