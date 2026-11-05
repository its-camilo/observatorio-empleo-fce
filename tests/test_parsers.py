"""Lectores de páginas con HTML mínimo de ejemplo (sin red)."""
from observatorio.scraper.computrabajo import parsear_detalle as ct_detalle, parsear_listado, slug, url_listado
from observatorio.scraper.linkedin import parsear_detalle, parsear_tarjetas

LI_DETALLE = """<html><h1 class="topcard__title">Analista Contable</h1>
<div class="show-more-less-html__markup"><p>Buscamos analista con <strong>Excel</strong>.</p><ul><li>SAP FICO</li></ul></div>
<ul><li class="description__job-criteria-item"><h3>Nivel de antigüedad</h3><span>Algo de responsabilidad</span></li>
<li class="description__job-criteria-item"><h3>Sectores</h3><span>Servicios financieros</span></li></ul></html>"""

LI_TARJETAS = """<li><div data-entity-urn="urn:li:jobPosting:123"><h3 class="base-search-card__title">Economista</h3>
<h4 class="base-search-card__subtitle"><a>Banco X</a></h4><span class="job-search-card__location">Bogotá, Colombia</span>
<time datetime="2026-11-01"></time></div></li>"""

CT_LISTADO = """<article class="box_offer" data-id="ABC123"><h2><a class="js-o-link" href="/ofertas-de-trabajo/oferta-ABC123#lc=x">Auxiliar contable</a></h2>
<p class="dFlex vm_fx fs16 fc_base mt5"><span class="fx_none mr10"><span class="fwB">4,5</span></span><a href="#">EMPRESA SAS</a></p>
<p class="fs16 fc_base mt5"><span class="mr10">Bogotá, D.C., Bogotá, D.C.</span></p>
<p class="fs13 fc_aux mt15">Hace 3 días</p></article>"""

CT_DETALLE = """<div div-link="oferta"><p class="mbB">Manejo de Siigo y Excel.
Salario: $ 1.750.000 mensuales
Palabras clave: contador, accountant</p></div>"""


def test_linkedin_detalle():
    d = parsear_detalle(LI_DETALLE)
    assert "Excel" in d["descripcion"] and "SAP FICO" in d["descripcion"]
    assert d["nivel"] == "Algo de responsabilidad" and d["sector"] == "Servicios financieros"


def test_linkedin_tarjetas():
    t = parsear_tarjetas(LI_TARJETAS)
    assert t == [{"id": "123", "cargo": "Economista", "empresa": "Banco X", "ubicacion": "Bogotá, Colombia", "fecha": "2026-11-01"}]


def test_computrabajo_listado():
    t = parsear_listado(CT_LISTADO)[0]
    assert t["id"] == "ABC123" and t["empresa"] == "EMPRESA SAS" and t["ubicacion"].startswith("Bogotá")
    assert t["fecha"] == "Hace 3 días" and t["url"].endswith("/ofertas-de-trabajo/oferta-ABC123")


def test_computrabajo_detalle_sin_salario_ni_palabras_clave():
    d = ct_detalle(CT_DETALLE)["descripcion"]
    assert "Siigo" in d and "1.750.000" not in d and "accountant" not in d


def test_urls_computrabajo():
    assert slug("Contador Público") == "contador-publico"
    assert url_listado("contador público", "bogota-dc", 2) == "https://co.computrabajo.com/trabajo-de-contador-publico-en-bogota-dc?p=2"
