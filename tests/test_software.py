def nombres(detector, texto, empresa=""):
    return {d.software for d in detector.detectar("", texto, empresa)}


def test_sinonimos_y_variantes(detector):
    n = nombres(detector, "Manejo de PowerBI, MS Excel y SAP S/4HANA. Deseable Siigo Nube.")
    assert {"Power BI", "Excel", "SAP", "Siigo Nube"} <= n


def test_palabra_completa(detector):
    n = nombres(detector, "Experiencia en JavaScript y MySQL")
    assert "JavaScript" in n and "MySQL" in n
    assert "Java" not in n and "SQL" not in n


def test_r_con_contexto_si(detector):
    assert "R" in nombres(detector, "Conocimientos en Python, R y SQL para análisis estadístico")
    assert "R" in nombres(detector, "Programación en R (deseable RStudio)")


def test_r_sin_contexto_no(detector):
    assert "R" not in nombres(detector, "Calle 26 # 69 R, Bogotá. Área de R&D y de RRHH.")
    assert "R" not in nombres(detector, "Requisitos: proactividad. R: responsable del proceso.")


def test_sas_empresa_no_es_software(detector):
    assert "SAS" not in nombres(detector, "Contadores Asociados SAS busca auxiliar contable con manejo de herramientas ofimáticas")
    assert "SAS" not in nombres(detector, "Trabaja en Inversiones S.A.S. con Excel")
    assert "SAS" not in nombres(detector, "Empresa ABC SAS ESP, análisis de datos con Excel")


def test_sas_software_si(detector):
    assert "SAS" in nombres(detector, "Manejo de SPSS, Stata o SAS para modelos estadísticos")
    assert "SAS" in nombres(detector, "Experiencia con SAS Enterprise Guide")


def test_word_y_access_ambiguos(detector):
    assert "Word" in nombres(detector, "Manejo de Office: Word, Excel y PowerPoint")
    assert "Access" not in nombres(detector, "You will have access to training")
    assert "Access" in nombres(detector, "Bases de datos en Microsoft Access")


def test_excel_verbo_en_ingles(detector):
    assert "Excel" not in nombres(detector, "Candidates who excel in communication")
    assert "Excel" in nombres(detector, "Advanced Excel skills required")


def test_nombre_de_empresa_no_cuenta(detector):
    assert "Siigo Nube" not in nombres(detector, "Siigo S.A.S. busca ejecutivo comercial", empresa="Siigo")


def test_texto_encontrado_original(detector):
    d = {x.software: x.texto_encontrado for x in detector.detectar("", "Dominio de POWER BI y tablas dinámicas")}
    assert d["Power BI"] == "POWER BI"
    assert d["Excel avanzado"] == "tablas dinámicas"


def test_catalogo_editable_sin_codigo(sesion):
    """GC agrega un software y se detecta sin tocar el código (criterio de aceptación)."""
    from observatorio.db.modelos import Catalogo, Sinonimo
    from observatorio.pipeline.software import DetectorSoftware

    c = Catalogo(software="EViews", grupo="Visualizadores, gestores de datos y softwares estadísticos")
    c.sinonimos.append(Sinonimo(texto="eviews"))
    sesion.add(c)
    sesion.commit()
    assert "EViews" in {d.software for d in DetectorSoftware.desde_bd(sesion).detectar("", "Modelos en EViews y Stata")}


def test_idiomas_y_blandas():
    from observatorio.pipeline.habilidades import detectar_blandas, detectar_idiomas

    assert detectar_idiomas("Excel avanzado. Inglés B2 indispensable") == "Inglés B2"
    assert "Portugués básico" in detectar_idiomas("Nivel de inglés intermedio y portugués básico")
    assert "Trabajo en equipo" in detectar_blandas("Buscamos trabajo en equipo y liderazgo")
