"""§9.1 sector: normalización, extracción, inferencia y backfill."""
from __future__ import annotations

from datetime import date

from observatorio.db.modelos import Oferta
from observatorio.pipeline.limpieza import normalizar_cruda
from observatorio.pipeline.sector import (
    backfill_sectores,
    construir_mapa_sector_por_empresa,
    extraer_sector_texto,
    inferir_sector_empresa,
    normalizar_sector,
    sector_desde_fuente,
)
from observatorio.pipeline.sectores_taxonomia import SECTORES_CANONICOS, sector_canonico


def test_normalizar_sector_ingles_a_espanol():
    assert normalizar_sector("Financial Services") == "Servicios financieros"
    assert normalizar_sector("software development") == "Desarrollo de software"


def test_extraer_sector_computrabajo():
    texto = "Requisitos:\nSector: Banca\nSalario competitivo"
    assert extraer_sector_texto(texto) == "Banca"


def test_sector_desde_fuente_prioriza_metadato():
    assert sector_desde_fuente("Retail", "Sector: Banca") == "Comercio al por menor"


def test_limpieza_sector_desde_linea_ct():
    row = normalizar_cruda(
        {
            "fuente": "Computrabajo",
            "id_fuente": "99",
            "cargo": "Analista",
            "empresa": "Banco X",
            "ubicacion": "Bogotá",
            "descripcion": "Sector: Servicios financieros\nExcel",
        },
        termino="x",
        carrera_termino="Economía",
        semestre="2026-II",
        corte="Inicio",
        fecha_extraccion=date(2026, 11, 1),
        id_ejecucion="t",
    )
    assert row["sector"] == "Servicios financieros"


def _oferta(oid: str, empresa: str, sector: str | None) -> Oferta:
    return Oferta(
        id_oferta=oid,
        fuente="LinkedIn",
        fecha_extraccion=date(2026, 11, 1),
        semestre="2026-II",
        corte="Inicio",
        cargo="Analista",
        empresa=empresa,
        sector=sector,
        ciudad="Bogotá",
        carrera_principal="Economía",
        clave_dedup=f"k-{oid}",
    )


def test_mapa_e_inferencia_por_empresa(sesion):
    sesion.add(_oferta("s1", "Acme Colombia SAS", "Banca"))
    sesion.add(_oferta("s2", "Acme Colombia S.A.S.", "Banca"))
    sesion.add(_oferta("s3", "Acme Colombia SAS", None))
    sesion.commit()
    mapa = construir_mapa_sector_por_empresa(sesion, min_ofertas=2)
    assert inferir_sector_empresa("Acme Colombia", mapa) == "Banca"


def test_taxonomia_canonica_limite_y_compuestos():
    assert len(SECTORES_CANONICOS) <= 100
    assert sector_canonico("Consulting And Business Services") == "Consultoría y servicios a empresas"
    assert sector_canonico("Banca y Servicios financieros") == "Banca"
    assert sector_canonico(
        "Servicios financieros, Servicios y consultoría de TI y Tecnología, información e internet"
    ) == "Servicios financieros"


def test_backfill_renormaliza_sector_existente(sesion):
    sesion.add(_oferta("r1", "Unico SA", "Consulting And Business Services"))
    sesion.add(_oferta("r2", "Unico SA", "Retail"))
    sesion.commit()
    prev = backfill_sectores(sesion, aplicar=False)
    assert prev["ofertas_renormalizadas"] == 2
    assert prev["sectores_distintos_antes"] == 2
    assert prev["sectores_distintos_despues"] <= 2
    assert sesion.get(Oferta, "r1").sector == "Consulting And Business Services"
    backfill_sectores(sesion, aplicar=True)
    sesion.commit()
    assert sesion.get(Oferta, "r1").sector == "Consultoría y servicios a empresas"
    assert sesion.get(Oferta, "r2").sector == "Comercio al por menor"


def test_backfill_sector_vista_previa_y_aplicar(sesion):
    sesion.add(_oferta("b1", "Gamma LTDA", "Tecnología, información e internet"))
    sesion.add(_oferta("b2", "Gamma LTDA", "Tecnología, información e internet"))
    sesion.add(_oferta("b3", "Gamma LTDA", None))
    sesion.commit()
    prev = backfill_sectores(sesion, aplicar=False)
    assert prev["aplicar"] is False
    assert prev["ofertas_actualizadas"] == 1
    assert prev["sin_sector_despues"] == prev["sin_sector_antes"] - 1
    assert sesion.get(Oferta, "b3").sector is None
    applied = backfill_sectores(sesion, aplicar=True)
    sesion.commit()
    assert applied["ofertas_actualizadas"] == 1
    assert sesion.get(Oferta, "b3").sector == "Tecnología, información e internet"