import pytest

from observatorio.config_esquemas import validar_valor_config
from observatorio.parametros import valores_por_defecto


def test_carreras_vacia_rechazada():
    with pytest.raises(ValueError, match="al menos una carrera"):
        validar_valor_config("carreras", [], {})


def test_tipo_oferta_invalido():
    with pytest.raises(ValueError, match="tipo_oferta"):
        validar_valor_config("tipo_oferta", "otro", {})


def test_distribucion_fuentes_suma():
    cfg = valores_por_defecto()
    with pytest.raises(ValueError):
        validar_valor_config(
            "distribucion_fuentes",
            {"linkedin": 50, "indeed": 30, "computrabajo": 10},
            cfg,
        )


def test_exclusion_lista():
    out = validar_valor_config("exclusion_titulo", ["  foo  ", "", "bar"], {})
    assert out == ["foo", "bar"]