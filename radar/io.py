"""Importación CSV/XLSX y exportación Excel sin perder ceros iniciales."""
import csv
import io
import re
import unicodedata
from openpyxl import load_workbook, Workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter
from .models import SearchResult

HEADERS = {"codigo", "codigos", "isbn", "ean", "upc", "sku", "material", "materiales", "producto", "code", "id", "gtin"}
LABELS = {"descripcion", "titulo", "nombre", "name", "description", "producto nombre"}
MAX_BATCH = 30


def key_of(v) -> str:
    return re.sub(r"\s+", " ", "".join(c for c in unicodedata.normalize("NFD", str(v or "").lower())
                            if unicodedata.category(c) != "Mn")).strip()


def to_code(cell) -> str:
    if cell is None:
        return ""
    if isinstance(cell, float):
        return str(int(cell)) if cell.is_integer() else str(cell)
    return str(cell).strip()


def read_codes(name: str, payload: bytes, max_rows: int = MAX_BATCH) -> list[tuple[str, str]]:
    if len(payload) > 4_000_000:
        raise ValueError("Archivo demasiado grande (máximo 4 MB)")
    rows = []
    if name.lower().endswith(".xlsx"):
        wb = load_workbook(io.BytesIO(payload), read_only=True, data_only=True)
        try:
            ws = wb.active
            rows = list(ws.iter_rows(min_row=1, max_row=max_rows + 50, values_only=True))
        finally:
            wb.close()
    elif name.lower().endswith(".csv"):
        try:
            text = payload.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = payload.decode("latin1")
        sample = text[:2048]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.reader(io.StringIO(text), dialect=dialect))[:max_rows + 50]
    else:
        raise ValueError("Solo se aceptan archivos .xlsx o .csv")
    if not rows:
        return []
    headers = [key_of(v) for v in rows[0]]
    code_col = next((i for i, h in enumerate(headers) if h in HEADERS), None)
    title_col = next((i for i, h in enumerate(headers) if h in LABELS), None)
    if code_col is None:
        # Se permite un CSV sin encabezado; todo se interpreta como código en la primera columna.
        if len(rows[0]) <= 2 and not any(" " in str(x or "") for x in rows[0]):
            code_col, start = 0, 0
        else:
            raise ValueError("No encontré columna ISBN, EAN, UPC, SKU, Materiales o Código")
    else:
        start = 1
    selected = []
    seen = set()
    for row in rows[start:]:
        code = to_code(row[code_col]) if code_col < len(row) else ""
        title = to_code(row[title_col]) if title_col is not None and title_col < len(row) else ""
        if code and code not in seen:
            selected.append((code, title))
            seen.add(code)
        if len(selected) >= max_rows:
            break
    return selected


def _safe(v):
    if isinstance(v, str) and v.startswith(("=", "+", "-", "@")):
        return "'" + v  # Evita inyección de fórmulas en archivos compartidos.
    return v


def workbook_bytes(results: list[SearchResult]) -> bytes:
    wb = Workbook()
    main = wb.active
    main.title = "Productos"
    specs = [
        ("Productos", ["Código", "Tipo", "Descripción", "Marca", "Editorial", "Estado", "Fuente identificación", "Precios web MXN", "Históricos MXN"],
         [[r.product.code, r.product.kind, r.product.title, r.product.brand, r.product.publisher,
           r.status, r.product.source, sum(o.kind == "ONLINE" and o.currency == "MXN" for o in r.offers),
           sum(o.kind == "HISTORICAL" for o in r.offers)] for r in results]),
        ("Ofertas", ["Código", "Tienda", "Descripción", "Precio MXN", "Tipo precio", "Coincidencia", "Origen", "Disponibilidad", "Fecha publicación", "Fecha consulta UTC", "URL", "Nota"],
         [[o.code, o.store, o.title, o.price, o.kind, o.match, o.source, o.availability,
           o.published_at, o.observed_at, o.url, o.evidence] for r in results for o in r.offers]),
        ("Diagnostico", ["Código", "Fuente", "Estado", "Detalle", "URL", "Fecha UTC"],
         [[r.product.code, s.source, s.code, s.message, s.url, s.checked_at] for r in results for s in r.statuses]),
        ("Enlaces", ["Código", "Tienda", "Buscar en"],
         [[r.product.code, name, link] for r in results for name, link in r.search_links]),
    ]
    for n, (name, headers, data) in enumerate(specs):
        ws = main if n == 0 else wb.create_sheet(name)
        ws.append(headers)
        for row in data:
            ws.append([_safe(v) for v in row])
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{max(2,ws.max_row)}"
        for c in ws[1]:
            c.fill = PatternFill("solid", fgColor="17345C")
            c.font = Font(bold=True, color="FFFFFF")
            c.alignment = Alignment(wrap_text=True)
        for col in ws.columns:
            letter = col[0].column_letter
            width = min(49, max(12, max(len(str(c.value or "")) for c in list(col)[:100]) + 2))
            ws.column_dimensions[letter].width = width
        for row in ws.iter_rows(min_row=2):
            row[0].number_format = "@"
        if name == "Ofertas":
            for row in ws.iter_rows(min_row=2):
                row[3].number_format = '"$"#,##0.00'
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
