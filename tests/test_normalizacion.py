from datetime import date

from observatorio.pipeline.limpieza import quitar_datos_personales
from observatorio.texto import (
    clave_cargo, clave_empresa, detectar_modalidad, detectar_nivel, detectar_tipo_oferta, normalizar_ciudad, normalizar_clave,
    normalizar_fecha, plegar,
)


def test_plegar_conserva_longitud():
    t = "Análisis en Bogotá con Ñandú"
    assert plegar(t) == "analisis en bogota con nandu"
    assert len(plegar(t)) == len(t)


def test_normalizar_clave():
    assert normalizar_clave("  Auxiliar   CONTABLE – Bogotá!! ") == "auxiliar contable bogota"


def test_ciudades():
    assert normalizar_ciudad("Bogota, D.C., Capital District, Colombia") == "Bogotá"
    assert normalizar_ciudad("Bogotá, CUN, Colombia") == "Bogotá"
    assert normalizar_ciudad("Medellín, Antioquia, Colombia") == "Medellín"
    assert normalizar_ciudad("Teusaquillo, Bogotá D.C.") == "Bogotá"
    assert normalizar_ciudad("Colombia", remoto=True) == "Remoto"
    assert normalizar_ciudad("4,5") == "Colombia"


def test_empresas_y_cargos():
    assert clave_empresa("Contadores Asociados S.A.S.") == clave_empresa("CONTADORES ASOCIADOS SAS")
    assert clave_empresa("Banco X Colombia S.A.") == "banco x"
    assert clave_cargo("Auxiliar Contable (a)") == clave_cargo("AUXILIAR CONTABLE")


def test_fechas():
    hoy = date(2026, 11, 5)
    assert normalizar_fecha("2026-10-02", hoy) == date(2026, 10, 2)
    assert normalizar_fecha("Hace 3 días", hoy) == date(2026, 11, 2)
    assert normalizar_fecha("15 hours ago", hoy) == hoy
    assert normalizar_fecha("Ayer", hoy) == date(2026, 11, 4)
    assert normalizar_fecha("2 weeks ago", hoy) == date(2026, 10, 22)
    assert normalizar_fecha("", hoy) is None


def test_tipo_nivel_modalidad():
    assert detectar_tipo_oferta("Practicante de Contabilidad") == "Práctica/pasantía"
    assert detectar_tipo_oferta("Aprendiz SENA administrativo") == "Práctica/pasantía"
    assert detectar_tipo_oferta("Analista contable") == "Empleo"
    assert detectar_nivel("Analista Senior de Riesgo") == "Senior"
    assert detectar_nivel("Auxiliar contable") == "Sin experiencia / Junior"
    assert detectar_nivel("Gerente financiero") == "Directivo"
    assert detectar_modalidad("Trabajo híbrido en Bogotá") == "Híbrido"
    assert detectar_modalidad("100% remoto") == "Remoto"


def test_quita_correos_telefonos_y_salarios():
    t = quitar_datos_personales("Envíe su hoja de vida a rrhh@empresa.com o al 3001234567. Salario: $1.750.000 mensuales")
    assert "@" not in t and "3001234567" not in t and "1.750.000" not in t
