from fastapi.testclient import TestClient


def test_salud_sin_auth():
    from observatorio.api.main import crear_app

    c = TestClient(crear_app())
    r = c.get("/api/salud")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_salud_db_ping(bd):
    from observatorio.api.main import crear_app

    c = TestClient(crear_app())
    r = c.get("/api/salud", params={"db": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["db_ok"] is True
    assert isinstance(body["db_latencia_ms"], int)
