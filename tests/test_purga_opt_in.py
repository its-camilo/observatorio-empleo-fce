"""Purga: borrado exige --purgar y --aplicar en la CLI."""
from __future__ import annotations

from datetime import date

from observatorio.db.modelos import Oferta
from observatorio.db.sesion import crear_tablas, fabrica_sesiones, motor
from observatorio.run import main


def test_cli_purga_aplicar_sin_purgar_no_borra(monkeypatch, capsys):
    url = "sqlite:///:memory:"
    monkeypatch.setenv("DATABASE_URL", url)
    motor(url)
    crear_tablas(url)
    with fabrica_sesiones(url)() as s:
        s.add(
            Oferta(
                id_oferta="cli-1",
                fuente="CT",
                fecha_extraccion=date.today(),
                semestre="2026-II",
                corte="Inicio",
                cargo="Recepcionista",
                ciudad="Bogotá",
                descripcion="Atención",
            )
        )
        s.commit()
    assert main(["purga-reglas", "--aplicar"]) == 0
    out = capsys.readouterr().out
    assert "vista_previa" in out
    assert "Borrado no ejecutado" in out or "aviso" in out
    with fabrica_sesiones(url)() as s:
        assert s.get(Oferta, "cli-1") is not None