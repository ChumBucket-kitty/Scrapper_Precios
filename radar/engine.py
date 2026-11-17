"""Orquestador independiente de Streamlit: fácil de ampliar con conectores."""
from .codes import classify_code
from .catalog import lookup_metadata
from .http import PoliteClient, FetchError
from .models import Product, SearchResult, SourceStatus
from .openprices import fetch_observed_prices
from .retail import candidate_product_links, scrape_one_url
from .shops import SHOPS, shop_for_url


def search_product(raw_code: str, *, label: str = "", stores: tuple[str, ...] = (),
                   manual_urls: tuple[str, ...] = (), auto_porrua: bool = False,
                   low_volume: bool = True, open_prices: bool = True, timeout: float = 7.0) -> SearchResult:
    code, kind = classify_code(raw_code)
    term = label.strip()[:120] if label.strip() else code
    if kind == "INVALID_CODE":
        return SearchResult(Product(code, kind), statuses=[SourceStatus("Entrada", "INVALID_CODE", "Código vacío, mal formado o con dígito de control inválido")])
    client = PoliteClient(timeout=timeout)
    product, statuses = lookup_metadata(client, code, kind, use_openlibrary=low_volume)
    if label and not product.title:
        product.title = label.strip()[:200]
        # Una descripción aportada por el usuario NO es verificación externa.
    r = SearchResult(product=product, statuses=statuses)
    enabled = [s for s in SHOPS if s.name in stores]
    r.search_links = [(s.name, s.search_url(term)) for s in enabled]

    if open_prices and kind in ("EAN8", "EAN13", "UPC"):
        obs, state = fetch_observed_prices(client, code)
        r.offers.extend(obs)
        r.statuses.append(state)

    for url in dict.fromkeys(u.strip() for u in manual_urls if u.strip()):
        shop = shop_for_url(url)
        if shop is None:
            r.statuses.append(SourceStatus("URL proporcionada", "INVALID_URL", "Se admiten solo URLs HTTPS de tiendas configuradas", url))
            continue
        try:
            offers, state = scrape_one_url(client, url, code, shop)
            r.offers.extend(offers)
            r.statuses.append(SourceStatus(shop.name + " (URL)", state, "Ficha analizada" if offers else "Sin precio verificable en MXN o no corresponde al código", url))
        except FetchError as exc:
            r.statuses.append(SourceStatus(shop.name + " (URL)", exc.code, str(exc), url))

    if auto_porrua and kind in ("ISBN10", "ISBN13"):
        shop = next((s for s in enabled if s.name == "Porrúa"), None)
        if shop:
            search_url = shop.search_url(code)
            try:
                page = client.get_public_html(search_url, shop.allowed_hosts)
                links = candidate_product_links(page.text, page.url, code, shop)
                for detail_url in links:
                    try:
                        offers, state = scrape_one_url(client, detail_url, code, shop)
                        r.offers.extend(offers)
                        r.statuses.append(SourceStatus("Porrúa (ficha)", state,
                                                       "Ficha encontrada" if offers else "Sin oferta verificable", detail_url))
                    except FetchError as exc:
                        r.statuses.append(SourceStatus("Porrúa (ficha)", exc.code, str(exc), detail_url))
                if not links:
                    r.statuses.append(SourceStatus("Porrúa (búsqueda)", "NOT_FOUND",
                                                   "No se localizaron fichas con el ISBN en la URL", search_url))
            except FetchError as exc:
                r.statuses.append(SourceStatus("Porrúa (búsqueda)", exc.code, str(exc), search_url))
    # Deduplicación básica cuando el usuario introdujo la misma ficha más de una vez.
    keys = set()
    unique = []
    for o in r.offers:
        key = (o.store, o.url, o.price, o.kind)
        if key not in keys:
            unique.append(o)
            keys.add(key)
    r.offers = unique
    return r
