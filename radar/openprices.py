"""Precios observados y comunitarios: no equivalen a cotizaciones vigentes."""
from .http import PoliteClient, FetchError
from .models import Offer, SourceStatus

URL = "https://prices.openfoodfacts.org/api/v1/prices"


def fetch_observed_prices(client: PoliteClient, code: str):
    try:
        data = client.get_json(URL, {"product_code": code, "currency": "MXN", "size": 20, "page": 1})
    except FetchError as exc:
        return [], SourceStatus("Open Prices", exc.code, str(exc), URL)
    offers = []
    for item in data.get("items", []):
        if not isinstance(item, dict) or str(item.get("product_code", "")) != code:
            continue
        if item.get("currency") != "MXN" or item.get("price_per", "UNIT") not in ("UNIT", None):
            continue
        from .retail import price_float
        price = price_float(item.get("price"))
        if price is None:
            continue
        location = item.get("location") or {}
        if not isinstance(location, dict):
            location = {}
        country = (location.get("osm_address_country_code") or "").upper()
        if country and country != "MX":
            continue
        name = (location.get("osm_name") or location.get("osm_display_name") or "Comercio no identificado")
        product = item.get("product") or {}
        offers.append(Offer(code=code, store=str(name), title=str(item.get("product_name") or product.get("product_name") or ""),
                            price=price, currency="MXN", url="https://prices.openfoodfacts.org/",
                            source="Open Prices (dato comunitario)", match="EXACT", kind="HISTORICAL",
                            published_at=str(item.get("date") or ""),
                            evidence="Precio observado, no cotización web actual; fuente ODbL"))
    return offers, SourceStatus("Open Prices", "FOUND" if offers else "NOT_FOUND",
                                f"{len(offers)} precios comunitarios en MXN" if offers else "Sin precios comunitarios en MXN para este código", URL)
