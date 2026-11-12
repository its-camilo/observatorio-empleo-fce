from __future__ import annotations

import uuid
from datetime import timedelta

from observatorio.corridas import lanzar, progreso
from observatorio.corridas_cierre import (
    cerrar_ejecucion_error,
    reconciliar_ejecucion,
    estado_github,
)
from observatorio.db.modelos import Ejecucion, Particion, ahora
from observatorio.db.sesion import crear_tablas, fabrica_sesiones, motor
from observatorio.orquestador import cerrar_corrida_workflow


def _sesion():
    url = f"sqlite:///:memory:{uuid.uuid4().hex}"
    motor(url)
    crear_tablas(url)
    return fabrica_sesiones(url)()


def test_cerrar_ejecucion_marca_terminada_fallida():
    with _sesion() as s:
        ejec = Ejecucion(id_ejecucion="2026-II-mitad-f8bd05", semestre="2026-II", corte="Mitad", estado="en_curso", fase="mini_corrida")
        ejec.inicio = ahora() - timedelta(hours=50)
        s.add(ejec)
        s.commit()
        assert cerrar_ejecucion_error(s, ejec, "Workflow falló", conclusion_github="failure")
        s.commit()
        assert ejec.estado in ("fallida", "incompleta")
        assert ejec.fase == "terminada"
        assert ejec.fin is not None
        assert "Workflow falló" in (ejec.errores or "")


def test_reconciliar_por_github_failure(monkeypatch):
    with _sesion() as s:
        ejec = Ejecucion(
            id_ejecucion="2026-II-mitad-abc123",
            semestre="2026-II",
            corte="Mitad",
            estado="en_curso",
            fase="mini_corrida",
            ejecutor="github",
            github_run_url="https://github.com/its-camilo/observatorio-empleo-fce/actions/runs/999001",
        )
        s.add(ejec)
        s.commit()

        def fake_estado(_id, url=None):
            return {"estado": "completed", "conclusion": "failure", "url": url}

        monkeypatch.setenv("GITHUB_REPO", "its-camilo/observatorio-empleo-fce")
        monkeypatch.setattr("observatorio.corridas_cierre.estado_github", fake_estado)
        assert reconciliar_ejecucion(s, ejec, consultar_github=True, persistir=True, horas_max_huerfana=9999)
        s.commit()
        assert ejec.estado in ("fallida", "incompleta")
        assert ejec.fase == "terminada"


def test_reconciliar_corrida_antigua_sin_github():
    with _sesion() as s:
        ejec = Ejecucion(id_ejecucion="vieja-colgada", semestre="2026-II", corte="Inicio", estado="en_curso", ejecutor="github")
        ejec.creado_en = ahora() - timedelta(hours=48)
        ejec.inicio = ejec.creado_en
        s.add(ejec)
        s.commit()
        assert reconciliar_ejecucion(s, ejec, consultar_github=False)
        assert ejec.estado in ("fallida", "incompleta")
        assert ejec.fase == "terminada"


def test_progreso_no_muestra_en_curso_tras_reconciliar(monkeypatch):
    with _sesion() as s:
        ejec = Ejecucion(
            id_ejecucion="2026-II-inicio-xyz",
            semestre="2026-II",
            corte="Inicio",
            estado="en_curso",
            ejecutor="github",
        )
        ejec.creado_en = ahora() - timedelta(hours=40)
        ejec.inicio = ejec.creado_en
        s.add(ejec)
        s.commit()

        monkeypatch.setattr(
            "observatorio.corridas_cierre.estado_github",
            lambda *_a, **_k: None,
        )
        p = progreso(s, ejec, consultar_github=True)
        assert p["estado"] != "en_curso"
        assert ejec.fase == "terminada"


def test_cerrar_corrida_workflow_idempotente():
    with _sesion() as s:
        ejec = Ejecucion(id_ejecucion="idem-1", semestre="2026-II", corte="Inicio", estado="completada", fase="terminada")
        s.add(ejec)
        s.commit()
        cerrar_corrida_workflow(s, "idem-1", "no debería cambiar")
        assert ejec.estado == "completada"


def test_reconciliar_incompleta_si_hubo_particiones_hechas(monkeypatch):
    with _sesion() as s:
        ejec = Ejecucion(id_ejecucion="parcial", semestre="2026-II", corte="Inicio", estado="en_curso", ejecutor="github")
        s.add(ejec)
        s.add(
            Particion(
                id_ejecucion="parcial",
                fuente="linkedin",
                estado="hecha",
                termino="administración",
                ubicacion="Bogotá",
            )
        )
        s.commit()

        def fake(_id, url=None):
            return {"estado": "completed", "conclusion": "failure", "url": url}

        monkeypatch.setattr("observatorio.corridas_cierre.estado_github", fake)
        reconciliar_ejecucion(s, ejec, horas_max_huerfana=9999)
        assert ejec.estado == "incompleta"


def test_estado_github_acepta_run_url_sin_token(monkeypatch):
    class Resp:
        status_code = 200

        def json(self):
            return {"status": "completed", "conclusion": "failure", "html_url": "https://github.com/x/y/actions/runs/1", "run_started_at": None}

    monkeypatch.setenv("GITHUB_REPO", "its-camilo/observatorio-empleo-fce")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr("observatorio.corridas_cierre.requests.get", lambda *a, **k: Resp())
    gh = estado_github("cualquiera", "https://github.com/its-camilo/observatorio-empleo-fce/actions/runs/12345")
    assert gh and gh["conclusion"] == "failure"


def test_lanzar_permite_si_corrida_colgada_fue_reconciliada(monkeypatch):
    with _sesion() as s:
        ejec = Ejecucion(id_ejecucion="colgada", semestre="2026-II", corte="Inicio", estado="en_curso")
        ejec.creado_en = ahora() - timedelta(hours=40)
        ejec.inicio = ejec.creado_en
        s.add(ejec)
        s.commit()

        def fake_dispatch(*_a, **_k):
            class R:
                status_code = 204

            return R()

        monkeypatch.setenv("GITHUB_TOKEN", "gh-test")
        monkeypatch.setenv("GITHUB_REPO", "its-camilo/observatorio-empleo-fce")
        monkeypatch.setenv("GITHUB_WORKFLOW", "corrida.yml")
        monkeypatch.setattr("observatorio.corridas.requests.post", fake_dispatch)
        monkeypatch.setattr("observatorio.corridas_cierre.estado_github", lambda *_a, **_k: None)

        nueva = lanzar(s, "2026-II", "inicio", "test@unal.edu.co")
        assert nueva.estado == "en_cola"
        s.refresh(ejec)
        assert ejec.estado in ("fallida", "incompleta")
