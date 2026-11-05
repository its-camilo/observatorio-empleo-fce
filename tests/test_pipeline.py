"""Corrida de punta a punta con ofertas sintéticas (sin red)."""
from observatorio import analisis
from observatorio import orquestador as orq
from observatorio.db.modelos import Oferta, OfertaCruda


def crudas(sesion, id_ej, lista):
    for d in lista:
        sesion.add(OfertaCruda(id_ejecucion=id_ej, fuente=d["fuente"], id_fuente=d["id_fuente"], termino=d.get("termino", "x"),
                               carrera_termino=d.get("carrera"), datos=d))
    sesion.commit()


BASE = [
    dict(fuente="LinkedIn", id_fuente="1", url="u1", cargo="Auxiliar Contable", empresa="Contadores SAS", ubicacion="Bogotá, Colombia",
         fecha_publicacion="2026-11-01", descripcion="Manejo de Excel y Siigo", carrera="Contaduría Pública"),
    dict(fuente="Indeed", id_fuente="a", url="u2", cargo="AUXILIAR CONTABLE", empresa="Contadores S.A.S.", ubicacion="Bogotá, CUN, Colombia",
         fecha_publicacion="2026-11-03", descripcion="Manejo de Excel y Siigo. Descripción más larga.", carrera="Contaduría Pública"),
    dict(fuente="LinkedIn", id_fuente="2", url="u3", cargo="Mesero", empresa="Restaurante", ubicacion="Bogotá", fecha_publicacion="2026-11-03",
         descripcion="Atención de mesas"),
    dict(fuente="Computrabajo", id_fuente="c1", url="u4", cargo="Analista de datos", empresa="Banco Y", ubicacion="Medellín, Antioquia",
         fecha_publicacion="Hace 2 días", descripcion="Profesional en Economía. Python, R y SQL. Power BI. Inglés B2.", carrera="Economía"),
    dict(fuente="LinkedIn", id_fuente="3", url="u5", cargo="Analista contable", empresa="Lima SAC", ubicacion="Lima, Perú",
         fecha_publicacion="2026-11-03", descripcion="Excel"),
]


def test_corrida_sintetica(sesion):
    e = orq.preparar(sesion, "2026-II", "inicio", "t1", fuentes=["linkedin"], limite_terminos=1, limite_ubicaciones=1, modo="prueba")
    sesion.commit()
    crudas(sesion, "t1", BASE)
    e = orq.consolidar(sesion, "t1", usar_llm=False)
    ids = {o.id_oferta for o in sesion.query(Oferta)}
    assert ids == {"IN-a", "CT-c1"}  # duplicado fusionado, mesero descartado, Perú fuera
    assert e.duplicados_eliminados >= 1 and e.no_relevantes == 1
    o = sesion.get(Oferta, "CT-c1")
    assert o.ciudad == "Medellín" and o.carrera_principal == "Economía" and o.idiomas == "Inglés B2"
    assert {x.software for x in o.softwares} == {"Python", "R", "SQL", "Power BI"}
    assert all(x.semestre == "2026-II" and x.corte == "Inicio" for x in o.softwares)
    rk = analisis.ranking(sesion, "2026-II", "Inicio", "Economía")
    assert rk[0]["porcentaje"] == 100.0


def test_dedup_entre_ejecuciones_y_reanudacion(sesion):
    orq.preparar(sesion, "2026-II", "inicio", "t1", fuentes=["linkedin"], limite_terminos=1, limite_ubicaciones=1, modo="prueba")
    sesion.commit()
    crudas(sesion, "t1", BASE[:1])
    orq.consolidar(sesion, "t1", usar_llm=False)
    # reanudar la misma ejecución no duplica
    orq.consolidar(sesion, "t1", usar_llm=False)
    assert sesion.query(Oferta).count() == 1
    # otra ejecución encuentra la misma oferta en otra fuente con descripción más larga: se actualiza, no se duplica
    orq.preparar(sesion, "2026-II", "mitad", "t2", fuentes=["linkedin"], limite_terminos=1, limite_ubicaciones=1, modo="prueba")
    sesion.commit()
    crudas(sesion, "t2", [BASE[1]])
    e2 = orq.consolidar(sesion, "t2", usar_llm=False)
    assert sesion.query(Oferta).count() == 1
    assert e2.duplicados_eliminados == 1
    assert "más larga" in sesion.query(Oferta).one().descripcion


def test_comparacion_entre_cortes(sesion):
    for idx, corte, lista in (("a", "inicio", BASE[:1]), ("b", "mitad", [BASE[3]])):
        orq.preparar(sesion, "2026-II", corte, idx, fuentes=["linkedin"], limite_terminos=1, limite_ubicaciones=1, modo="prueba")
        sesion.commit()
        crudas(sesion, idx, lista)
        orq.consolidar(sesion, idx, usar_llm=False)
    c = analisis.comparar(sesion, "2026-II", "Inicio", "2026-II", "Mitad")
    estados = {x["software"]: x["estado"] for x in c["softwares"]}
    assert estados["Siigo Nube"] == "desapareció" and estados["Python"] == "nuevo"


def test_exportar_excel(sesion):
    from openpyxl import load_workbook
    import io
    from observatorio.exportar import a_excel

    orq.preparar(sesion, "2026-II", "inicio", "t1", fuentes=["linkedin"], limite_terminos=1, limite_ubicaciones=1, modo="prueba")
    sesion.commit()
    crudas(sesion, "t1", BASE)
    orq.consolidar(sesion, "t1", usar_llm=False)
    wb = load_workbook(io.BytesIO(a_excel(sesion, "2026-II", "Inicio")))
    assert {"Ofertas", "Oferta_Software", "Catalogo", "Ejecuciones", "Ranking", "Cursos"} <= set(wb.sheetnames)
    assert [c.value for c in wb["Ofertas"][1]][:4] == ["id_oferta", "fuente", "url", "fecha_publicacion"]


def test_llm_simulado_para_dudosas(sesion, monkeypatch):
    from observatorio.pipeline import llm as modulo

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-prueba")

    def falso(self, mensajes):
        import json
        ofertas = json.loads(mensajes[1]["content"])["ofertas"]
        return {"resultados": [{"id": o["id"], "relevante": True, "carreras": ["Economía"], "herramientas_no_catalogadas": ["EViews"]}
                               for o in ofertas]}, "modelo-prueba:free"

    monkeypatch.setattr(modulo.ClienteLLM, "_llamar", falso)
    orq.preparar(sesion, "2026-II", "inicio", "t1", fuentes=["linkedin"], limite_terminos=1, limite_ubicaciones=1, modo="prueba")
    sesion.commit()
    crudas(sesion, "t1", [dict(fuente="LinkedIn", id_fuente="9", url="u", cargo="Consultor Senior", empresa="Firma",
                               ubicacion="Bogotá", fecha_publicacion="2026-11-01",
                               descripcion="Profesional en economía con experiencia en finanzas y EViews")])
    orq.consolidar(sesion, "t1", usar_llm=True)
    o = sesion.get(Oferta, "LI-9")
    assert o is not None and o.clasificado_por == "llm" and o.carrera == "Economía"
