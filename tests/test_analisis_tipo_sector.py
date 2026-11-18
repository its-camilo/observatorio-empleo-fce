"""Rankings y comparación por tipo de oferta y sector (RF-12/13)."""
from __future__ import annotations

from datetime import date

from observatorio import analisis
from observatorio.analisis import ETIQUETA_SIN_DATO
from observatorio.db.modelos import Oferta


def _oferta(oid: str, sem: str, cor: str, *, tipo: str | None, sector: str | None, carrera: str) -> Oferta:
    return Oferta(
        id_oferta=oid,
        fuente="LinkedIn",
        fecha_extraccion=date(2026, 11, 1),
        semestre=sem,
        corte=cor,
        cargo="Analista",
        empresa="Acme",
        ciudad="Bogotá",
        tipo_oferta=tipo,
        sector=sector,
        carrera_principal=carrera,
        carrera=carrera,
        clave_dedup=f"k-{oid}",
    )


def test_ranking_tipo_oferta_y_sector(sesion):
    sesion.add_all(
        [
            _oferta("t1", "2026-II", "Inicio", tipo="Empleo", sector="Banca", carrera="Economía"),
            _oferta("t2", "2026-II", "Inicio", tipo="Empleo", sector=None, carrera="Economía"),
            _oferta("t3", "2026-II", "Inicio", tipo="Práctica/pasantía", sector="Banca", carrera="Economía"),
        ]
    )
    sesion.commit()
    rk_t = analisis.ranking_tipo_oferta(sesion, "2026-II", "Inicio", "Economía", con_variacion=False)
    assert {r["tipo_oferta"]: r["ofertas"] for r in rk_t} == {"Empleo": 2, "Práctica/pasantía": 1}
    rk_s = analisis.ranking_sector(sesion, "2026-II", "Inicio", "Economía", con_variacion=False)
    by = {r["sector"]: r["ofertas"] for r in rk_s}
    assert by["Banca"] == 2
    assert by[ETIQUETA_SIN_DATO] == 1
    assert rk_s[-1]["sector"] == ETIQUETA_SIN_DATO


def test_comparar_incluye_tipo_y_sector(sesion):
    for oid, cor, tipo in (("c1", "Inicio", "Empleo"), ("c2", "Inicio", "Empleo"), ("c3", "Mitad", "Práctica/pasantía")):
        sesion.add(_oferta(oid, "2026-II", cor, tipo=tipo, sector="Servicios financieros", carrera="Economía"))
    sesion.commit()
    res = analisis.comparar(sesion, "2026-II", "Inicio", "2026-II", "Mitad", "Economía")
    assert "tipos_oferta" in res and "sectores" in res
    tipos = {x["tipo_oferta"]: x for x in res["tipos_oferta"]}
    assert tipos["Empleo"]["estado"] == "desapareció"
    assert tipos["Práctica/pasantía"]["estado"] == "nuevo"
    sectores = {x["sector"]: x for x in res["sectores"]}
    assert sectores["Servicios financieros"]["porcentaje_a"] == 100.0