"""Capitales departamentales: catálogo, alias y purga."""

from datetime import date

import pytest

from observatorio.capitales import (
    CAPITALES_DEPARTAMENTALES,
    capital_desde_texto,
    es_capital_departamental,
    ubicaciones_capitales_defecto,
)
from observatorio.db.modelos import Oferta
from observatorio.mantenimiento import MOTIVO_FUERA_CAPITAL, purgar_por_reglas


@pytest.mark.parametrize(
    "texto,esperada",
    [
        ("Bogotá, D.C., Colombia", "Bogotá"),
        ("Bogota D C", "Bogotá"),
        ("Medellin, Antioquia", "Medellín"),
        ("Cartagena de Indias, Bolivar", "Cartagena"),
        ("Envigado, Antioquia", None),
        ("Chía, Cundinamarca", None),
        ("Soacha, Cundinamarca", None),
        ("Bello, Antioquia", None),
        ("Colombia", None),
        ("", None),
        ("Trabajo remoto en Colombia", "Remoto"),
    ],
)
def test_capital_desde_texto(texto, esperada):
    assert capital_desde_texto(texto) == esperada


@pytest.mark.parametrize("capital", CAPITALES_DEPARTAMENTALES)
def test_todas_las_capitales_reconocidas(capital):
    assert es_capital_departamental(capital, None) is True
    assert es_capital_departamental(capital, f"{capital}, Colombia") is True


@pytest.mark.parametrize(
    "ciudad",
    ["Envigado", "Chía", "Bello", "Palmira", "Floridablanca", "Soledad", "Girardot", "Colombia"],
)
def test_municipios_no_capital(ciudad):
    assert es_capital_departamental(ciudad, None) is False


def test_envigado_antioquia_no_es_capital():
    assert es_capital_departamental("Envigado", "Envigado, Antioquia, Colombia") is False


def test_bogota_localidad_es_capital():
    assert es_capital_departamental("Bogotá", "Usaquén, Bogotá, Colombia") is True


def test_remoto_se_conserva():
    assert es_capital_departamental("Remoto", "Colombia") is True


def test_ubicaciones_defecto_son_32_capitales():
    nombres = {u["nombre"] for u in ubicaciones_capitales_defecto()}
    assert nombres == set(CAPITALES_DEPARTAMENTALES)
    assert len(nombres) == 32


def test_purga_fuera_de_capital(sesion):
    hoy = date.today()
    sesion.add_all(
        [
            Oferta(
                id_oferta="cap-1",
                fuente="LI",
                fecha_extraccion=hoy,
                semestre="2026-II",
                corte="Inicio",
                cargo="Analista",
                ciudad="Medellín",
                descripcion="SAP",
            ),
            Oferta(
                id_oferta="nc-1",
                fuente="LI",
                fecha_extraccion=hoy,
                semestre="2026-II",
                corte="Inicio",
                cargo="Analista",
                ciudad="Envigado",
                descripcion="SAP",
            ),
        ]
    )
    sesion.commit()
    res = purgar_por_reglas(sesion, aplicar=False)
    assert res["por_motivo"].get(MOTIVO_FUERA_CAPITAL, 0) == 1
    assert res["candidatas_purgables"] >= 1
