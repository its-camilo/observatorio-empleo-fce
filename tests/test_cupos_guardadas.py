"""Cupos de ofertas guardadas por fuente×carrera y clasificación con término."""
from observatorio import orquestador as orq
from observatorio.db.modelos import Oferta
from observatorio.parametros import valores_por_defecto
from observatorio.plan_extraccion import presupuesto_por_carrera, presupuesto_por_fuente, presupuesto_fuente_carrera
from observatorio.cupos_guardadas import ControlCuposGuardadas, construir_presupuestos_preparar


def _cruda(id_ej, sufijo, fuente, carrera, cargo, desc="experiencia SAP NIIF análisis"):
    return dict(
        fuente=fuente,
        id_fuente=sufijo,
        url=f"https://x/{sufijo}",
        cargo=cargo,
        empresa="Firma",
        ubicacion="Bogotá, Colombia",
        fecha_publicacion="2026-11-01",
        descripcion=desc,
        carrera=carrera,
    )


def test_preparar_congela_presupuesto_guardadas_y_extraccion(sesion):
    cfg = valores_por_defecto()
    cfg["objetivo_ofertas_corrida"] = 300
    cfg["meta_ofertas"] = 300
    ejec = orq.preparar(sesion, "2026-II", "mitad", "cupos-1", modo="completa")
    sesion.commit()
    p = ejec.parametros
    assert p["presupuesto_guardadas_fuente_carrera"]["linkedin"]
    assert p["objetivo_ofertas_corrida"] > 300
    assert p["presupuesto_fuentes"]["linkedin"] > p["presupuesto_guardadas_fuentes"]["linkedin"]


def test_consolidar_respeta_cupo_administracion(sesion):
    """Todas las crudas parecen Administración en contenido pero el cupo de Admin es mínimo."""
    meta = 30
    cfg_def = valores_por_defecto()
    fuentes = ["linkedin", "indeed", "computrabajo"]
    presu_f = presupuesto_por_fuente(meta, fuentes, cfg_def)
    presu_c = presupuesto_por_carrera(meta, cfg_def)
    presu_fc = presupuesto_fuente_carrera(presu_f, cfg_def)
    presu_fc["linkedin"]["Administración de Empresas"] = 3
    meta_admin = presu_c.get("Administración de Empresas", 1)
    crudas_admin = [
        _cruda(
            "cupos-admin",
            f"a{i}",
            "LinkedIn",
            "Administración de Empresas",
            "Analista de gestión",
            "administración de empresas procesos gerenciales SAP excel avanzado",
        )
        for i in range(25)
    ]
    crudas_econ = [
        _cruda("cupos-admin", f"e{i}", "LinkedIn", "Economía", "Analista financiero", "economía python SQL power bi")
        for i in range(5)
    ]
    from observatorio.db.modelos import Ejecucion

    orq.preparar(sesion, "2026-II", "mitad", "cupos-admin", fuentes=["linkedin"], modo="prueba")
    ejec = sesion.get(Ejecucion, "cupos-admin")
    ejec.parametros = {
        **(ejec.parametros or {}),
        "meta_ofertas_guardadas": meta,
        "presupuesto_guardadas_fuentes": presu_f,
        "presupuesto_guardadas_carreras": presu_c,
        "presupuesto_guardadas_fuente_carrera": presu_fc,
        "objetivo_ofertas_corrida": sum(presu_f.values()),
        "presupuesto_fuentes": presu_f,
        "presupuesto_carreras": presu_c,
        "presupuesto_fuente_carrera": presu_fc,
    }
    ejec.meta_ofertas = meta
    sesion.commit()
    from tests.test_pipeline import crudas

    crudas(sesion, "cupos-admin", crudas_admin + crudas_econ)
    ej = orq.consolidar(sesion, "cupos-admin", permitir_mini=False)
    admin = sesion.query(Oferta).filter(
        Oferta.id_ejecucion == "cupos-admin",
        Oferta.carrera_principal == "Administración de Empresas",
    ).count()
    assert admin <= 3
    assert admin <= meta_admin


def test_control_cupo_no_supera_celda(sesion):
    orq.preparar(sesion, "2026-II", "inicio", "cupos-ctl", modo="prueba")
    meta_fc = {"linkedin": {"Economía": 2}}
    ctl = ControlCuposGuardadas(sesion, "cupos-ctl", {"linkedin": 10}, {"Economía": 2}, meta_fc)
    assert ctl.puede_guardar("LinkedIn", "Economía")[0]
    ctl.registrar("LinkedIn", "Economía")
    ctl.registrar("LinkedIn", "Economía")
    ok, motivo = ctl.puede_guardar("LinkedIn", "Economía")
    assert not ok and "excedente_cupo" in motivo


def test_termino_busqueda_clasifica_con_puntaje_2(sesion):
    from observatorio.parametros import leer_config
    from observatorio.pipeline.clasificacion import ClasificadorReglas

    cfg = leer_config(sesion)
    cl = ClasificadorReglas(cfg["reglas_carrera"], cfg["exclusion_titulo"], cfg["carreras"])
    c = cl.clasificar(
        "Consultor Senior",
        "Experiencia general en proyectos",
        "Economía",
    )
    assert c.estado == "relevante" and c.carreras[0] == "Economía"