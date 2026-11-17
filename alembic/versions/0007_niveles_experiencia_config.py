"""RF-01: configuración de niveles de experiencia en tabla config."""
from __future__ import annotations

import copy

from alembic import op
from sqlalchemy.orm import Session

from observatorio.db.modelos import Config
from observatorio.pipeline.nivel_experiencia import config_niveles_defecto

revision = "0007_niveles_experiencia"
down_revision = "0006_rf18_habilidades"
branch_labels = None
depends_on = None

_DESCR = (
    "Niveles de experiencia permitidos al buscar y procesar ofertas. "
    "modo=todos sin filtro; modo=algunos solo guarda los niveles listados."
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
        _upsert_config(session, "niveles_experiencia", copy.deepcopy(config_niveles_defecto()), _DESCR)
        session.commit()
    finally:
        session.close()


def downgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)
    try:
        fila = session.get(Config, "niveles_experiencia")
        if fila is not None:
            session.delete(fila)
        session.commit()
    finally:
        session.close()