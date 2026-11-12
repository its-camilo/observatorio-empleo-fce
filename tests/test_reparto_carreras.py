"""Corrida 2026-II-mitad-c224f7: con objetivo 500 todas las consultas quedaron en Administración
y Indeed/Computrabajo se marcaron 'hechas' sin consultar. Estas pruebas cubren ese caso."""
from collections import Counter

from observatorio import orquestador as orq
from observatorio.db.modelos import Particion


def _preparar(sesion, objetivo=500):
    cfg = orq.leer_config(sesion)
    ejec = orq.preparar(sesion, "2026-II", "mitad", modo="completa")
    ejec.parametros = {**(ejec.parametros or {}), "objetivo_ofertas_corrida": objetivo}
    sesion.query(Particion).filter(Particion.id_ejecucion == ejec.id_ejecucion).delete()
    ejec = orq.preparar(sesion, "2026-II", "mitad", id_ejecucion=ejec.id_ejecucion, modo="completa")
    return cfg, ejec


def test_consultas_repartidas_entre_las_tres_carreras(sesion):
    _, ejec = _preparar(sesion)
    parts = list(sesion.query(Particion).filter(Particion.id_ejecucion == ejec.id_ejecucion))
    for fuente in {p.fuente for p in parts}:
        carreras = Counter(p.carrera for p in parts if p.fuente == fuente)
        assert len(carreras) == 3, (fuente, carreras)


def test_consultas_intercaladas_por_carrera(sesion):
    _, ejec = _preparar(sesion)
    li = [p.carrera for p in sesion.query(Particion).filter(
        Particion.id_ejecucion == ejec.id_ejecucion, Particion.fuente == "linkedin").order_by(Particion.id)]
    assert len(set(li[:3])) == 3


def test_presupuesto_fuente_carrera_guardado(sesion):
    _, ejec = _preparar(sesion)
    fc = ejec.parametros["presupuesto_fuente_carrera"]
    for f, cupo in ejec.parametros["presupuesto_fuentes"].items():
        assert sum(fc[f].values()) == cupo
