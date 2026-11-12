import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def cliente(bd, monkeypatch):
    from observatorio.api import seguridad
    from observatorio.api.rutas import auth_usuarios

    def falso_google(credencial):
        # credencial de prueba: "correo|verificado"
        email, ok = credencial.split("|")
        return {"email": email, "email_verified": ok == "1", "name": "Prueba"}

    monkeypatch.setattr(seguridad, "verificar_google", falso_google)
    monkeypatch.setattr(auth_usuarios, "verificar_google", falso_google)
    from observatorio.api.main import crear_app

    return TestClient(crear_app())


def ingresar(c, email, ok="1"):
    return c.post("/api/auth/google", json={"credential": f"{email}|{ok}"})


def test_solo_dominio_unal(cliente):
    r = ingresar(cliente, "alguien@gmail.com")
    assert r.status_code == 403 and "unal.edu.co" in r.json()["detail"]


def test_correo_no_verificado(cliente):
    assert ingresar(cliente, "x@unal.edu.co", "0").status_code == 403


def test_usuario_nuevo_queda_pendiente(cliente):
    r = ingresar(cliente, "monitor@unal.edu.co")
    assert r.status_code == 403 and "pendiente" in r.json()["detail"]


def test_admin_inicial_entra_y_aprueba(cliente):
    r = ingresar(cliente, "clagosm@unal.edu.co")
    assert r.status_code == 200
    tok = r.json()["token"]
    assert r.json()["usuario"]["rol"] == "admin"
    H = {"Authorization": f"Bearer {tok}"}
    ingresar(cliente, "monitor@unal.edu.co")
    usuarios = cliente.get("/api/usuarios", headers=H).json()
    mon = next(u for u in usuarios if u["email"] == "monitor@unal.edu.co")
    assert mon["estado"] == "pendiente"
    assert cliente.put(f"/api/usuarios/{mon['id']}", json={"estado": "aprobado"}, headers=H).status_code == 200
    r2 = ingresar(cliente, "monitor@unal.edu.co")
    assert r2.status_code == 200 and r2.json()["usuario"]["rol"] == "usuario"


def test_rutas_protegidas_y_solo_admin(cliente):
    assert cliente.get("/api/ofertas").status_code == 401
    assert cliente.get("/api/ofertas", headers={"Authorization": "Bearer basura"}).status_code == 401
    admin = ingresar(cliente, "uniic_bog@unal.edu.co").json()["token"]
    ingresar(cliente, "monitor@unal.edu.co")
    HA = {"Authorization": f"Bearer {admin}"}
    mon = next(u for u in cliente.get("/api/usuarios", headers=HA).json() if u["email"] == "monitor@unal.edu.co")
    cliente.put(f"/api/usuarios/{mon['id']}", json={"estado": "aprobado"}, headers=HA)
    HU = {"Authorization": f"Bearer {ingresar(cliente, 'monitor@unal.edu.co').json()['token']}"}
    assert cliente.get("/api/catalogo", headers=HU).status_code == 200
    assert cliente.post("/api/catalogo", json={"software": "EViews", "grupo": "X"}, headers=HU).status_code == 403
    assert cliente.post("/api/catalogo", json={"software": "EViews", "grupo": "X"}, headers=HA).status_code == 200
    assert cliente.get("/api/usuarios", headers=HU).status_code == 403
    assert cliente.post("/api/tokens-mcp", json={"nombre": "x"}, headers=HU).status_code == 200
    assert cliente.post("/api/corridas", json={"semestre": "2026-II", "corte": "inicio"}, headers=HU).status_code == 403
    assert cliente.post("/api/validacion/muestras", json={"semestre": "2026-II", "corte": "inicio", "tamano": 5}, headers=HU).status_code == 403


def test_admin_inicial_no_se_puede_degradar(cliente):
    tok = ingresar(cliente, "clagosm@unal.edu.co").json()["token"]
    H = {"Authorization": f"Bearer {tok}"}
    u = next(x for x in cliente.get("/api/usuarios", headers=H).json() if x["email"] == "clagosm@unal.edu.co")
    assert cliente.put(f"/api/usuarios/{u['id']}", json={"rol": "usuario"}, headers=H).status_code == 400


def test_lanzar_corrida_sin_github_explica_el_error(cliente):
    tok = ingresar(cliente, "clagosm@unal.edu.co").json()["token"]
    r = cliente.post("/api/corridas", json={"semestre": "2026-II", "corte": "inicio"}, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 400 and "GITHUB_TOKEN" in r.json()["detail"]


def test_lanzar_corrida_llama_workflow_dispatch(cliente, monkeypatch):
    import observatorio.corridas as corr

    monkeypatch.setenv("GITHUB_TOKEN", "ghp_prueba")
    monkeypatch.setenv("GITHUB_REPO", "its-camilo/observatorio-empleo-fce")
    monkeypatch.setenv("GITHUB_WORKFLOW", "corrida.yml")
    llamadas = []

    class Resp:
        status_code = 204
        text = ""

    monkeypatch.setattr(corr.requests, "post", lambda url, **kw: llamadas.append((url, kw["json"])) or Resp())
    tok = ingresar(cliente, "clagosm@unal.edu.co").json()["token"]
    r = cliente.post("/api/corridas", json={"semestre": "2026-ii", "corte": "Mitad"}, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text
    url, cuerpo = llamadas[0]
    assert url.endswith("/actions/workflows/corrida.yml/dispatches")
    assert cuerpo["inputs"]["semestre"] == "2026-II" and cuerpo["inputs"]["corte"] == "mitad"
    assert cuerpo["inputs"]["run_id"] == r.json()["id_ejecucion"]
    assert r.json()["estado"] == "en_cola"
    # no se puede lanzar otra mientras hay una en cola
    r2 = cliente.post("/api/corridas", json={"semestre": "2026-II", "corte": "final"}, headers={"Authorization": f"Bearer {tok}"})
    assert r2.status_code == 400


def test_csv_publico_para_power_bi(cliente):
    r = cliente.get("/api/publico/catalogo.csv")
    assert r.status_code == 200 and r.text.lstrip("\ufeff").startswith("software,grupo,sinonimos,activo")
    assert cliente.get("/api/publico/usuarios.csv").status_code == 404
