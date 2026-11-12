from observatorio.parametros import valores_por_defecto
from observatorio.pipeline.clasificacion import ClasificadorReglas


def clasificador():
    cfg = valores_por_defecto()
    return ClasificadorReglas(
        cfg["reglas_carrera"],
        cfg["exclusion_titulo"],
        cfg["carreras"],
        cfg.get("exclusion_operativa_titulo"),
    )


def test_titulo_contable():
    c = clasificador().clasificar("Auxiliar Contable", "Manejo de NIIF", "Contaduría Pública")
    assert c.estado == "relevante" and c.carreras[0] == "Contaduría Pública"


def test_titulo_economia():
    c = clasificador().clasificar("Economista Junior", "Modelos econométricos")
    assert c.estado == "relevante" and c.carreras[0] == "Economía"


def test_multietiqueta_maximo_cinco():
    c = clasificador().clasificar("Analista financiero y contable", "Profesional en Contaduría Pública, Economía o Administración de Empresas")
    assert c.estado == "relevante"
    assert {"Contaduría Pública", "Economía"} <= set(c.carreras)
    assert len(c.carreras) <= 5


def test_excluido_no_relevante():
    assert clasificador().clasificar("Enfermera jefe", "Atención de pacientes").estado == "no_relevante"
    assert clasificador().clasificar("Desarrollador Backend Java", "Spring Boot").estado == "no_relevante"


def test_excluido_pero_con_carrera_especifica_es_relevante():
    assert clasificador().clasificar("Desarrollador de reportes contables", "").estado == "relevante"


def test_dudosa_y_respaldo():
    cl = clasificador()
    c = cl.clasificar("Consultor Senior", "Profesional en Economía o Administración de Empresas con experiencia en finanzas")
    assert c.estado == "dudosa"
    r = ClasificadorReglas.respaldo(c)
    assert r.estado == "relevante" and r.clasificado_por == "reglas_respaldo"


def test_sin_senales():
    assert clasificador().clasificar("Mesero", "Atención en restaurante").estado == "no_relevante"


def test_auxiliar_administrativo_no_relevante():
    c = clasificador().clasificar("Auxiliar Administrativo", "Apoyo en oficina y archivo", "Administración de Empresas")
    assert c.estado == "no_relevante"


def test_analista_administrativo_sigue_relevante():
    c = clasificador().clasificar("Analista Administrativo", "Profesional en administración de empresas")
    assert c.estado == "relevante"
