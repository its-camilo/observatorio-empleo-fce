import pytest

from observatorio.distribucion import (
    DISTRIBUCION_FUENTES_DEFECTO,
    normalizar_porcentajes,
    repartir_enteros,
    validar_distribucion,
)
from observatorio.plan_extraccion import fuentes_para_corrida, presupuesto_por_fuente, presupuesto_por_carrera


def test_repartir_enteros_suma_exacta():
    pct = {"linkedin": 42, "indeed": 30, "computrabajo": 28}
    rep = repartir_enteros(10_000, pct)
    assert sum(rep.values()) == 10_000
    assert rep["linkedin"] > rep["indeed"] > rep["computrabajo"]


def test_cero_por_ciento_desactiva_fuente():
    cfg = {
        "fuentes": {"linkedin": {"activa": True}, "indeed": {"activa": True}, "computrabajo": {"activa": True}},
        "distribucion_fuentes": {"linkedin": 50, "indeed": 50, "computrabajo": 0},
    }
    assert "computrabajo" not in fuentes_para_corrida(cfg)
    rep = presupuesto_por_fuente(100, fuentes_para_corrida(cfg), cfg)
    assert rep.get("computrabajo", 0) == 0
    assert sum(rep.values()) == 100


def test_validar_rechaza_suma_distinta():
    with pytest.raises(ValueError, match="deben sumar 100"):
        validar_distribucion({"linkedin": 40, "indeed": 40, "computrabajo": 10})


def test_normalizar_porcentajes():
    n = normalizar_porcentajes({"a": 1, "b": 1, "c": 1})
    assert abs(sum(n.values()) - 100) < 0.02


def test_presupuesto_carreras():
    cfg = {
        "carreras": ["Administración de Empresas", "Contaduría Pública", "Economía"],
        "distribucion_carreras": {"Administración de Empresas": 34, "Contaduría Pública": 33, "Economía": 33},
    }
    rep = presupuesto_por_carrera(300, cfg)
    assert sum(rep.values()) == 300


def test_defecto_fuentes_sin_google():
    assert "google" not in DISTRIBUCION_FUENTES_DEFECTO
