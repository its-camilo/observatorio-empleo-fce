"""Reglas de software/habilidad cursable y exclusión operativa reforzada."""

from observatorio.parametros import valores_por_defecto
from observatorio.pipeline.clasificacion import titulo_excluido_operativo
from observatorio.pipeline.valor_formativo import detectar_habilidades_tecnicas, oferta_tiene_valor_formativo


def test_auxiliar_administrativa_con_excel_sin_valor_formativo(detector):
    patrones = valores_por_defecto()["exclusion_operativa_titulo"]
    cargo = "Auxiliar administrativa"
    assert titulo_excluido_operativo(cargo, patrones)
    cargo = "Auxiliar administrativa"
    ok, _ = oferta_tiene_valor_formativo(cargo, "Manejo de Office y Excel", detector)
    assert not ok


def test_analista_administrativo_sap_sigue_relevante_y_con_valor(detector):
    patrones = valores_por_defecto()["exclusion_operativa_titulo"]
    cargo = "Analista administrativo"
    assert not titulo_excluido_operativo(cargo, patrones)
    ok, motivo = oferta_tiene_valor_formativo(cargo, "Experiencia en módulos SAP FI", detector)
    assert ok and motivo in ("software_catalogo", "habilidad_tecnica", "llm_habilidad_cursable")


def test_oferta_sin_software_ni_habilidad(detector):
    ok, motivo = oferta_tiene_valor_formativo(
        "Coordinador de proyectos",
        "Trabajo en equipo, comunicación y proactividad. Horario flexible.",
        detector,
    )
    assert not ok
    assert "sin_software" in motivo


def test_excel_avanzado_cuenta(detector):
    assert detectar_habilidades_tecnicas("Se requiere Excel avanzado y tablas dinámicas")
    ok, _ = oferta_tiene_valor_formativo("Analista de costos", "Excel avanzado obligatorio", detector)
    assert ok


def test_auxiliar_administrativo_y_contable_excluido():
    patrones = valores_por_defecto()["exclusion_operativa_titulo"]
    assert titulo_excluido_operativo("Auxiliar administrativo y contable", patrones)
    assert titulo_excluido_operativo("Asistente administrativa bilingüe", patrones)


def test_asesor_comercial_excluido_analista_no():
    patrones = valores_por_defecto()["exclusion_operativa_titulo"]
    assert titulo_excluido_operativo("Asesor comercial", patrones)
    assert titulo_excluido_operativo("asesor/a comercial", patrones)
    assert not titulo_excluido_operativo("Analista comercial", patrones)


def test_analista_crm_en_titulo(detector):
    ok, motivo = oferta_tiene_valor_formativo("Analista CRM y automatización", "", detector)
    assert ok and motivo == "habilidad_tecnica"


def test_analista_logistica_en_titulo(detector):
    ok, _ = oferta_tiene_valor_formativo("Analista de Operaciones Logísticas", "", detector)
    assert ok
