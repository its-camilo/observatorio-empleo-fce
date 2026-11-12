from observatorio.plan_extraccion import (
    max_particiones_fuente,
    objetivo_ofertas_corrida,
    ordenar_fuentes,
    presupuesto_por_fuente,
)


def test_orden_linkedin_primero():
    assert ordenar_fuentes(["google", "indeed", "linkedin"]) == ["linkedin", "indeed", "google"]


def test_presupuesto_suma_objetivo():
    fuentes = ["linkedin", "indeed", "computrabajo", "google"]
    rep = presupuesto_por_fuente(100, fuentes)
    assert sum(rep.values()) == 100
    assert rep["linkedin"] >= rep["indeed"] >= rep["google"]


def test_objetivo_migra_limite():
    assert objetivo_ofertas_corrida({"limite_extraccion_corrida": 200}) == 200


def test_max_particiones_por_cupo():
    assert max_particiones_fuente(38, 100) == 1
    assert max_particiones_fuente(250, 100) == 3
