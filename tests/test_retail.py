from radar.retail import parse_product_html, price_float
from radar.discovery import candidate_product_links, title_similarity
from radar.shops import SHOPS, shop_for_url

PRODUCT = '''<html><h1>Superdeportistas mexicanos</h1><script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"Superdeportistas mexicanos",
"isbn":"9786073842839", "offers":{"@type":"Offer", "price": "269.00",
"priceCurrency":"MXN", "availability":"https://schema.org/InStock"}}
</script></html>'''


def test_exact_price():
    offers, status = parse_product_html(PRODUCT, "https://porrua.mx/superdeportistas-9786073842839.html", "9786073842839", "Porrúa")
    assert status == "FOUND" and offers[0].price == 269.0 and offers[0].match == "EXACT"


def test_reject_other_gtin_even_if_url_matches():
    mismatch = PRODUCT.replace('"isbn":"9786073842839"', '"isbn":"9786073842846"')
    offers, status = parse_product_html(mismatch, "https://porrua.mx/9786073842839.html", "9786073842839", "Porrúa")
    # Nunca atribuir la oferta de la edición equivocada.
    assert offers == []


def test_no_different_currency():
    offers, status = parse_product_html(PRODUCT.replace('"MXN"', '"USD"'),
                                        "https://porrua.mx/9786073842839.html", "9786073842839", "Porrúa")
    assert offers == [] and status == "PRODUCT_FOUND_NO_PRICE"


def test_url_only_not_exact():
    html = PRODUCT.replace('"isbn":"9786073842839"', '"sku":"SKU-X"')
    offers, state = parse_product_html(html, "https://porrua.mx/9786073842839.html", "9786073842839", "Porrúa")
    assert offers[0].match == "URL_ONLY" and state == "MATCH_UNCERTAIN"


def test_jsonld_graph_not_other_offers():
    html = '''<script type="application/ld+json">{"@graph":[
    {"@type":"Product","isbn":"9786073842839","name":"A","offers":{"price":123,"priceCurrency":"MXN"}},
    {"@type":"Product","isbn":"9786073842846","name":"B","offers":{"price":999,"priceCurrency":"MXN"}}]}
    </script>'''
    offers, _ = parse_product_html(html, "https://porrua.mx/producto.html", "9786073842839", "Porrúa")
    assert [x.price for x in offers] == [123]


def test_meta_tag_price_by_url():
    html = '<h1>Libro</h1><meta property="product:price:amount" content="449.90"><meta property="product:price:currency" content="MXN">'
    offers, status = parse_product_html(html, "https://porrua.mx/libro-9786073842839.html", "9786073842839", "Porrúa")
    assert offers[0].price == 449.90 and offers[0].match == "URL_ONLY"


def test_no_arbitrary_visible_price():
    html = '<h1>Libro</h1><p>Oferta $99.00</p>'
    offers, status = parse_product_html(html, "https://porrua.mx/libro-9786073842839.html", "9786073842839", "Porrúa")
    assert offers == []


def test_aggregate_lowprice_not_vendor_price():
    html = '''<script type="application/ld+json">{"@type":"Product","gtin13":"9786073842839",
    "offers":{"@type":"AggregateOffer","lowPrice":34,"priceCurrency":"MXN"}}</script>'''
    offers, _ = parse_product_html(html, "https://porrua.mx/producto.html", "9786073842839", "Porrúa")
    assert offers == []


def test_price_formats():
    assert price_float("$1,299.00") == 1299
    assert price_float("1.299,50") == 1299.5
    assert price_float("0") is None


def test_discovery_code_and_allowed_host():
    shop = SHOPS[0]
    html = '<a href="/super-9786073842839.html">Libro</a><a href="https://evil.test/9786073842839.html">Malo</a>'
    links = candidate_product_links(html, shop.search_url("9786073842839"), "9786073842839", shop)
    assert links == ["https://porrua.mx/super-9786073842839.html"]


def test_discovery_title_similarity():
    assert title_similarity("Memoria USB Kingston 64GB", "Memoria USB Kingston 64GB oferta") > .9
    assert title_similarity("Memoria USB Kingston 64GB", "Pelota de fútbol") < .4


def test_shop_host_allowlist():
    assert shop_for_url("https://porrua.mx/producto.html")
    assert not shop_for_url("http://porrua.mx/producto.html")
    assert not shop_for_url("https://porrua.mx.evil.test/producto.html")
    assert not shop_for_url("https://porrua.mx:8080/producto.html")
