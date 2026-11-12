"""Config: solo capitales departamentales y catálogo de ubicaciones."""
from __future__ import annotations

from alembic import op
from sqlalchemy.orm import Session

from observatorio.capitales import ubicaciones_capitales_defecto
from observatorio.db.modelos import Config

revision = "0003_solo_capitales"
down_revision = "0002_indices_corte"
branch_labels = None
depends_on = None

_DESCR_SOLO = (
    "Si está activo, solo se guardan ofertas en capitales departamentales (o Remoto). "
    "Las corridas consultan únicamente ciudades del catálogo de capitales."
)
_DESCR_UBIC = (
    "Capitales departamentales (33 jurisdicciones) a consultar en cada fuente. "
    "Vacío en computrabajo = no se consulta en esa fuente."
)


def _upsert_config(s: Session, clave: str, valor, descripcion: str) -> None:
    fila = s.get(Config, clave)
    if fila is None:
        s.add(Config(clave=clave, valor=valor, descripcion=descripcion, actualizado_por="alembic"))
    else:
        fila.valor = valor
        fila.descripcion = descripcion
        fila.actualizado_por = "alembic"


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)
    try:
        _upsert_config(session, "solo_capitales_departamento", True, _DESCR_SOLO)
        _upsert_config(session, "ubicaciones", ubicaciones_capitales_defecto(), _DESCR_UBIC)
        session.commit()
    finally:
        session.close()


def downgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)
    try:
        fila = session.get(Config, "solo_capitales_departamento")
        if fila is not None:
            session.delete(fila)
        session.commit()
    finally:
        session.close()
