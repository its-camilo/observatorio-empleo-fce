from observatorio.mantenimiento import TERMINOS_BUSQUEDA_RETIRADOS, purgar_ofertas_operativas
from observatorio.parametros import valores_por_defecto
from observatorio.pipeline.clasificacion import titulo_excluido_operativo
from observatorio.run import main


def test_terminos_retirados_incluyen_auxiliar_administrativo():
    assert "auxiliar administrativo" in TERMINOS_BUSQUEDA_RETIRADOS


def test_patron_operativo_auxiliar_admin():
    patrones = valores_por_defecto()["exclusion_operativa_titulo"]
    assert titulo_excluido_operativo("Auxiliar Administrativo - Bogotá", patrones)
    assert not titulo_excluido_operativo("Analista Administrativo", patrones)


def test_purga_operativa_sin_run_id(monkeypatch, capsys):
    """El workflow de mantenimiento invoca purga-operativa sin --run-id."""
    from observatorio.db.modelos import Base
    from observatorio.db.sesion import crear_tablas, fabrica_sesiones, motor

    url = "sqlite:///:memory:"
    monkeypatch.setenv("DATABASE_URL", url)
    motor(url)
    crear_tablas(url)
    assert main(["purga-operativa"]) == 0
    out = capsys.readouterr().out
    assert "vista_previa" in out


def test_vista_previa_incluye_ejemplos_cargos():
    from datetime import date

    from observatorio.db.modelos import Base, Oferta
    from observatorio.db.sesion import fabrica_sesiones, motor

    url = "sqlite:///:memory:"
    Base.metadata.create_all(motor(url))
    with fabrica_sesiones(url)() as s:
        s.add(
            Oferta(
                id_oferta="op-1",
                fuente="LinkedIn",
                url="https://example.com/1",
                fecha_publicacion=date.today(),
                fecha_extraccion=date.today(),
                semestre="2026-II",
                corte="Inicio",
                cargo="Auxiliar administrativo y recepción",
                ciudad="Bogotá",
                carrera_principal="Administración de Empresas",
            )
        )
        s.commit()
        res = purgar_ofertas_operativas(s, aplicar=False)
        assert res["candidatas"] >= 1
        assert "Auxiliar administrativo" in " ".join(res.get("ejemplos_cargos", []))
