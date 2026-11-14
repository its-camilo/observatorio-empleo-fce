"""Extracción paralela por fuente (matriz Actions) y reparto de tiempo."""
import pytest
from sqlalchemy import func, select

from observatorio import orquestador as orq
from observatorio.db.modelos import Particion
from observatorio.plan_extraccion import minutos_por_fuente, presupuesto_por_fuente


def test_minutos_por_fuente_suman_el_tiempo_total_modo_secuencial():
    """En extracción local en serie, el tiempo global se reparte entre fuentes."""
    presu = presupuesto_por_fuente(3000, ["linkedin", "indeed", "computrabajo"], {
        "distribucion_fuentes": {"linkedin": 58.33, "indeed": 25, "computrabajo": 16.67},
        "carreras": [],
    })
    m = minutos_por_fuente(320, 3000, presu, ["linkedin", "indeed", "computrabajo"])
    assert sum(m.values()) == pytest.approx(320)


def test_matriz_paralela_tiempo_completo_en_cada_job(sesion):
    ejec = orq.preparar(sesion, "2026-II", "mitad", modo="completa")
    sesion.commit()
    jobs = orq.matriz_extraccion_fuentes(sesion, ejec.id_ejecucion, 320)
    assert len(jobs) == 3
    assert all(j["max_minutos"] == 320 for j in jobs)


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


def test_preparar_reanudacion_no_sobrescribe_presupuestos_ni_particiones(sesion, monkeypatch):
    """Al reanudar (mismo run_id), cupos congelados no deben recalcularse aunque cambie la config."""
    ejec = orq.preparar(sesion, "2026-II", "mitad", id_ejecucion="2026-II-mitad-resume", modo="completa")
    ejec.parametros = {
        **(ejec.parametros or {}),
        "objetivo_ofertas_corrida": 3000,
        "presupuesto_fuentes": {"linkedin": 1750, "indeed": 750, "computrabajo": 500},
        "presupuesto_carreras": {"Administración de Empresas": 144, "Contaduría Pública": 1251, "Economía": 1605},
        "presupuesto_fuente_carrera": {
            "linkedin": {"Administración de Empresas": 84, "Contaduría Pública": 730, "Economía": 936},
            "indeed": {"Administración de Empresas": 36, "Contaduría Pública": 313, "Economía": 401},
            "computrabajo": {"Administración de Empresas": 24, "Contaduría Pública": 208, "Economía": 268},
        },
    }
    sesion.commit()
    n_antes = sesion.scalar(select(func.count()).select_from(Particion).where(Particion.id_ejecucion == ejec.id_ejecucion))
    params_antes = dict(ejec.parametros)

    cfg_vieja = orq.leer_config(sesion)
    cfg_nueva = {**cfg_vieja, "distribucion_fuentes": {"linkedin": 10, "indeed": 80, "computrabajo": 10}}
    monkeypatch.setattr(orq, "leer_config", lambda _s: cfg_nueva)

    ejec2 = orq.preparar(
        sesion,
        "2026-II",
        "mitad",
        id_ejecucion=ejec.id_ejecucion,
        modo="completa",
        fuentes=["indeed", "computrabajo"],
    )
    n_despues = sesion.scalar(select(func.count()).select_from(Particion).where(Particion.id_ejecucion == ejec.id_ejecucion))
    assert ejec2.parametros["presupuesto_fuentes"] == params_antes["presupuesto_fuentes"]
    assert ejec2.parametros["presupuesto_carreras"] == params_antes["presupuesto_carreras"]
    assert ejec2.parametros["presupuesto_fuente_carrera"] == params_antes["presupuesto_fuente_carrera"]
    assert n_despues == n_antes
