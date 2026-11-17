"""Reanudar corrida y reintentar consolidación vía API."""
from __future__ import annotations

import pytest

import observatorio.corridas as corr

pytest_plugins = ["tests.test_api_auth"]
from observatorio.db.modelos import Ejecucion, OfertaCruda, Particion

from tests.test_api_auth import ingresar


def _headers_admin(cliente):
    tok = ingresar(cliente, "clagosm@unal.edu.co").json()["token"]
    return {"Authorization": f"Bearer {tok}"}


def _ejec_incompleta(sesion, id_ej: str, *, pendientes: int = 0, estado: str = "incompleta") -> None:
    ej = Ejecucion(
        id_ejecucion=id_ej,
        semestre="2026-II",
        corte="Mitad",
        ejecutado_por="test@unal.edu.co",
        estado=estado,
        fase="terminada",
        modo="completa",
        ejecutor="github",
    )
    sesion.add(ej)
    for i in range(pendientes):
        sesion.add(
            Particion(
                id_ejecucion=id_ej,
                fuente="linkedin",
                termino=f"t{i}",
                carrera="Economía",
                ubicacion=f"Bogotá-{i}",
                estado="pendiente",
            )
        )
    if pendientes == 0 and estado in ("incompleta", "fallida"):
        sesion.add(
            OfertaCruda(
                id_ejecucion=id_ej,
                fuente="LinkedIn",
                id_fuente="x1",
                termino="excel",
                carrera_termino="Economía",
                ubicacion="Bogotá",
                datos={},
            )
        )
    sesion.commit()


def test_reanudar_rechaza_si_no_resumible(cliente, sesion):
    _ejec_incompleta(sesion, "ec-ok", pendientes=0, estado="completada")
    H = _headers_admin(cliente)
    r = cliente.post("/api/corridas/ec-ok/reanudar", headers=H)
    assert r.status_code == 400
    assert "no se puede reanudar" in r.json()["detail"].lower()


def test_reanudar_rechaza_si_en_curso(cliente, sesion):
    _ejec_incompleta(sesion, "ec-run", pendientes=5)
    ej = sesion.get(Ejecucion, "ec-run")
    ej.estado = "en_curso"
    sesion.commit()
    H = _headers_admin(cliente)
    r = cliente.post("/api/corridas/ec-run/reanudar", headers=H)
    assert r.status_code == 400 and "en marcha" in r.json()["detail"].lower()


def test_reanudar_dispatched_con_mismo_run_id(cliente, sesion, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_prueba")
    monkeypatch.setenv("GITHUB_REPO", "its-camilo/observatorio-empleo-fce")
    monkeypatch.setenv("GITHUB_WORKFLOW", "corrida.yml")
    llamadas = []

    class Resp:
        status_code = 204
        text = ""

    monkeypatch.setattr(corr.requests, "post", lambda url, **kw: llamadas.append(kw["json"]) or Resp())
    _ejec_incompleta(sesion, "2026-ii-mitad-d494cf", pendientes=48)
    H = _headers_admin(cliente)
    r = cliente.post("/api/corridas/2026-ii-mitad-d494cf/reanudar", headers=H)
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "en_cola"
    assert llamadas[0]["inputs"]["run_id"] == "2026-ii-mitad-d494cf"
    assert llamadas[0]["inputs"]["fase"] == "completa"
    assert llamadas[0]["inputs"]["ejecutado_por"] == "clagosm@unal.edu.co"


def test_reintentar_consolidacion_solo_consolidar(cliente, sesion, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_prueba")
    monkeypatch.setenv("GITHUB_REPO", "its-camilo/observatorio-empleo-fce")
    llamadas = []

    class Resp:
        status_code = 204
        text = ""

    monkeypatch.setattr(corr.requests, "post", lambda url, **kw: llamadas.append(kw["json"]) or Resp())
    _ejec_incompleta(sesion, "ec-cons", pendientes=0, estado="fallida")
    H = _headers_admin(cliente)
    r = cliente.post("/api/corridas/ec-cons/reintentar-consolidacion", headers=H)
    assert r.status_code == 200
    assert llamadas[0]["inputs"]["fase"] == "solo_consolidar"
    assert llamadas[0]["inputs"]["run_id"] == "ec-cons"


def test_reintentar_rechaza_con_pendientes(cliente, sesion):
    _ejec_incompleta(sesion, "ec-pend", pendientes=3, estado="incompleta")
    H = _headers_admin(cliente)
    r = cliente.post("/api/corridas/ec-pend/reintentar-consolidacion", headers=H)
    assert r.status_code == 400
    assert "consultas pendientes" in r.json()["detail"].lower()


def test_terminar_marca_omitida_y_estado_manual(cliente, sesion):
    _ejec_incompleta(sesion, "ec-fin", pendientes=3)
    H = _headers_admin(cliente)
    r = cliente.post("/api/corridas/ec-fin/terminar", headers=H)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["estado"] == "terminada_manual"
    assert data["acciones"]["puede_terminar"] is False
    from sqlalchemy import select

    from observatorio.db.modelos import Particion

    omitidas = list(
        sesion.scalars(select(Particion).where(Particion.id_ejecucion == "ec-fin", Particion.estado == "omitida"))
    )
    assert len(omitidas) == 3
    assert any("Se omitieron 3 consultas" in (x or "") for x in (data.get("errores_detalle") or []))


def test_terminar_sin_consolidacion_previa_dispara_solo_consolidar(cliente, sesion, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_prueba")
    monkeypatch.setenv("GITHUB_REPO", "its-camilo/observatorio-empleo-fce")
    llamadas = []

    class Resp:
        status_code = 204
        text = ""

    monkeypatch.setattr(corr.requests, "post", lambda url, **kw: llamadas.append(kw["json"]) or Resp())
    ej = Ejecucion(
        id_ejecucion="ec-pre",
        semestre="2026-II",
        corte="Mitad",
        ejecutado_por="test@unal.edu.co",
        estado="fallida",
        fase="procesando",
        modo="completa",
        ejecutor="github",
    )
    sesion.add(ej)
    sesion.add(
        OfertaCruda(
            id_ejecucion="ec-pre",
            fuente="LinkedIn",
            id_fuente="c1",
            termino="excel",
            carrera_termino="Economía",
            ubicacion="Bogotá",
            datos={},
        )
    )
    sesion.commit()
    H = _headers_admin(cliente)
    r = cliente.post("/api/corridas/ec-pre/terminar", headers=H)
    assert r.status_code == 200
    assert r.json()["estado"] == "en_cola"
    assert llamadas[0]["inputs"]["fase"] == "solo_consolidar"
    assert llamadas[0]["inputs"]["run_id"] == "ec-pre"


def test_terminar_rechaza_si_completada(cliente, sesion):
    _ejec_incompleta(sesion, "ec-ok2", pendientes=0, estado="completada")
    H = _headers_admin(cliente)
    r = cliente.post("/api/corridas/ec-ok2/terminar", headers=H)
    assert r.status_code == 400


def test_reanudar_rechaza_si_otra_corrida_activa(cliente, sesion, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_prueba")
    monkeypatch.setenv("GITHUB_REPO", "its-camilo/observatorio-empleo-fce")

    class Resp:
        status_code = 204
        text = ""

    monkeypatch.setattr(corr.requests, "post", lambda *a, **k: Resp())
    _ejec_incompleta(sesion, "ec-a", pendientes=2)
    sesion.add(
        Ejecucion(
            id_ejecucion="ec-activa",
            semestre="2026-II",
            corte="Inicio",
            ejecutado_por="x",
            estado="en_curso",
            fase="extrayendo",
            modo="completa",
            ejecutor="github",
        )
    )
    sesion.commit()
    H = _headers_admin(cliente)
    r = cliente.post("/api/corridas/ec-a/reanudar", headers=H)
    assert r.status_code == 400 and "en marcha" in r.json()["detail"].lower()