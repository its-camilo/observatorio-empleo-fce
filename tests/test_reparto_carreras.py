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


def test_relleno_llega_al_objetivo_con_consultas_pobres(sesion, monkeypatch):
    """Sin relleno entre fuentes: las tres fuentes aportan crudas y ninguna carrera queda en cero."""
    import itertools

    from observatorio.db.modelos import Ejecucion
    from observatorio.scraper.base import OfertaCrudaDatos

    contador = itertools.count()

    class Pobre:
        def extraer(self, c, ya_existe):
            for _ in range(5):  # cada consulta trae sólo 5 ofertas
                i = next(contador)
                yield OfertaCrudaDatos(fuente={"linkedin": "LinkedIn", "indeed": "Indeed"}.get(c.fuente, "Computrabajo"),
                                       id_fuente=f"x{i}", url=f"https://e/{i}", cargo=c.termino, descripcion="d")

    monkeypatch.setattr(orq, "crear_extractor", lambda f, cfg: Pobre())
    e = Ejecucion(id_ejecucion="r1", semestre="2026-II", corte="Mitad", parametros={"objetivo_ofertas_corrida": 300})
    sesion.add(e)
    sesion.flush()
    orq.preparar(sesion, "2026-II", "mitad", id_ejecucion="r1")
    orq.extraer_secuencial(sesion, "r1")
    total = orq.contar_crudas_ejecucion(sesion, "r1")
    assert total > 0
    por_fuente = {f: orq.contar_crudas_fuente(sesion, "r1", f) for f in ("linkedin", "indeed", "computrabajo")}
    assert min(por_fuente.values()) > 0, por_fuente
    por_carrera = {c: orq.contar_crudas_carrera(sesion, "r1", c) for c in e.parametros["presupuesto_carreras"]}
    assert min(por_carrera.values()) > 0


def test_objetivo_alcanzado_no_deja_corrida_incompleta(sesion, monkeypatch):
    """Corrida 2026-II-mitad-48d007: llegó a 200/200 y quedó "incompleta" por 36 consultas de relleno sin hacer."""
    import itertools

    from observatorio.db.modelos import Ejecucion
    from observatorio.scraper.base import OfertaCrudaDatos

    contador = itertools.count()

    class Rica:
        def extraer(self, c, ya_existe):
            for _ in range(40):
                i = next(contador)
                yield OfertaCrudaDatos(fuente={"linkedin": "LinkedIn", "indeed": "Indeed"}.get(c.fuente, "Computrabajo"),
                                       id_fuente=f"y{i}", url=f"https://e/y{i}", cargo=c.termino, descripcion="d")

    monkeypatch.setattr(orq, "crear_extractor", lambda f, cfg: Rica())
    e = Ejecucion(id_ejecucion="r2", semestre="2026-II", corte="Mitad", parametros={"objetivo_ofertas_corrida": 100})
    sesion.add(e)
    sesion.flush()
    orq.preparar(sesion, "2026-II", "mitad", id_ejecucion="r2")
    orq.extraer_secuencial(sesion, "r2")
    assert orq.contar_crudas_ejecucion(sesion, "r2") >= 100
    orq.finalizar(sesion, e)
    assert e.estado == "completada", (e.estado, e.errores)
    assert not any("sin hacer" in x for x in (e.errores_detalle or []))
