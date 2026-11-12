import observatorio.pipeline.openrouter_modelos as om


def test_es_modelo_gratis_por_sufijo_y_precio():
    assert om.es_modelo_gratis({"id": "x/model:free", "pricing": {"prompt": "1", "completion": "1"}})
    assert om.es_modelo_gratis({"id": "x/model", "pricing": {"prompt": "0", "completion": "0"}})
    assert not om.es_modelo_gratis({"id": "x/paid", "pricing": {"prompt": "0.001", "completion": "0.002"}})


def test_resolver_prioriza_preferidos_disponibles(monkeypatch):
    om._cache_catalogo.clear()
    om._cache_por_corrida.clear()

    def _fake(_key):
        return {"m1:free", "m2:free", "viejo:free"}

    monkeypatch.setattr(om, "_catalogo_gratis", _fake)
    got = om.resolver_modelos(
        preferidos=["viejo:free", "m1:free", "otro"],
        api_key="sk-x",
        id_corrida="run-1",
    )
    assert got[0] == "viejo:free"
    assert got[1] == "m1:free"
    assert "m2:free" in got
    assert om.resolver_modelos(preferidos=["viejo:free"], api_key="sk-x", id_corrida="run-1") == got


def test_resolver_sin_gratis_no_usa_lista_obsoleta(monkeypatch):
    om._cache_catalogo.clear()
    om._cache_por_corrida.clear()
    monkeypatch.setattr(om, "_catalogo_gratis", lambda _k: set())
    got = om.resolver_modelos(
        preferidos=["meta-llama/llama-3.3-70b-instruct:free"],
        api_key="sk-x",
        id_corrida=None,
    )
    assert got == []


def test_cliente_llm_resuelve_modelos(monkeypatch, sesion):
    from observatorio.pipeline.llm import ClienteLLM

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-prueba")
    monkeypatch.setattr(
        om,
        "resolver_modelos",
        lambda **kw: ["openrouter/free", "google/gemma-4-31b-it:free"],
    )
    c = ClienteLLM(sesion, {"habilitado": True}, ["Economía"], id_corrida="t-llm")
    assert c.habilitado
    assert c.modelos[0] == "openrouter/free"
