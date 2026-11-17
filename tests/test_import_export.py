import io
from openpyxl import Workbook, load_workbook
from radar.io import read_codes, workbook_bytes
from radar.models import Product, SearchResult, SourceStatus, Offer


def test_csv_keep_long_id():
    content = 'ISBN,Descripcion\n9786073842839,Libro\n9786073842839,Duplicado\n4006381333931,Prueba'.encode()
    assert read_codes('codigos.csv', content) == [('9786073842839', 'Libro'), ('4006381333931', 'Prueba')]


def test_xlsx_keep_code_as_text():
    w = Workbook()
    w.active.append(['Materiales', 'Descripción'])
    w.active.append(['9786073842839', 'Libro'])
    buf = io.BytesIO()
    w.save(buf)
    assert read_codes('inventario.xlsx', buf.getvalue()) == [('9786073842839', 'Libro')]


def test_export_offers_and_statuses():
    r = SearchResult(Product('9786073842839', 'ISBN13', title='Libro'),
                     offers=[Offer('9786073842839','Tienda','Libro',299.0,'MXN','https://porrua.mx/libro','JSON-LD','EXACT')],
                     statuses=[SourceStatus('Tienda','FOUND','Hay precio')])
    payload = workbook_bytes([r])
    w = load_workbook(io.BytesIO(payload))
    assert w.sheetnames == ['Productos','Ofertas','Diagnostico','Enlaces']
    assert w['Productos']['A2'].value == '9786073842839'
    assert w['Productos']['A2'].data_type == 's'
    assert w['Ofertas']['D2'].value == 299


def test_formula_injection_prevented():
    r = SearchResult(Product('SKU-1', 'INTERNAL_SKU', title='=HYPERLINK("bad")'))
    w = load_workbook(io.BytesIO(workbook_bytes([r])))
    assert w['Productos']['C2'].data_type == 's'
