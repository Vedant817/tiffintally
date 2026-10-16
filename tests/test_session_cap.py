"""Hard session bounds retain recently used cooks and version follows packaging."""

from datetime import datetime, timedelta
from importlib.metadata import version

from fastapi.testclient import TestClient

import tiffintally.app as application


def test_active_sessions_cannot_exceed_cap(monkeypatch):
    monkeypatch.setattr(application, "SESSIONS", {})
    monkeypatch.setattr(application, "MAX_SESSIONS", 2)
    first = TestClient(application.app)
    first.get("/prep")
    old = first.cookies.get(application.SESSION_COOKIE)
    application.SESSIONS[old].touched = datetime.now() - timedelta(seconds=10)
    second = TestClient(application.app)
    second.get("/prep")
    recent = second.cookies.get(application.SESSION_COOKIE)
    third = TestClient(application.app)
    third.get("/prep")
    assert len(application.SESSIONS) == 2
    assert old not in application.SESSIONS and recent in application.SESSIONS


def test_health_uses_installed_project_version():
    assert TestClient(application.app).get("/health").json()["version"] == version("tiffintally")
