"""Excel: tamaño apto para Vercel y openpyxl válido."""
from __future__ import annotations

import io

from openpyxl import load_workbook

from observatorio.exportar import MAX_EXCEL_RESPUESTA_BYTES, a_excel


def test_excel_sin_descripcion_cabe_en_limite_vercel(sesion):
    data = a_excel(sesion, incluir_descripcion=False)
    assert len(data) > 1000
    assert len(data) < MAX_EXCEL_RESPUESTA_BYTES
    wb = load_workbook(io.BytesIO(data), read_only=True)
    assert "Ofertas" in wb.sheetnames
    wb.close()

