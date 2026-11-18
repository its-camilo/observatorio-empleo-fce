"""Índices para listado de ofertas y filtros por corte."""
from __future__ import annotations

from alembic import op

revision = "0008_perf_listado"
down_revision = "0007_niveles_experiencia"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ofertas_incluidas_corte_fecha
        ON ofertas (semestre, corte, fecha_publicacion DESC NULLS LAST)
        WHERE excluida_resultado_corrida IS NOT TRUE OR excluida_resultado_corrida IS NULL
        """
    )
    with op.batch_alter_table("ofertas") as batch_op:
        batch_op.create_index("ix_ofertas_semestre_corte_fuente", ["semestre", "corte", "fuente"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("ofertas") as batch_op:
        batch_op.drop_index("ix_ofertas_semestre_corte_fuente")
    op.execute("DROP INDEX IF EXISTS ix_ofertas_incluidas_corte_fecha")