import radar.engine as engine
from radar.models import Product
from radar.http import FetchError, FetchResult

CODE = "9786073842839"
SEARCH = '<a href="/libro-9786073842839.html">Libro</a>'
DETAIL = '''<h1>Superdeportistas mexicanos</h1><script type="application/ld+json">
{"@type":"Product", "isbn":"9786073842839", "name":"Superdeportistas mexicanos",
"offers":{"price":269,"priceCurrency":"MXN"}}</script>'''


class Client:
    def __init__(self, timeout=9):
        pass

    def get_public_html(self, url, hosts):
        if "catalogsearch" in url:
            return FetchResult(SEARCH, url, 200)
        if "/libro-" in url:
            return FetchResult(DETAIL, url, 200)
        raise FetchError("SOURCE_BLOCKED", "HTTP 403")


def fake_meta(client, code, kind):
    return Product(code, kind, title="Superdeportistas mexicanos", status="FOUND"), []


def test_auto_search_recovers_price(monkeypatch):
    monkeypatch.setattr(engine, "PoliteClient", Client)
    monkeypatch.setattr(engine, "lookup_metadata", fake_meta)
    r = engine.search_product(CODE, stores=("Porrúa",), automatic=("Porrúa",), use_crawlee=False)
    assert r.offers[0].price == 269 and r.offers[0].match == "EXACT"
    assert r.status == "FOUND"


def test_explicit_url_in_any_shop(monkeypatch):
    monkeypatch.setattr(engine, "PoliteClient", Client)
    monkeypatch.setattr(engine, "lookup_metadata", fake_meta)
    r = engine.search_product(CODE, manual_urls=("https://porrua.mx/libro-9786073842839.html",), stores=(), use_crawlee=False)
    assert len(r.offers) == 1


def test_blocked_not_not_found(monkeypatch):
    class Blocked(Client):
        def get_public_html(self, url, hosts):
            raise FetchError("SOURCE_BLOCKED", "HTTP 403")
    monkeypatch.setattr(engine, "PoliteClient", Blocked)
    r = engine.search_product(CODE, stores=("Porrúa",), automatic=("Porrúa",),
                              metadata=False, use_crawlee=False)
    assert r.status == "PARTIAL_RESULTS"
    assert any(s.code == "SOURCE_BLOCKED" for s in r.statuses)


def test_sku_never_invents_prices(monkeypatch):
    monkeypatch.setattr(engine, "PoliteClient", Client)
    r = engine.search_product("SKU-INTERNO-001", metadata=False)
    assert not r.offers and r.status == "INTERNAL_SKU"


def test_invalid_code(monkeypatch):
    r = engine.search_product("9786073842830", metadata=False)
    assert r.status == "INVALID_CODE" and not r.offers
