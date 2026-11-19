"""Tablas de agregados precalculados y conteos por corte."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0009_agregados"
down_revision = "0008_perf_listado"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agregados_analisis",
        sa.Column("clave", sa.String(256), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "conteos_ofertas_corte",
        sa.Column("semestre", sa.String(16), primary_key=True),
        sa.Column("corte", sa.String(16), primary_key=True),
        sa.Column("carrera", sa.String(120), primary_key=True),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_conteos_ofertas_corte_lookup
        ON conteos_ofertas_corte (semestre, corte, carrera)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_conteos_ofertas_corte_lookup")
    op.drop_table("conteos_ofertas_corte")
    op.drop_table("agregados_analisis")