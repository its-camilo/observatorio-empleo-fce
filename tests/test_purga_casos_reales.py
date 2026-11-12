"""Casos que en Neon se marcaban mal como sin_software_ni_habilidad."""

from datetime import date

from observatorio.db.modelos import Oferta
from observatorio.mantenimiento import (
    MOTIVO_OPERATIVO,
    MOTIVO_SIN_DESCRIPCION,
    MOTIVO_SIN_FORMATIVO,
    motivo_purga_oferta,
    purgar_por_reglas,
)
from observatorio.parametros import valores_por_defecto
from observatorio.pipeline.clasificacion import titulo_excluido_operativo
from observatorio.pipeline.valor_formativo import oferta_tiene_valor_formativo


def _motivo(detector, cargo: str, descripcion: str | None = None) -> str | None:
    patrones = valores_por_defecto()["exclusion_operativa_titulo"]
    return motivo_purga_oferta(
        cargo,
        descripcion,
        "",
        patrones=patrones,
        detector=detector,
        requiere_formativo=True,
    )


def test_analistas_con_habilidad_en_titulo_sin_descripcion(detector):
    casos = [
        "Analista CRM y automatización",
        "Analista de Inventarios Cali",
        "Analista de Mercadeo y Desarrollo de Proyectos.",
        "Analista comercial y de compras",
        "Analista de Operaciones Logísticas",
        "Analista de talento humano",
    ]
    for cargo in casos:
        ok, motivo = oferta_tiene_valor_formativo(cargo, "", detector)
        assert ok, f"{cargo} debería tener valor formativo en el título ({motivo})"
        assert _motivo(detector, cargo, "") == MOTIVO_SIN_DESCRIPCION


def test_cargos_operativos_antes_de_sin_software(detector):
    patrones = valores_por_defecto()["exclusion_operativa_titulo"]
    assert titulo_excluido_operativo("Auxiliar contable y administrativo", patrones)
    assert titulo_excluido_operativo("asesor/a comercial", patrones)
    assert _motivo(detector, "Auxiliar contable y administrativo", "Manejo de Excel") == MOTIVO_OPERATIVO
    assert _motivo(detector, "asesor/a comercial", "Ventas y atención") == MOTIVO_OPERATIVO


def test_sin_descripcion_no_cuenta_como_purgable(sesion, detector):
    hoy = date.today()
    sesion.add_all(
        [
            Oferta(
                id_oferta="nd-1",
                fuente="LinkedIn",
                fecha_extraccion=hoy,
                semestre="2026-II",
                corte="Inicio",
                cargo="Analista CRM y automatización",
                descripcion=None,
            ),
            Oferta(
                id_oferta="nd-2",
                fuente="Indeed",
                fecha_extraccion=hoy,
                semestre="2026-II",
                corte="Inicio",
                cargo="Auxiliar contable y administrativo",
                descripcion="",
            ),
        ]
    )
    sesion.commit()
    res = purgar_por_reglas(sesion, aplicar=False, max_ejemplos=20)
    assert res["total_ofertas"] >= 2
    assert res["por_motivo"].get(MOTIVO_SIN_DESCRIPCION, 0) >= 1
    assert res["por_motivo"].get(MOTIVO_OPERATIVO, 0) >= 1
    assert res["candidatas_purgables"] == res["por_motivo"].get(MOTIVO_OPERATIVO, 0)
    assert MOTIVO_SIN_FORMATIVO not in res["por_motivo"] or res["por_motivo"][MOTIVO_SIN_FORMATIVO] == 0
    assert "ejemplos" in res and len(res["ejemplos"]) >= 2
    assert "por_fuente_purgables" in res


def test_vista_previa_incluye_fragmento_descripcion(sesion):
    hoy = date.today()
    sesion.add(
        Oferta(
            id_oferta="desc-1",
            fuente="CT",
            fecha_extraccion=hoy,
            semestre="2026-II",
            corte="Inicio",
            cargo="Analista financiero",
            descripcion="Trabajo en equipo, comunicación y proactividad. Sin herramientas.",
        )
    )
    sesion.commit()
    res = purgar_por_reglas(sesion, aplicar=False)
    assert res["por_motivo"][MOTIVO_SIN_FORMATIVO] == 1
    frag = next(e for e in res["ejemplos"] if e["id_oferta"] == "desc-1")
    assert "Trabajo en equipo" in frag["descripcion_fragmento"]
