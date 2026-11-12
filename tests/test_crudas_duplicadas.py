"""Inserción concurrente de crudas: uq_cruda no debe tumbar la sesión."""
from sqlalchemy import func, select

from observatorio.db.crudas import insertar_cruda
from observatorio.db.modelos import Base, OfertaCruda
from observatorio.db.sesion import fabrica_sesiones, motor


def test_insertar_cruda_duplicado_sin_invalidar_sesion():
    url = "sqlite:///:memory:"
    Base.metadata.create_all(motor(url))
    datos = {"fuente": "LinkedIn", "cargo": "Analista"}
    with fabrica_sesiones(url)() as s:
        assert insertar_cruda(
            s,
            id_ejecucion="run-1",
            fuente="LinkedIn",
            id_fuente="123",
            termino="contador",
            carrera_termino="Contaduría Pública",
            ubicacion="Bogotá",
            datos=datos,
        )
        s.commit()
        assert (
            insertar_cruda(
                s,
                id_ejecucion="run-1",
                fuente="LinkedIn",
                id_fuente="123",
                termino="contador",
                carrera_termino="Contaduría Pública",
                ubicacion="Bogotá",
                datos=datos,
            )
            is False
        )
        s.commit()
        total = s.scalar(select(func.count()).select_from(OfertaCruda))
        assert total == 1
