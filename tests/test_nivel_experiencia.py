"""RF-01: filtro por nivel de experiencia y parámetros LinkedIn."""
from __future__ import annotations

from observatorio.pipeline.nivel_experiencia import (
    NIVELES_EXPERIENCIA,
    config_niveles_defecto,
    linkedin_query_f_e,
    nivel_permitido,
    niveles_efectivos,
    normalizar_config_niveles,
)


def test_config_defecto_todos_sin_filtro():
    d = config_niveles_defecto()
    assert d["modo"] == "todos"
    assert niveles_efectivos(d) is None


def test_niveles_efectivos_todos_sin_filtro():
    assert niveles_efectivos({"modo": "todos", "niveles": NIVELES_EXPERIENCIA}) is None


def test_niveles_efectivos_alguno_restringe():
    cfg = {"modo": "algunos", "niveles": ["Practicante", "Sin experiencia / Junior"]}
    assert niveles_efectivos(cfg) == {"Practicante", "Sin experiencia / Junior"}


def test_nivel_permitido_rechaza_no_especificado_si_no_esta_en_lista():
    permitidos = {"Practicante", "Sin experiencia / Junior"}
    assert nivel_permitido("Practicante", permitidos)
    assert not nivel_permitido("Senior", permitidos)
    assert not nivel_permitido(None, permitidos)
    assert not nivel_permitido("No especificado", permitidos)


def test_linkedin_f_e_solo_junior_y_practicante():
    permitidos = {"Practicante", "Sin experiencia / Junior"}
    q = linkedin_query_f_e(permitidos)
    assert set(q.split("&")) == {"f_E=1", "f_E=2"}


def test_normalizar_lista_antigua():
    assert normalizar_config_niveles(["Practicante"]) == {
        "modo": "algunos",
        "niveles": ["Practicante"],
    }