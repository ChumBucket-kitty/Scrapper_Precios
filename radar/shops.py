"""Tiendas mexicanas: enlaces públicos; no se anuncia API donde no existe."""
from dataclasses import dataclass
from urllib.parse import quote_plus


@dataclass(frozen=True)
class Shop:
    name: str
    domain: str
    auto_search: bool = False
    hosts: tuple[str, ...] = ()

    def search_url(self, term: str) -> str:
        if self.name == "Porrúa":
            return f"https://porrua.mx/catalogsearch/result/?q={quote_plus(term)}"
        if self.name == "Mercado Libre":
            return f"https://listado.mercadolibre.com.mx/{quote_plus(term)}"
        if self.name == "Amazon México":
            return f"https://www.amazon.com.mx/s?k={quote_plus(term)}"
        # Enlace de investigación para humanos, no es una API ni se extrae Google.
        return f"https://www.google.com/search?q={quote_plus('site:' + self.domain + ' ' + term)}"

    @property
    def allowed_hosts(self) -> set[str]:
        return {self.domain, "www." + self.domain, *self.hosts}


SHOPS = [
    Shop("Porrúa", "porrua.mx", auto_search=True),
    Shop("Gandhi", "gandhi.com.mx"),
    Shop("El Sótano", "elsotano.com"),
    Shop("Gonvill", "gonvill.com.mx"),
    Shop("Sanborns", "sanborns.com.mx"),
    Shop("Liverpool", "liverpool.com.mx"),
    Shop("Walmart México", "walmart.com.mx"),
    Shop("Office Depot", "officedepot.com.mx"),
    Shop("Coppel", "coppel.com"),
    Shop("Cyberpuerta", "cyberpuerta.mx"),
    Shop("Mercado Libre", "mercadolibre.com.mx", hosts=("listado.mercadolibre.com.mx",)),
    Shop("Amazon México", "amazon.com.mx"),
]


def shop_for_url(url: str) -> Shop | None:
    from urllib.parse import urlparse
    try:
        p = urlparse(url)
        if p.scheme != "https" or p.port not in (None, 443):
            return None
        host = (p.hostname or "").lower()
        return next((s for s in SHOPS if host in s.allowed_hosts), None)
    except ValueError:
        return None
