from observatorio.mantenimiento import TERMINOS_BUSQUEDA_RETIRADOS
from observatorio.parametros import valores_por_defecto
from observatorio.pipeline.clasificacion import titulo_excluido_operativo


def test_terminos_retirados_incluyen_auxiliar_administrativo():
    assert "auxiliar administrativo" in TERMINOS_BUSQUEDA_RETIRADOS


def test_patron_operativo_auxiliar_admin():
    patrones = valores_por_defecto()["exclusion_operativa_titulo"]
    assert titulo_excluido_operativo("Auxiliar Administrativo - Bogotá", patrones)
    assert not titulo_excluido_operativo("Analista Administrativo", patrones)
