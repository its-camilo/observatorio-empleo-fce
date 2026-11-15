"""Ofertas: marcar exclusion por ajuste de proporción (no destructivo)."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_oferta_exclusion"
down_revision = "0003_solo_capitales"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ofertas",
        sa.Column("excluida_resultado_corrida", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("ofertas", sa.Column("motivo_exclusion_corrida", sa.String(length=64), nullable=True))
    op.create_index("ix_ofertas_excluida_resultado", "ofertas", ["excluida_resultado_corrida"])


def downgrade() -> None:
    op.drop_index("ix_ofertas_excluida_resultado", table_name="ofertas")
    op.drop_column("ofertas", "motivo_exclusion_corrida")
    op.drop_column("ofertas", "excluida_resultado_corrida")