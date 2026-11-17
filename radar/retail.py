"""Extracción de precios declarados en páginas de producto (no inferidos de listados).

Prioridad: Schema.org Product/Offer (JSON-LD o microdata) y metatags de precio.
Los precios se publican con calidad EXACT, TITLE_MATCH o URL_ONLY.
TITLE_MATCH/URL_ONLY son provisionales; no se mezclan con exactos en indicadores.
"""
import json
import re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

from .codes import clean_code
from .discovery import title_similarity
from .models import Offer
from .http import PoliteClient
from .shops import Shop


def price_float(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2) if 0 < float(value) < 1_000_000 else None
    raw = str(value or "").strip()
    if not raw:
        return None
    raw = re.sub(r"[^0-9,.]", "", raw)
    if not raw:
        return None
    if "," in raw and "." in raw:
        raw = raw.replace(",", "") if raw.rfind(".") > raw.rfind(",") else raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        if raw.count(",") == 1 and len(raw.rsplit(",", 1)[1]) in (1, 2):
            raw = raw.replace(",", ".")
        else:
            raw = raw.replace(",", "")
    try:
        price = float(raw)
        return round(price, 2) if 0 < price < 1_000_000 else None
    except ValueError:
        return None


def _iter_objects(data):
    if isinstance(data, list):
        for node in data:
            yield from _iter_objects(node)
    elif isinstance(data, dict):
        if "@graph" in data:
            yield from _iter_objects(data["@graph"])
        yield data


def _product_object(node: dict) -> bool:
    types = node.get("@type", node.get("type", []))
    types = types if isinstance(types, list) else [types]
    return any(str(t).lower().rstrip("/").endswith(("product", "book", "productmodel")) for t in types)


def _meta_products(soup: BeautifulSoup, html: str, url: str) -> list[dict]:
    products = []
    try:
        import extruct
        data = extruct.extract(html, base_url=url, syntaxes=["json-ld", "microdata"])
        for doc in data.get("json-ld", []):
            products.extend(obj for obj in _iter_objects(doc) if _product_object(obj))
        for entry in data.get("microdata", []):
            if not isinstance(entry, dict) or not _product_object(entry):
                continue
            props = entry.get("properties", {})
            if isinstance(props, dict):
                obj = dict(props)
                obj["@type"] = "Product"
                products.append(obj)
    except Exception:
        # Respaldo si extruct no está disponible o el sitio genera metadatos malformados.
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                node = json.loads(script.string or script.get_text() or "")
                products.extend(obj for obj in _iter_objects(node) if _product_object(obj))
            except (ValueError, TypeError):
                continue
    return products


def _scalar(value):
    if isinstance(value, list):
        return _scalar(value[0]) if value else ""
    if isinstance(value, dict):
        return str(value.get("value") or value.get("@value") or "")
    return str(value or "")


def _ids(product: dict) -> set[str]:
    fields = ("isbn", "gtin", "gtin8", "gtin12", "gtin13", "gtin14", "sku", "mpn", "productID", "productId")
    return {clean_code(_scalar(product[key])) for key in fields if product.get(key) and _scalar(product[key])}


def _page_title(soup: BeautifulSoup) -> str:
    h = soup.select_one("h1")
    if h and h.get_text(strip=True):
        return h.get_text(" ", strip=True)[:220]
    og = soup.select_one('meta[property="og:title"]')
    if og:
        return og.get("content", "")[:220]
    return ""


def _match(code: str, url: str, ids: set[str], candidate_title: str, known_title: str) -> str:
    if code in ids:
        return "EXACT"
    # Cuando hay un GTIN/ISBN explícitamente distinto, NO usar URL o título como sustituto.
    reliable = {x for x in ids if x.isdigit() and len(x) in (8, 12, 13, 14)}
    if reliable and code.isdigit() and len(code) in (8, 12, 13, 14) and code not in reliable:
        return "NO_MATCH"
    if code and len(code) >= 8 and code.lower() in urlparse(url).path.lower():
        return "URL_ONLY"
    if known_title and title_similarity(known_title, candidate_title) >= .82:
        return "TITLE_MATCH"
    return "NO_MATCH"


def _currency(obj: dict, parent: dict) -> str:
    cur = _scalar(obj.get("priceCurrency") or parent.get("priceCurrency") or "").upper().strip()
    return cur


def _offers_from_product(obj: dict) -> list[dict]:
    raw = obj.get("offers") or []
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    offers = []
    for offer in raw:
        if not isinstance(offer, dict):
            continue
        # AggregateOffer representa un agregado de vendedores, no un precio confirmado de la tienda.
        t = _scalar(offer.get("@type") or offer.get("type")).lower()
        if "aggregateoffer" in t and "price" not in offer:
            continue
        offers.append(offer)
    return offers


def _meta_price(soup: BeautifulSoup) -> tuple[float | None, str]:
    candidates = (
        ('meta[property="product:price:amount"]', "content"),
        ('meta[property="og:price:amount"]', "content"),
        ('meta[itemprop="price"]', "content"),
        ('[itemprop="price"][content]', "content"),
        ('[data-price-type="finalPrice"][data-price-amount]', "data-price-amount"),
        ('[data-price-amount][data-price-type="finalPrice"]', "data-price-amount"),
    )
    currency = ""
    for selector in ('meta[property="product:price:currency"]', 'meta[itemprop="priceCurrency"]', '[itemprop="priceCurrency"][content]'):
        tag = soup.select_one(selector)
        if tag:
            currency = (tag.get("content") or "").upper()
            break
    for selector, attribute in candidates:
        node = soup.select_one(selector)
        if node:
            price = price_float(node.get(attribute, ""))
            if price:
                return price, currency
    return None, currency


def parse_product_html(html: str, url: str, code: str, store: str, known_title: str = "") -> tuple[list[Offer], str]:
    soup = BeautifulSoup(html, "html.parser")
    products = _meta_products(soup, html, url)
    offers = []
    matched = False
    has_product = bool(products)
    for obj in products:
        title = _scalar(obj.get("name"))[:220] or _page_title(soup)
        match = _match(code, url, _ids(obj), title, known_title)
        if match == "NO_MATCH":
            continue
        matched = True
        for entry in _offers_from_product(obj):
            price_value = entry.get("price")
            if not price_value and isinstance(entry.get("priceSpecification"), dict):
                price_value = entry["priceSpecification"].get("price")
            price = price_float(price_value)
            currency = _currency(entry, obj)
            if not price or currency != "MXN":
                continue
            availability = _scalar(entry.get("availability")).split("/")[-1]
            offers.append(Offer(code=code, store=store, title=title, price=price,
                                currency="MXN", url=url, source="Schema.org / Extruct", match=match,
                                availability=availability, evidence="Precio de oferta en ficha de producto"))

    # Fallback para fichas que solo exponen metatags y no schema.org.
    if not offers:
        title = _page_title(soup)
        # Se requiere identidad verificable: URL (provisional) o título similar.
        match = _match(code, url, set(), title, known_title)
        if match != "NO_MATCH":
            matched = True
            amount, currency = _meta_price(soup)
            # Nunca asumir MXN si una página informa otra divisa.
            if amount and (currency == "MXN" or (not currency and urlparse(url).hostname and urlparse(url).hostname.endswith(".mx"))):
                offers.append(Offer(code=code, store=store, title=title, price=amount,
                                    currency="MXN", url=url, source="Metadatos de precio HTML",
                                    match=match, evidence="Precio declarado en metatag; confirmar si hay promoción"))

    unique = {(o.url, o.price, o.match): o for o in offers}
    offers = list(unique.values())
    if offers:
        return offers, "FOUND" if any(o.match == "EXACT" for o in offers) else "MATCH_UNCERTAIN"
    if matched:
        return [], "PRODUCT_FOUND_NO_PRICE"
    return [], "MATCH_UNCERTAIN" if has_product else "NOT_FOUND"


def scrape_one_url(client: PoliteClient, url: str, code: str, shop: Shop, title: str = "") -> tuple[list[Offer], str]:
    response = client.get_public_html(url, shop.allowed_hosts)
    return parse_product_html(response.text, response.url, code, shop.name, title)
