from radar.openprices import fetch_observed_prices
from radar.catalog import lookup_metadata
from radar.models import Product, SearchResult, SourceStatus
from radar.http import PoliteClient, FetchError


class FakeClient:
    def get_json(self, url, params=None):
        if 'openlibrary.org' in url:
            return {'title': 'Libro ejemplo', 'publishers': ['Editorial Prueba'], 'covers': [123]}
        if 'prices.openfoodfacts' in url:
            return {'items': [
                {'product_code': '4006381333931', 'price': 30.00, 'price_per': 'UNIT', 'currency': 'MXN',
                 'date': '2025-01-12', 'location': {'osm_name': 'Tienda X', 'osm_address_country_code': 'MX'}},
                {'product_code': '4006381333931', 'price': 3.00, 'price_per': 'KILOGRAM', 'currency': 'MXN',
                 'location': {'osm_address_country_code': 'MX'}},
                {'product_code': '4006381333931', 'price': 88.00, 'currency': 'EUR'}]}
        return {'status': 0}


def test_open_library_info():
    prod, states = lookup_metadata(FakeClient(), '9786073842839', 'ISBN13')
    assert prod.title == 'Libro ejemplo' and prod.status == 'FOUND'


def test_open_prices_historical_not_current():
    prices, state = fetch_observed_prices(FakeClient(), '4006381333931')
    assert len(prices) == 1 and prices[0].kind == 'HISTORICAL' and prices[0].published_at == '2025-01-12'
    assert state.code == 'FOUND'
    r = SearchResult(Product('4006381333931', 'EAN13'), offers=prices)
    assert r.status == 'HISTORICAL_ONLY'


def test_robots_refuse_without_network():
    client = PoliteClient()
    try:
        client.get_public_html('http://porrua.mx/test', {'porrua.mx'})
    except FetchError as exc:
        assert exc.code == 'INVALID_URL'
    else:
        raise AssertionError('Debe rechazar HTTP')
