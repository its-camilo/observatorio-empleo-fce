"""Cursos desde demanda en ofertas y temas para dictado."""
import math
from datetime import date

import pytest

from observatorio.cursos_demanda import (
    _senal_plataforma,
    calcular_puntaje_recomendacion,
    consulta_para,
    contar_demanda_software,
    demanda_temas,
    normalizar_senales_plataforma,
    terminos_para_busqueda_cursos,
)
from observatorio.db.modelos import Ejecucion, Oferta, OfertaSoftware
from observatorio.parametros import valores_por_defecto


def _oferta(i: str, carrera: str, ejec: str) -> Oferta:
    return Oferta(
        id_oferta=f"cd-{i}",
        fuente="LinkedIn",
        carrera_principal=carrera,
        carrera=carrera,
        cargo="Analista",
        fecha_extraccion=date.today(),
        semestre="2026-II",
        corte="Mitad",
        id_ejecucion=ejec,
        descripcion="texto",
    )


def test_consulta_para_mapea_catalogo():
    assert "Power BI" in consulta_para("power bi")
    assert "NIIF" in consulta_para("niif")


def test_consulta_para_access_y_r_sin_falsos_positivos():
    assert consulta_para("Access") == "Microsoft Access base de datos"
    assert consulta_para("R") == "R estadística"
    assert consulta_para("Power Automate") == "Power Automate"
    assert consulta_para("Trello") == "Trello"
    assert consulta_para("Introduction to Web Accessibility") == "Introduction to Web Accessibility"


def test_terminos_desde_ofertas_y_fallback(sesion):
    cfg = valores_por_defecto()
    ejec = Ejecucion(id_ejecucion="cd-1", semestre="2026-II", corte="Mitad")
    sesion.add(ejec)
    for i in range(8):
        o = _oferta(str(i), "Economía", "cd-1")
        sesion.add(o)
        sesion.add(OfertaSoftware(id_oferta=o.id_oferta, software="Power BI", semestre="2026-II", corte="Mitad", carrera="Economía"))
    sesion.commit()
    terminos = terminos_para_busqueda_cursos(sesion, "2026-II", "Mitad", cfg)
    assert any(t.habilidad == "Power BI" for t in terminos)
    assert terminos[0].ofertas >= 8


@pytest.mark.parametrize(
    "curso",
    [
        {"plataforma": "edX", "posicion": 1, "inscritos_recientes": -1},
        {"plataforma": "edX", "posicion": 1, "inscritos_recientes": None},
        {"plataforma": "edX", "posicion": 1, "inscritos_recientes": "no-es-numero"},
        {"plataforma": "edX", "posicion": 1, "inscritos_recientes": float("nan")},
        {"plataforma": "Coursera", "posicion": 2, "calificacion": -3.5, "num_calificaciones": -10},
        {"plataforma": "Coursera", "posicion": 2, "calificacion": None, "num_calificaciones": "1.2k"},
        {"plataforma": "Platzi", "posicion": "bad", "calificacion": float("inf"), "num_calificaciones": -1},
    ],
)
def test_senal_plataforma_sin_domain_error_y_puntaje_acotado(curso):
    senal = _senal_plataforma(curso)
    assert math.isfinite(senal)
    assert senal >= 0
    lote = [dict(curso)]
    normalizar_senales_plataforma(lote)
    norm = lote[0]["_senal_plat"]
    assert math.isfinite(norm)
    assert 0.0 <= norm <= 1.0
    puntaje = calcular_puntaje_recomendacion(40.0, norm)
    assert 0.0 <= puntaje <= 1.0


def test_puntaje_recomendacion_pesa_demanda():
    alto = calcular_puntaje_recomendacion(80.0, 0.2, peso_demanda=0.65)
    bajo = calcular_puntaje_recomendacion(10.0, 0.9, peso_demanda=0.65)
    assert alto > bajo


def test_demanda_temas_y_variacion(sesion):
    cfg = valores_por_defecto()
    ejec1 = Ejecucion(id_ejecucion="cd-a", semestre="2026-II", corte="Inicio")
    ejec2 = Ejecucion(id_ejecucion="cd-b", semestre="2026-II", corte="Mitad")
    sesion.add_all([ejec1, ejec2])
    o1 = _oferta("a", "Economía", "cd-a")
    o1.corte = "Inicio"
    o2 = _oferta("b", "Economía", "cd-b")
    sesion.add_all([o1, o2])
    sesion.add(OfertaSoftware(id_oferta=o1.id_oferta, software="Python", semestre="2026-II", corte="Inicio", carrera="Economía"))
    sesion.add(OfertaSoftware(id_oferta=o2.id_oferta, software="Python", semestre="2026-II", corte="Mitad", carrera="Economía"))
    for i in range(4):
        oid = f"cd-b{i}"
        ob = _oferta(oid, "Economía", "cd-b")
        sesion.add(ob)
        sesion.add(OfertaSoftware(id_oferta=ob.id_oferta, software="Python", semestre="2026-II", corte="Mitad", carrera="Economía"))
    sesion.commit()
    total, conteos, _ = contar_demanda_software(sesion, "2026-II", "Mitad")
    assert conteos.get("Python") == 5  # o2 + 4 en bucle
    temas = demanda_temas(sesion, "2026-II", "Mitad", cfg, limite=10)
    py = next(t for t in temas if t["tema"] == "Python")
    assert py["variacion_pp"] is not None