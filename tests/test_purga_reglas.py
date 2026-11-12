from datetime import date

from observatorio.db.modelos import Oferta
from observatorio.mantenimiento import MOTIVO_OPERATIVO, MOTIVO_SIN_FORMATIVO, purgar_por_reglas


def test_purga_vista_previa_por_motivo(sesion):
    hoy = date.today()
    sesion.add_all(
        [
            Oferta(
                id_oferta="p1",
                fuente="CT",
                fecha_extraccion=hoy,
                semestre="2026-II",
                corte="Inicio",
                cargo="Auxiliar administrativo",
                descripcion="Manejo de Excel",
            ),
            Oferta(
                id_oferta="p2",
                fuente="CT",
                fecha_extraccion=hoy,
                semestre="2026-II",
                corte="Inicio",
                cargo="Analista financiero",
                descripcion="Solo trabajo en equipo y comunicación",
            ),
            Oferta(
                id_oferta="p3",
                fuente="CT",
                fecha_extraccion=hoy,
                semestre="2026-II",
                corte="Inicio",
                cargo="Analista contable",
                descripcion="SAP y NIIF",
            ),
        ]
    )
    sesion.commit()
    res = purgar_por_reglas(sesion, aplicar=False)
    assert res["candidatas"] == 2
    assert res["por_motivo"][MOTIVO_OPERATIVO] == 1
    assert res["por_motivo"][MOTIVO_SIN_FORMATIVO] == 1
    assert "ejemplos_por_motivo" in res


def test_purga_aplicar_borra(sesion):
    hoy = date.today()
    sesion.add(
        Oferta(
            id_oferta="del-1",
            fuente="CT",
            fecha_extraccion=hoy,
            semestre="2026-II",
            corte="Inicio",
            cargo="Recepcionista",
            descripcion="Atención al público",
        )
    )
    sesion.commit()
    res = purgar_por_reglas(sesion, aplicar=True)
    assert res["eliminadas"] == 1
    assert sesion.get(Oferta, "del-1") is None
