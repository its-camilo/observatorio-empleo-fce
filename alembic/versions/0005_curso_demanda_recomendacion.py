"""Cursos: demanda de habilidad y puntaje de recomendación."""

from alembic import op
import sqlalchemy as sa

revision = "0005_curso_demanda"
down_revision = "0004_oferta_exclusion_proporcion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cursos", sa.Column("habilidad_demanda", sa.String(160), nullable=True))
    op.add_column("cursos", sa.Column("demanda_ofertas", sa.Integer(), nullable=True))
    op.add_column("cursos", sa.Column("demanda_pct", sa.Float(), nullable=True))
    op.add_column("cursos", sa.Column("demanda_carreras", sa.Text(), nullable=True))
    op.add_column("cursos", sa.Column("puntaje_recomendacion", sa.Float(), nullable=True))
    op.create_index("ix_cursos_puntaje", "cursos", ["puntaje_recomendacion"])


def downgrade() -> None:
    op.drop_index("ix_cursos_puntaje", table_name="cursos")
    op.drop_column("cursos", "puntaje_recomendacion")
    op.drop_column("cursos", "demanda_carreras")
    op.drop_column("cursos", "demanda_pct")
    op.drop_column("cursos", "demanda_ofertas")
    op.drop_column("cursos", "habilidad_demanda")