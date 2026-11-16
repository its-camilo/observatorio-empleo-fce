"""Valida la cadena de migraciones Alembic sin conectar a la base de datos."""
from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def _script_dir() -> ScriptDirectory:
    raiz = Path(__file__).resolve().parents[1]
    cfg = Config(str(raiz / "alembic.ini"))
    cfg.set_main_option("script_location", str(raiz / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_alembic_un_solo_head():
    script = _script_dir()
    heads = script.get_heads()
    assert len(heads) == 1, f"Se esperaba un solo head de migración, hay: {heads}"


def test_alembic_down_revision_existen():
    script = _script_dir()
    conocidos = {rev.revision for rev in script.walk_revisions()}
    for rev in script.walk_revisions():
        down = rev.down_revision
        if down is None:
            continue
        refs = down if isinstance(down, tuple) else (down,)
        for d in refs:
            assert d in conocidos, f"La revisión {rev.revision} referencia down_revision inexistente: {d!r}"