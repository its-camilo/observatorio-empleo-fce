"""Índices compuestos para consultas por semestre+corte (dashboard y rankings)."""
from __future__ import annotations

from alembic import op

revision = "0002_indices_corte"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ofertas") as batch_op:
        batch_op.create_index("ix_ofertas_semestre_corte", ["semestre", "corte"], unique=False)
    with op.batch_alter_table("oferta_software") as batch_op:
        batch_op.create_index("ix_oferta_software_semestre_corte", ["semestre", "corte"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("oferta_software") as batch_op:
        batch_op.drop_index("ix_oferta_software_semestre_corte")
    with op.batch_alter_table("ofertas") as batch_op:
        batch_op.drop_index("ix_ofertas_semestre_corte")
