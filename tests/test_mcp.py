import pytest
from fastapi.testclient import TestClient

H = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json", "mcp-protocol-version": "2025-06-18"}


@pytest.fixture()
def cliente(bd, monkeypatch):
    monkeypatch.setenv("AUTH_DEV_MODE", "true")
    from observatorio.api.main import crear_app

    return TestClient(crear_app())


def rpc(c, metodo, params=None, token=None, id_=1):
    cab = dict(H)
    if token:
        cab["Authorization"] = f"Bearer {token}"
    r = c.post("/mcp", headers=cab, json={"jsonrpc": "2.0", "id": id_, "method": metodo, "params": params or {}})
    assert r.status_code == 200, r.text
    return r.json()


def herramientas(c, token=None):
    return {t["name"] for t in rpc(c, "tools/list", token=token)["result"]["tools"]}


def test_inicializa_sin_login(cliente):
    r = rpc(cliente, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}})
    assert r["result"]["serverInfo"]["name"] == "observatorio-empleo-fce"


def test_solo_lectura_sin_token(cliente):
    h = herramientas(cliente)
    assert {"buscar_ofertas_empleo", "ranking_software", "comparar_cortes", "listar_catalogo", "listar_ejecuciones",
            "listar_cursos_tendencia", "resumen_corte"} <= h
    assert "lanzar_corrida" not in h and "estado_corrida" not in h
    assert not any("usuario" in x or "validacion" in x or "token" in x for x in h)
    r = rpc(cliente, "tools/call", {"name": "lanzar_corrida", "arguments": {"semestre": "2026-II", "corte": "inicio"}})
    assert r["result"]["isError"] is True


def test_herramienta_de_lectura(cliente):
    r = rpc(cliente, "tools/call", {"name": "listar_catalogo", "arguments": {}})
    texto = "".join(x.get("text", "") for x in r["result"]["content"])
    assert "Power BI" in texto
    r = rpc(cliente, "tools/call", {"name": "buscar_ofertas_empleo", "arguments": {"tamano": 500}})
    assert r["result"].get("isError") is not True


def test_token_admin_habilita_herramientas_y_se_revoca(cliente):
    sesion = cliente.post("/api/auth/dev", json={"email": "clagosm@unal.edu.co"}).json()["token"]
    HA = {"Authorization": f"Bearer {sesion}"}
    t = cliente.post("/api/tokens-mcp", json={"nombre": "prueba"}, headers=HA).json()
    assert t["token"].startswith("obs_")
    assert {"lanzar_corrida", "estado_corrida"} <= herramientas(cliente, t["token"])
    r = rpc(cliente, "tools/call", {"name": "estado_corrida", "arguments": {"run_id": "no-existe"}}, token=t["token"])
    assert r["result"]["isError"] is True and "No existe" in r["result"]["content"][0]["text"]
    cliente.delete(f"/api/tokens-mcp/{t['id']}", headers=HA)
    assert "lanzar_corrida" not in herramientas(cliente, t["token"])
    assert "lanzar_corrida" not in herramientas(cliente, "obs_inventado")


def test_token_usuario_solo_lectura_en_mcp(cliente):
    admin = cliente.post("/api/auth/dev", json={"email": "uniic_bog@unal.edu.co"}).json()["token"]
    HA = {"Authorization": f"Bearer {admin}"}
    mon = cliente.get("/api/usuarios", headers=HA).json()
    u = next(x for x in mon if x["email"] == "monitor@unal.edu.co") if any(x["email"] == "monitor@unal.edu.co" for x in mon) else None
    if u is None:
        cliente.post("/api/auth/dev", json={"email": "monitor@unal.edu.co"})
        u = next(x for x in cliente.get("/api/usuarios", headers=HA).json() if x["email"] == "monitor@unal.edu.co")
    cliente.put(f"/api/usuarios/{u['id']}", json={"estado": "aprobado"}, headers=HA)
    sesion = cliente.post("/api/auth/dev", json={"email": "monitor@unal.edu.co"}).json()["token"]
    HU = {"Authorization": f"Bearer {sesion}"}
    t = cliente.post("/api/tokens-mcp", json={"nombre": "lectura"}, headers=HU).json()
    h = herramientas(cliente, t["token"])
    assert "estado_corrida" in h and "lanzar_corrida" not in h
    r = rpc(cliente, "tools/call", {"name": "lanzar_corrida", "arguments": {"semestre": "2026-II", "corte": "inicio"}}, token=t["token"])
    assert r["result"]["isError"] is True


def test_token_guardado_solo_como_hash(cliente, sesion):
    from observatorio.db.modelos import TokenMcp

    tok = cliente.post("/api/auth/dev", json={"email": "clagosm@unal.edu.co"}).json()["token"]
    t = cliente.post("/api/tokens-mcp", json={"nombre": "x"}, headers={"Authorization": f"Bearer {tok}"}).json()["token"]
    filas = sesion.query(TokenMcp).all()
    assert filas and all(f.hash != t and t not in f.hash for f in filas)


def test_limite_por_ip():
    from observatorio.mcp_servidor import LimitadorPorIp

    lim = LimitadorPorIp(por_minuto=3)
    assert [lim.permitir("1.1.1.1") for _ in range(4)] == [True, True, True, False]
    assert lim.permitir("2.2.2.2")
