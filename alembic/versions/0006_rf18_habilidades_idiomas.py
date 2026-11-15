"""RF-18: catálogos editables y relaciones habilidades blandas / idiomas por oferta."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_rf18_habilidades"
down_revision = "0005_curso_demanda"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalogo_habilidades",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("actualizado_en", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nombre"),
    )
    op.create_table(
        "sinonimos_habilidad",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("catalogo_habilidad_id", sa.Integer(), nullable=False),
        sa.Column("texto", sa.String(length=160), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("catalogo_habilidad_id", "texto", name="uq_sinonimo_habilidad"),
        sa.ForeignKeyConstraint(["catalogo_habilidad_id"], ["catalogo_habilidades.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_sin_hab_cat", "sinonimos_habilidad", ["catalogo_habilidad_id"])

    op.create_table(
        "catalogo_idiomas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nombre", sa.String(length=80), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("actualizado_en", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nombre"),
    )
    op.create_table(
        "sinonimos_idioma",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("catalogo_idioma_id", sa.Integer(), nullable=False),
        sa.Column("texto", sa.String(length=160), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("catalogo_idioma_id", "texto", name="uq_sinonimo_idioma"),
        sa.ForeignKeyConstraint(["catalogo_idioma_id"], ["catalogo_idiomas.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_sin_idi_cat", "sinonimos_idioma", ["catalogo_idioma_id"])

    op.create_table(
        "oferta_habilidades",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_oferta", sa.String(length=120), nullable=False),
        sa.Column("habilidad", sa.String(length=120), nullable=False),
        sa.Column("texto_encontrado", sa.String(length=255), nullable=True),
        sa.Column("carrera", sa.String(length=255), nullable=True),
        sa.Column("semestre", sa.String(length=16), nullable=False),
        sa.Column("corte", sa.String(length=16), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id_oferta", "habilidad", name="uq_oferta_habilidad"),
        sa.ForeignKeyConstraint(["id_oferta"], ["ofertas.id_oferta"], ondelete="CASCADE"),
    )
    op.create_index("ix_oferta_hab_corte", "oferta_habilidades", ["semestre", "corte", "habilidad"])

    op.create_table(
        "oferta_idiomas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_oferta", sa.String(length=120), nullable=False),
        sa.Column("idioma", sa.String(length=80), nullable=False),
        sa.Column("nivel", sa.String(length=40), nullable=True),
        sa.Column("carrera", sa.String(length=255), nullable=True),
        sa.Column("semestre", sa.String(length=16), nullable=False),
        sa.Column("corte", sa.String(length=16), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id_oferta", "idioma", name="uq_oferta_idioma"),
        sa.ForeignKeyConstraint(["id_oferta"], ["ofertas.id_oferta"], ondelete="CASCADE"),
    )
    op.create_index("ix_oferta_idi_corte", "oferta_idiomas", ["semestre", "corte", "idioma"])


def downgrade() -> None:
    op.drop_table("oferta_idiomas")
    op.drop_table("oferta_habilidades")
    op.drop_table("sinonimos_idioma")
    op.drop_table("catalogo_idiomas")
    op.drop_table("sinonimos_habilidad")
    op.drop_table("catalogo_habilidades")