"""Extracción paralela por fuente (matriz Actions) y reparto de tiempo."""
from observatorio import orquestador as orq
from observatorio.plan_extraccion import minutos_por_fuente, presupuesto_por_fuente


def test_minutos_por_fuente_suman_el_tiempo_total():
    presu = presupuesto_por_fuente(3000, ["linkedin", "indeed", "computrabajo"], {
        "distribucion_fuentes": {"linkedin": 58.33, "indeed": 25, "computrabajo": 16.67},
        "carreras": [],
    })
    m = minutos_por_fuente(320, 3000, presu, ["linkedin", "indeed", "computrabajo"])
    assert sum(m.values()) == 320


def test_matriz_extraccion_un_job_por_fuente(sesion):
    ejec = orq.preparar(sesion, "2026-II", "mitad", modo="completa")
    ejec.parametros = {**(ejec.parametros or {}), "objetivo_ofertas_corrida": 500}
    sesion.commit()
    jobs = orq.matriz_extraccion_fuentes(sesion, ejec.id_ejecucion, 320)
    fuentes = {j["fuente"] for j in jobs}
    assert fuentes == {"linkedin", "indeed", "computrabajo"}
    assert all(j["max_minutos"] > 0 for j in jobs)


def test_matriz_filtra_fuentes_para_reanudar(sesion):
    ejec = orq.preparar(sesion, "2026-II", "mitad", modo="completa")
    sesion.commit()
    jobs = orq.matriz_extraccion_fuentes(sesion, ejec.id_ejecucion, 320, ["indeed", "computrabajo"])
    assert {j["fuente"] for j in jobs} == {"indeed", "computrabajo"}


def test_presupuesto_carreras_respeta_config(sesion):
    from observatorio.db.modelos import Particion

    cfg = orq.leer_config(sesion)
    ejec = orq.preparar(sesion, "2026-II", "mitad", modo="completa")
    ejec.parametros = {**(ejec.parametros or {}), "objetivo_ofertas_corrida": 3000}
    sesion.query(Particion).filter(Particion.id_ejecucion == ejec.id_ejecucion).delete()
    ejec = orq.preparar(sesion, "2026-II", "mitad", id_ejecucion=ejec.id_ejecucion, modo="completa")
    presu = ejec.parametros["presupuesto_carreras"]
    raw = cfg.get("distribucion_carreras") or {}
    total = sum(presu.values())
    assert total == 3000
    for carrera, cupo in presu.items():
        pct = float(raw.get(carrera, 0))
        esperado = int(3000 * pct / 100)
        assert abs(cupo - esperado) <= 2, (carrera, cupo, esperado)