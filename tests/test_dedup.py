from datetime import date

from observatorio.pipeline.dedup import clave_dedup, deduplicar


def oferta(idf, empresa, cargo, ciudad, fecha, desc, termino="t"):
    return {"id_oferta": idf, "clave_dedup": clave_dedup(empresa, cargo, ciudad, desc), "fecha_publicacion": fecha,
            "descripcion": desc, "termino_busqueda": termino}


def test_misma_oferta_en_dos_fuentes_gana_la_descripcion_mas_larga():
    a = oferta("LI-1", "Contadores Asociados S.A.S.", "Auxiliar Contable", "Bogotá", date(2026, 11, 1), "corta", "auxiliar contable")
    b = oferta("IN-x", "CONTADORES ASOCIADOS SAS", "AUXILIAR CONTABLE (a)", "Bogotá", date(2026, 11, 3), "descripción mucho más larga", "contador")
    unicas, dup = deduplicar([a, b], dias=7)
    assert dup == 1 and len(unicas) == 1
    assert unicas[0]["id_oferta"] == "IN-x"
    assert set(unicas[0]["termino_busqueda"].split("; ")) == {"auxiliar contable", "contador"}


def test_fechas_lejanas_no_son_duplicado():
    a = oferta("LI-1", "Empresa", "Analista", "Bogotá", date(2026, 10, 1), "x")
    b = oferta("LI-2", "Empresa", "Analista", "Bogotá", date(2026, 10, 20), "y")
    unicas, dup = deduplicar([a, b], dias=7)
    assert dup == 0 and len(unicas) == 2


def test_distinta_ciudad_no_es_duplicado():
    a = oferta("LI-1", "Empresa", "Analista", "Bogotá", date(2026, 10, 1), "x")
    b = oferta("LI-2", "Empresa", "Analista", "Medellín", date(2026, 10, 2), "y")
    assert deduplicar([a, b])[1] == 0


def test_mismo_id_es_duplicado():
    a = oferta("LI-1", "Empresa", "Analista", "Bogotá", None, "x")
    b = oferta("LI-1", "Empresa", "Analista", "Bogotá", None, "xx")
    unicas, dup = deduplicar([a, b])
    assert dup == 1 and unicas[0]["descripcion"] == "xx"


def test_empresa_generica_no_fusiona_ofertas_distintas():
    a = oferta("CT-1", "Importante empresa del sector", "Auxiliar contable", "Bogotá", date(2026, 11, 1), "Empresa de transporte busca")
    b = oferta("CT-2", "Importante empresa del sector", "Auxiliar contable", "Bogotá", date(2026, 11, 1), "Clínica odontológica requiere")
    assert deduplicar([a, b])[1] == 0
