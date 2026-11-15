"""RF-18 habilidades blandas e idiomas."""
from __future__ import annotations

from observatorio.db.semilla import sembrar_habilidades_idiomas
from observatorio.pipeline.detector_habilidades_idiomas import DetectorHabilidadesIdiomas

SNIPPET_IDIOMAS = """
Buscamos profesional con inglés B2 o nivel avanzado, trabajo en equipo y comunicación asertiva.
"""

SNIPPET_SOLO_BLANDAS = """
Perfil con liderazgo, resolución de problemas, pensamiento analítico y orientación al cliente.
"""


def test_detector_idiomas_y_blandas(sesion):
    sembrar_habilidades_idiomas(sesion)
    sesion.commit()
    det = DetectorHabilidadesIdiomas.desde_bd(sesion)
    idiomas = det.detectar_idiomas(SNIPPET_IDIOMAS)
    assert any(x.idioma == "Inglés" for x in idiomas)
    assert any((x.nivel or "").upper().startswith("B2") or "avanzado" in (x.nivel or "").lower() for x in idiomas)
    blandas = det.detectar_blandas(SNIPPET_IDIOMAS)
    nombres = {b.habilidad for b in blandas}
    assert "Trabajo en equipo" in nombres
    assert "Comunicación" in nombres


def test_detector_blandas_lista_rf(sesion):
    sembrar_habilidades_idiomas(sesion)
    sesion.commit()
    det = DetectorHabilidadesIdiomas.desde_bd(sesion)
    blandas = {b.habilidad for b in det.detectar_blandas(SNIPPET_SOLO_BLANDAS)}
    for esperada in ("Liderazgo", "Resolución de problemas", "Pensamiento analítico", "Servicio al cliente"):
        assert esperada in blandas