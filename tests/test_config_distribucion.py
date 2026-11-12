import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def cliente(bd, monkeypatch):
    from observatorio.api import seguridad
    from observatorio.api.rutas import auth_usuarios

    def falso_google(credencial):
        email, ok = credencial.split("|")
        return {"email": email, "email_verified": ok == "1", "name": "Prueba"}

    monkeypatch.setattr(seguridad, "verificar_google", falso_google)
    monkeypatch.setattr(auth_usuarios, "verificar_google", falso_google)
    from observatorio.api.main import crear_app

    return TestClient(crear_app())


@pytest.fixture()
def headers_admin(cliente):
    r = cliente.post("/api/auth/google", json={"credential": "clagosm@unal.edu.co|1"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_put_distribucion_fuentes_valida(cliente, headers_admin):
    r = cliente.put(
        "/api/config/distribucion_fuentes",
        json={"valor": {"linkedin": 42, "indeed": 30, "computrabajo": 28}},
        headers=headers_admin,
    )
    assert r.status_code == 200


def test_put_distribucion_rechaza_suma(cliente, headers_admin):
    r = cliente.put(
        "/api/config/distribucion_fuentes",
        json={"valor": {"linkedin": 50, "indeed": 30, "computrabajo": 10}},
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_normalizar_endpoint(cliente, headers_admin):
    r = cliente.post(
        "/api/config/distribucion/normalizar?clave=distribucion_fuentes",
        json={"valor": {"linkedin": 4, "indeed": 3, "computrabajo": 3}},
        headers=headers_admin,
    )
    assert r.status_code == 200
    data = r.json()
    assert abs(sum(data["valor"].values()) - 100) < 0.1
