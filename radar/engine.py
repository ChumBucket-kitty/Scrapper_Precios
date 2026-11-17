"""Motor principal. Las fallas de una tienda no impiden continuar con otras."""
from .codes import classify_code
from .catalog import lookup_metadata
from .http import PoliteClient, FetchError
from .models import Product, SearchResult, SourceStatus
from .openprices import fetch_observed_prices
from .retail import scrape_one_url
from .discovery import candidate_product_links
from .crawler import fetch_search_with_crawlee
from .shops import SHOPS, shop_for_url


def search_product(raw_code: str, *, label: str = "", stores: tuple[str, ...] = (),
                   automatic: tuple[str, ...] = (), manual_urls: tuple[str, ...] = (),
                   use_crawlee: bool = True, metadata: bool = True,
                   observed_prices: bool = False, timeout: float = 9.0) -> SearchResult:
    code, kind = classify_code(raw_code)
    if kind == "INVALID_CODE":
        return SearchResult(Product(code, kind), statuses=[
            SourceStatus("Entrada", "INVALID_CODE", "Código vacío, incorrecto o ISBN/EAN con dígito verificador inválido")])

    client = PoliteClient(timeout=timeout)
    if metadata:
        product, statuses = lookup_metadata(client, code, kind)
    else:
        product, statuses = Product(code, kind), []
    if label and not product.title:
        product.title = label.strip()[:200]
    result = SearchResult(product=product, statuses=statuses)
    enabled = [shop for shop in SHOPS if shop.name in stores]
    term = code if kind != "INTERNAL_SKU" else (product.title or code)
    result.search_links = [(shop.name, shop.search_url(term)) for shop in enabled]

    if observed_prices and kind in ("EAN8", "EAN13", "UPC"):
        offers, state = fetch_observed_prices(client, code)
        result.offers.extend(offers)
        result.statuses.append(state)

    # URLs proporcionadas: pueden ser tiendas sin buscador automático.
    visited = set()
    for raw_url in list(dict.fromkeys(u.strip() for u in manual_urls if u.strip()))[:8]:
        shop = shop_for_url(raw_url)
        if shop is None:
            result.statuses.append(SourceStatus("URL proporcionada", "INVALID_URL", "Solo fichas HTTPS de las tiendas configuradas", raw_url))
            continue
        try:
            offers, status = scrape_one_url(client, raw_url, code, shop, product.title)
            result.offers.extend(offers)
            result.statuses.append(SourceStatus(shop.name + " · ficha directa", status,
                                  "Precio consultado" if offers else "No se pudo verificar un precio para el código", raw_url))
            visited.add(raw_url)
        except FetchError as exc:
            result.statuses.append(SourceStatus(shop.name + " · ficha directa", exc.code, str(exc), raw_url))
        except Exception as exc:
            result.statuses.append(SourceStatus(shop.name + " · ficha directa", "SOURCE_ERROR", type(exc).__name__, raw_url))

    for shop in enabled:
        if shop.name not in automatic or not shop.search_template:
            result.statuses.append(SourceStatus(shop.name + " · automático", "SKIPPED", "Sin consulta automática (enlace manual disponible)"))
            continue
        url = shop.search_url(term)
        try:
            if use_crawlee:
                page = fetch_search_with_crawlee(url, shop, client, timeout)
            else:
                page = client.get_public_html(url, shop.allowed_hosts)
            candidates = candidate_product_links(page.text, page.url, code, shop, product.title, limit=3)
            if not candidates:
                result.statuses.append(SourceStatus(shop.name + " · búsqueda", "NOT_FOUND", "La búsqueda respondió, pero no se identificaron enlaces de producto confiables", url))
                continue
            result.statuses.append(SourceStatus(shop.name + " · búsqueda", "FOUND", f"{len(candidates)} ficha(s) candidata(s); falta validarlas", url))
            for candidate in candidates:
                if candidate in visited:
                    continue
                visited.add(candidate)
                try:
                    offers, state = scrape_one_url(client, candidate, code, shop, product.title)
                    result.offers.extend(offers)
                    result.statuses.append(SourceStatus(shop.name + " · producto", state,
                                         "Precio recuperado" if offers else "Sin precio verificable", candidate))
                except FetchError as exc:
                    result.statuses.append(SourceStatus(shop.name + " · producto", exc.code, str(exc), candidate))
                except Exception as exc:
                    result.statuses.append(SourceStatus(shop.name + " · producto", "SOURCE_ERROR", type(exc).__name__, candidate))
        except FetchError as exc:
            result.statuses.append(SourceStatus(shop.name + " · búsqueda", exc.code, str(exc), url))
        except Exception as exc:
            result.statuses.append(SourceStatus(shop.name + " · búsqueda", "SOURCE_ERROR", type(exc).__name__, url))

    dedup = {}
    for offer in result.offers:
        key = (offer.store, offer.url, offer.price, offer.kind, offer.match)
        dedup[key] = offer
    result.offers = sorted(dedup.values(), key=lambda o: (o.kind != "ONLINE", o.price))
    return result
