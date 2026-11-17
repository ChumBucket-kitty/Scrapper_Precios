from radar.retail import parse_product_html, price_float, candidate_product_links
from radar.shops import SHOPS, shop_for_url

PRODUCT = '''<html><script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"Libro de prueba",
"isbn":"9786073842839", "offers":{"@type":"Offer", "price": "269.00",
"priceCurrency":"MXN", "availability":"https://schema.org/InStock"}}
</script></html>'''


def test_schema_product_exact_price():
    result, status = parse_product_html(PRODUCT, "https://porrua.mx/libro-9786073842839.html", "9786073842839", "Porrúa")
    assert status == "FOUND"
    assert len(result) == 1 and result[0].price == 269.0
    assert result[0].match == "EXACT"


def test_reject_mismatch():
    result, state = parse_product_html(PRODUCT, "https://porrua.mx/otro-libro.html", "9786073842846", "Porrúa")
    assert not result and state == "MATCH_UNCERTAIN"


def test_reject_unsupported_currency():
    html = PRODUCT.replace('"MXN"', '"USD"')
    result, state = parse_product_html(html, "https://porrua.mx/libro-9786073842839.html", "9786073842839", "Porrúa")
    assert not result and state == "PRODUCT_FOUND_NO_PRICE"


def test_uncertain_url_match():
    html = PRODUCT.replace('"isbn":"9786073842839"', '"sku":"INTERNAL234"')
    result, state = parse_product_html(html, "https://porrua.mx/libro-9786073842839.html", "9786073842839", "Porrúa")
    assert state == "MATCH_UNCERTAIN" and result[0].match == "URL_ONLY"


def test_no_unrelated_graph_product():
    html = '''<script type="application/ld+json">{"@graph":[
      {"@type":"Product","isbn":"9786073842839","name":"A","offers":{"price":123,"priceCurrency":"MXN"}},
      {"@type":"Product","isbn":"9786073842846","name":"B","offers":{"price":999,"priceCurrency":"MXN"}}]}
      </script>'''
    offers, _ = parse_product_html(html, "https://porrua.mx/producto.html", "9786073842839", "Porrúa")
    assert [o.price for o in offers] == [123]


def test_price_formats():
    assert price_float("$1,299.00") == 1299.0
    assert price_float("1.299,50") == 1299.5
    assert price_float("269") == 269
    assert price_float("0") is None


def test_shop_security():
    assert shop_for_url("https://porrua.mx/producto.html") is not None
    assert shop_for_url("https://porrua.mx.evil.example/prod") is None
    assert shop_for_url("http://porrua.mx/prod") is None
    assert shop_for_url("https://porrua.mx:444/prod") is None


def test_product_links():
    shop = SHOPS[0]
    html = '<a href="/libro-9786073842839.html">Prueba</a><a href="https://malicioso.test/libro-9786073842839.html">Malo</a>'
    links = candidate_product_links(html, "https://porrua.mx/catalogsearch/result/?q=9786073842839", "9786073842839", shop)
    assert links == ["https://porrua.mx/libro-9786073842839.html"]
