"""Conectores para tiendas. Las URL de búsqueda experimentales NO son APIs oficiales."""
from dataclasses import dataclass
from urllib.parse import quote_plus, urlparse


@dataclass(frozen=True)
class Shop:
    name: str
    domain: str
    search_template: str = ""  # Si vacío, solo enlaces de búsqueda manual
    template_verified: bool = False
    extra_hosts: tuple[str, ...] = ()

    @property
    def allowed_hosts(self) -> set[str]:
        return {self.domain, "www." + self.domain, *self.extra_hosts}

    def search_url(self, term: str) -> str:
        if self.search_template:
            return self.search_template.format(q=quote_plus(term))
        if self.name == "Mercado Libre":
            return "https://listado.mercadolibre.com.mx/" + quote_plus(term)
        if self.name == "Amazon México":
            return "https://www.amazon.com.mx/s?k=" + quote_plus(term)
        # Búsqueda manual, no hacemos scraping de Google.
        return "https://www.google.com/search?q=" + quote_plus("site:" + self.domain + " " + term)


SHOPS = [
    Shop("Porrúa", "porrua.mx", "https://porrua.mx/catalogsearch/result/?q={q}", True),
    # Gandhi usa /s; parámetro ft es patrón de búsqueda experimental y puede cambiar.
    Shop("Gandhi", "gandhi.com.mx", "https://www.gandhi.com.mx/s?ft={q}", False),
    Shop("El Sótano", "elsotano.com"),
    Shop("Gonvill", "gonvill.com.mx"),
    Shop("Sanborns", "sanborns.com.mx"),
    Shop("Liverpool", "liverpool.com.mx"),
    Shop("Walmart México", "walmart.com.mx"),
    Shop("Office Depot", "officedepot.com.mx"),
    Shop("Coppel", "coppel.com"),
    Shop("Cyberpuerta", "cyberpuerta.mx"),
    Shop("Mercado Libre", "mercadolibre.com.mx", extra_hosts=("listado.mercadolibre.com.mx",)),
    Shop("Amazon México", "amazon.com.mx"),
]
SHOPS_BY_NAME = {shop.name: shop for shop in SHOPS}


def shop_for_url(url: str) -> Shop | None:
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.port not in (None, 443):
            return None
        host = (parsed.hostname or "").lower()
        return next((s for s in SHOPS if host in s.allowed_hosts), None)
    except ValueError:
        return None
