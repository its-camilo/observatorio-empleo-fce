from observatorio.plan_extraccion import (
    fuentes_para_corrida,
    max_particiones_fuente,
    objetivo_ofertas_corrida,
    ordenar_fuentes,
    presupuesto_por_fuente,
)

CFG = {
    "fuentes": {
        "linkedin": {"activa": True},
        "indeed": {"activa": True},
        "computrabajo": {"activa": True},
    },
    "distribucion_fuentes": {"linkedin": 42, "indeed": 30, "computrabajo": 28},
}


def test_orden_linkedin_primero():
    assert ordenar_fuentes(["computrabajo", "indeed", "linkedin"]) == ["linkedin", "indeed", "computrabajo"]


def test_presupuesto_suma_objetivo():
    fuentes = fuentes_para_corrida(CFG)
    rep = presupuesto_por_fuente(100, fuentes, CFG)
    assert sum(rep.values()) == 100
    assert rep["linkedin"] >= rep["indeed"] >= rep["computrabajo"]


def test_objetivo_migra_limite():
    assert objetivo_ofertas_corrida({"limite_extraccion_corrida": 200}) == 200


def test_max_particiones_por_cupo():
    assert max_particiones_fuente(38, 100) == 1
    assert max_particiones_fuente(250, 100) == 3


def test_google_no_entra_en_corrida():
    cfg = {**CFG, "fuentes": {**CFG["fuentes"], "google": {"activa": True}}}
    assert "google" not in fuentes_para_corrida(cfg, ["google", "linkedin"])
