"""Extracción estricta de ofertas públicas, principalmente Schema.org JSON-LD."""
import json
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from .models import Offer
from .http import PoliteClient, FetchError
from .shops import Shop


def price_float(value) -> float | None:
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        return round(float(value), 2) if 0 < float(value) < 1_000_000 else None
    s = re.sub(r"[^\d,.]", "", str(value or ""))
    if not s:
        return None
    if ',' in s and '.' in s:
        # El separador decimal es el último.
        s = s.replace(',', '') if s.rfind('.') > s.rfind(',') else s.replace('.', '').replace(',', '.')
    elif s.count(',') == 1 and len(s.rsplit(',', 1)[1]) in (1, 2):
        s = s.replace(',', '.')
    else:
        s = s.replace(',', '')
    try:
        x = float(s)
        return round(x, 2) if 0 < x < 1_000_000 else None
    except ValueError:
        return None


def _objects(node):
    if isinstance(node, list):
        for child in node:
            yield from _objects(child)
    elif isinstance(node, dict):
        if "@graph" in node:
            yield from _objects(node["@graph"])
        yield node


def _is_product(obj: dict) -> bool:
    kinds = obj.get("@type", [])
    kinds = kinds if isinstance(kinds, list) else [kinds]
    return any(str(t).lower().endswith("product") for t in kinds)


def _identifiers(obj: dict) -> set[str]:
    values = set()
    for key in ("gtin", "gtin8", "gtin12", "gtin13", "gtin14", "isbn", "sku", "productID", "mpn"):
        v = obj.get(key)
        if isinstance(v, (str, int)):
            from .codes import clean_code
            values.add(clean_code(str(v)))
    return values


def _find_offers(obj: dict) -> list[dict]:
    offers = obj.get("offers", [])
    offers = offers if isinstance(offers, list) else [offers]
    # Sin recurrir a otros bloques ni a productos recomendados de la página.
    return [o for o in offers if isinstance(o, dict)]


def parse_product_html(html: str, url: str, code: str, store: str) -> tuple[list[Offer], str]:
    soup = BeautifulSoup(html, "html.parser")
    found_product = False
    offers = []
    found_match = False
    for script in soup.find_all("script", type=lambda x: x and "ld+json" in x.lower()):
        try:
            blob = json.loads(script.string or script.get_text() or "")
        except (ValueError, TypeError):
            continue
        for obj in _objects(blob):
            if not _is_product(obj):
                continue
            found_product = True
            ids = _identifiers(obj)
            # Un SKU distinto no demuestra que el GTIN es distinto: se exige la coincidencia si está.
            if code in ids:
                match = "EXACT"
            elif code in urlparse(url).path.upper():
                match = "URL_ONLY"  # plausible, no identificación verificada
            else:
                continue
            found_match = True
            for offer in _find_offers(obj):
                price = price_float(offer.get("price"))
                currency = str(offer.get("priceCurrency") or "").upper()
                if price is None or currency != "MXN":
                    continue
                offer_url = offer.get("url") or url
                if not isinstance(offer_url, str):
                    offer_url = url
                # Evita atribuir el precio a otra URL o dominio.
                parsed = urlparse(urljoin(url, offer_url))
                if parsed.hostname != urlparse(url).hostname:
                    offer_url = url
                availability = str(offer.get("availability", "")).rsplit("/", 1)[-1]
                offers.append(Offer(code=code, store=store, title=str(obj.get("name", "") or ""),
                                    price=price, currency="MXN", url=urljoin(url, offer_url),
                                    source="HTML público / JSON-LD", match=match,
                                    availability=availability, evidence="Oferta publicada en ficha del sitio"))
    if offers:
        uniq = {(o.url, o.price): o for o in offers}
        return list(uniq.values()), "FOUND" if any(o.match == "EXACT" for o in offers) else "MATCH_UNCERTAIN"
    if found_match:
        return [], "PRODUCT_FOUND_NO_PRICE"
    if found_product:
        return [], "MATCH_UNCERTAIN"
    return [], "NOT_FOUND"


def candidate_product_links(html: str, search_url: str, code: str, shop: Shop) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    result = []
    for a in soup.select("a[href]"):
        href = urljoin(search_url, a.get("href", ""))
        parsed = urlparse(href)
        if (parsed.scheme == "https" and parsed.hostname in shop.allowed_hosts and
            code in parsed.path.upper() and href != search_url and href not in result):
            result.append(href)
        if len(result) >= 2:
            break
    return result


def scrape_one_url(client: PoliteClient, url: str, code: str, shop: Shop) -> tuple[list[Offer], str]:
    page = client.get_public_html(url, shop.allowed_hosts)
    return parse_product_html(page.text, page.url, code, shop.name)
