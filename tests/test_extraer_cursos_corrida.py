"""Inserción de cursos por ejecución (re-ejecución sin violar uq_curso)."""
from __future__ import annotations

from sqlalchemy import func, select

from observatorio.db.modelos import Curso, Ejecucion
from observatorio.orquestador import extraer_cursos_corrida


def _lote_cursos() -> list[dict]:
    base = {
        "termino": "Excel",
        "titulo": "Curso",
        "organizacion": "Test",
        "nivel": None,
        "tipo": "Curso",
        "calificacion": None,
        "num_calificaciones": None,
        "inscritos_recientes": None,
    }
    return [
        {**base, "plataforma": "Coursera", "url": "https://example.test/excel-a", "posicion": 1},
        {**base, "plataforma": "edX", "url": "https://example.test/excel-a", "posicion": 1},
        {**base, "plataforma": "Coursera", "url": "https://example.test/excel-a", "posicion": 2, "titulo": "Dup"},
        {**base, "plataforma": "Platzi", "url": "https://example.test/excel-b", "posicion": 1},
    ]


def test_extraer_cursos_corrida_dos_veces_sin_duplicados(sesion, monkeypatch):
    ejec = Ejecucion(
        id_ejecucion="ec-cursos-uq",
        semestre="2026-II",
        corte="Mitad",
        estado="en_curso",
    )
    sesion.add(ejec)
    sesion.commit()

    def _fake_extraer(_plataformas, _consultas, _max_por_termino):
        return _lote_cursos(), []

    monkeypatch.setattr("observatorio.scraper.cursos.extraer_cursos", _fake_extraer)

    r1 = extraer_cursos_corrida(sesion, ejec.id_ejecucion)
    r2 = extraer_cursos_corrida(sesion, ejec.id_ejecucion)

    assert r1["cursos"] == 3
    assert r2["cursos"] == 3

    rows = list(sesion.scalars(select(Curso).where(Curso.id_ejecucion == ejec.id_ejecucion)))
    assert len(rows) == 3
    assert sesion.scalar(
        select(func.count())
        .select_from(Curso)
        .where(Curso.id_ejecucion == ejec.id_ejecucion)
    ) == 3
    claves = {(c.plataforma.lower(), c.url) for c in rows}
    assert len(claves) == 3