"""Los agregados precalculados deben coincidir con el cálculo en vivo."""
from __future__ import annotations

from datetime import date

from observatorio import agregados, analisis
from observatorio.consultas import valores_filtros
from observatorio.db.modelos import Oferta


def _oferta(oid: str, sem: str, cor: str, *, carrera: str = "Economía") -> Oferta:
    return Oferta(
        id_oferta=oid,
        fuente="LinkedIn",
        fecha_extraccion=date(2026, 11, 1),
        semestre=sem,
        corte=cor,
        cargo="Analista",
        empresa="Acme",
        ciudad="Bogotá",
        tipo_oferta="Empleo",
        sector="Banca",
        carrera_principal=carrera,
        carrera=carrera,
        clave_dedup=f"k-{oid}",
    )


def test_agregados_coinciden_con_calculo_vivo(sesion):
    sesion.add_all(
        [
            _oferta("a1", "2026-II", "Inicio"),
            _oferta("a2", "2026-II", "Inicio", carrera="Contaduría Pública"),
            _oferta("a3", "2026-II", "Mitad"),
        ]
    )
    sesion.commit()

    sem, cor = "2026-II", "Mitad"
    agregados.refrescar_agregados_corte(sesion, "2026-II", "Inicio")
    agregados.refrescar_agregados_corte(sesion, sem, cor)
    sesion.commit()

    clave_resumen = f"resumen:{sem}:{cor}"
    assert agregados.leer(sesion, clave_resumen) == analisis.resumen_corte(
        sesion, sem, cor, para_dashboard=True
    )

    for carrera in agregados.CARRERAS_RANKING:
        car = carrera or None
        clave_rank = f"analisis:ranking:{sem}:{cor}:{carrera}"
        esperado = {
            "ranking": analisis.ranking(sesion, sem, cor, car),
            "grupos": analisis.ranking_por_grupo(sesion, sem, cor, car),
        }
        assert agregados.leer(sesion, clave_rank) == esperado

        assert agregados.leer(sesion, f"analisis:ranking-hab:{sem}:{cor}:{carrera}") == {
            "ranking": analisis.ranking_habilidades(sesion, sem, cor, car),
        }
        assert agregados.leer(sesion, f"analisis:ranking-tipo:{sem}:{cor}:{carrera}") == {
            "ranking": analisis.ranking_tipo_oferta(sesion, sem, cor, car),
        }

    assert agregados.leer(sesion, "filtros:ofertas") == valores_filtros(sesion)
    assert agregados.leer(sesion, "cortes_disponibles") == analisis.cortes_disponibles(sesion)

    prev = analisis.corte_anterior(sesion, sem, cor)
    if prev is not None:
        sem_a, cor_a = prev
        for carrera in agregados.CARRERAS_RANKING:
            car = carrera or None
            clave_cmp = f"analisis:comparar:{sem_a}:{cor_a}:{sem}:{cor}:{carrera}"
            assert agregados.leer(sesion, clave_cmp) == analisis.comparar(sesion, sem_a, cor_a, sem, cor, car)

    assert agregados.conteo_ofertas_precalculado(sesion, "2026-II", "Inicio", None) == 2