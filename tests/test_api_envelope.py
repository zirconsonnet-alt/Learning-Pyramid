from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapter.errors import register_exception_handlers
from adapter.main import create_app


def test_unknown_api_path_returns_error_envelope() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/not-found")
    assert resp.status_code == 404
    assert resp.json() == {
        "ok": False,
        "error": {
            "code": "NOT_FOUND",
            "message": "Not found",
        },
    }


def test_unknown_exception_hides_internal_details_by_default() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom() -> dict:
        raise RuntimeError("sensitive-path: C:/secret/file.txt")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")

    assert resp.status_code == 500
    assert resp.json() == {
        "ok": False,
        "error": {
            "code": "UNKNOWN",
            "message": "Internal server error",
        },
    }
