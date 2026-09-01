from fastapi.testclient import TestClient

from main import app


def test_api_reports_the_release_version():
    assert TestClient(app).get("/openapi.json").json()["info"]["version"] == "2.1.0"
