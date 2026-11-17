"""Descubre candidatos en la búsqueda interna sin atribuirles precios todavía."""
import re
import unicodedata
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from .shops import Shop


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def title_similarity(title: str, candidate: str) -> float:
    terms = {x for x in normalized(title).split() if len(x) >= 4}
    found = set(normalized(candidate).split())
    if len(terms) < 2:
        return 0.0
    return len(terms.intersection(found)) / len(terms)


def candidate_product_links(html: str, search_url: str, code: str, shop: Shop,
                            title: str = "", limit: int = 3) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    scores = {}
    for a in soup.select("a[href]"):
        href = urljoin(search_url, a.get("href", ""))
        p = urlparse(href)
        if p.scheme != "https" or p.hostname not in shop.allowed_hosts or p.path in ("", "/", "/s"):
            continue
        if href.split("#")[0] == search_url.split("#")[0]:
            continue
        # Evita enlaces a búsqueda, perfil, carrito y categoría general.
        if any(x in p.path.lower() for x in ("/account", "/cart", "/checkout", "/catalogsearch/", "/search", "/login", "/wishlist")):
            continue
        card = a.find_parent(attrs={"data-product-id": True}) or a.find_parent(class_=re.compile("product|item", re.I))
        context = (a.get_text(" ", strip=True) + " " + (card.get_text(" ", strip=True)[:300] if card else ""))
        value = 0
        if code and (code.lower() in href.lower() or code.lower() in context.lower()):
            value = 100
        elif title and title_similarity(title, context + " " + p.path.replace("-", " ")) >= .75:
            value = 45  # Solo descubrimiento; la ficha deberá validar identidad.
        if value:
            scores[href] = max(scores.get(href, 0), value)
    return [url for url, _ in sorted(scores.items(), key=lambda it: -it[1])[:limit]]
