"""Carga inicial idempotente: catálogo, términos, configuración y administradores."""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from observatorio.config import ajustes
from observatorio.db.modelos import Catalogo, Config, Sinonimo, TerminoBusqueda, Usuario
from observatorio.parametros import POR_DEFECTO

DATOS = Path(__file__).resolve().parent.parent / "datos"


def _sinonimo(item) -> dict:
    if isinstance(item, str):
        return {"texto": item}
    return {
        "texto": item["t"],
        "sensible_mayusculas": bool(item.get("cs")),
        "requiere_contexto": bool(item.get("ctx")),
        "patron_exclusion": item.get("excluir"),
    }


def sembrar_catalogo(s: Session, forzar: bool = False) -> int:
    """Carga el catálogo inicial si la tabla está vacía (o `forzar`)."""
    if s.query(Catalogo).count() and not forzar:
        return 0
    datos = json.loads((DATOS / "catalogo.json").read_text(encoding="utf-8"))
    n = 0
    for g in datos["grupos"]:
        for sw in g["softwares"]:
            fila = s.query(Catalogo).filter_by(software=sw["software"]).one_or_none()
            if fila is None:
                fila = Catalogo(software=sw["software"], grupo=g["grupo"], activo=sw.get("activo", True),
                                contexto=sw.get("contexto"))
                s.add(fila)
                s.flush()
                n += 1
            existentes = {(x.texto, x.sensible_mayusculas) for x in fila.sinonimos}
            for item in sw["sinonimos"]:
                d = _sinonimo(item)
                if (d["texto"], d.get("sensible_mayusculas", False)) in existentes:
                    continue
                # Un mismo texto puede repetirse con reglas distintas solo si cambia mayúsculas
                if any(x.texto == d["texto"] for x in fila.sinonimos):
                    continue
                fila.sinonimos.append(Sinonimo(**d))
                existentes.add((d["texto"], d.get("sensible_mayusculas", False)))
    s.flush()
    return n


def sembrar_terminos(s: Session) -> int:
    if s.query(TerminoBusqueda).count():
        return 0
    datos = json.loads((DATOS / "terminos.json").read_text(encoding="utf-8"))
    n = 0
    for tipo in ("principal", "ampliado"):
        for carrera, terminos in datos[tipo].items():
            for t in dict.fromkeys(terminos):
                s.add(TerminoBusqueda(termino=t, carrera=carrera, tipo=tipo, activo=True))
                n += 1
    s.flush()
    return n


def sembrar_config(s: Session) -> int:
    n = 0
    for clave, d in POR_DEFECTO.items():
        if s.get(Config, clave) is None:
            s.add(Config(clave=clave, valor=d["valor"], descripcion=d["descripcion"], actualizado_por="semilla"))
            n += 1
    s.flush()
    return n


def sembrar_admins(s: Session) -> int:
    n = 0
    for email in ajustes().admins_iniciales:
        u = s.query(Usuario).filter_by(email=email).one_or_none()
        if u is None:
            s.add(Usuario(email=email, rol="admin", estado="aprobado", aprobado_por="semilla"))
            n += 1
    s.flush()
    return n


def sembrar_todo(s: Session) -> dict[str, int]:
    return {
        "catalogo": sembrar_catalogo(s),
        "terminos": sembrar_terminos(s),
        "config": sembrar_config(s),
        "admins": sembrar_admins(s),
    }
