"""Metadatos de acceso abierto, sin claves ni cuotas freemium."""
from .models import Product, SourceStatus
from .http import PoliteClient, FetchError


def lookup_metadata(client: PoliteClient, code: str, kind: str, use_openlibrary: bool = True):
    product = Product(code=code, kind=kind, status="NOT_FOUND")
    states: list[SourceStatus] = []
    if kind in ("ISBN10", "ISBN13") and use_openlibrary:
        url = f"https://openlibrary.org/isbn/{code}.json"
        try:
            obj = client.get_json(url)
            product.title = obj.get("title", "") or ""
            pubs = obj.get("publishers", [])
            product.publisher = ", ".join(pubs[:2]) if isinstance(pubs, list) else ""
            covers = obj.get("covers", [])
            if isinstance(covers, list) and covers:
                product.image_url = f"https://covers.openlibrary.org/b/id/{covers[0]}-M.jpg"
            if product.title:
                product.source, product.status = "Open Library", "FOUND"
                states.append(SourceStatus("Open Library", "FOUND", "Ficha bibliográfica localizada", url))
            else:
                states.append(SourceStatus("Open Library", "NOT_FOUND", "No hay ficha para este ISBN", url))
        except FetchError as exc:
            states.append(SourceStatus("Open Library", exc.code, str(exc), url))
    elif kind in ("ISBN10", "ISBN13"):
        states.append(SourceStatus("Open Library", "SKIPPED", "Consultas masivas desactivadas para respetar política de uso"))

    if kind in ("EAN8", "EAN13", "UPC"):
        # Open Products Facts (general) y Open Food Facts (alimentos).
        for site, source in (("world.openproductsfacts.org", "Open Products Facts"),
                             ("world.openfoodfacts.org", "Open Food Facts")):
            url = f"https://{site}/api/v2/product/{code}"
            try:
                obj = client.get_json(url, {"fields": "code,product_name,product_name_es,brands,image_front_url,image_url"})
                data = obj.get("product") or {}
                if obj.get("status") == 1 and isinstance(data, dict):
                    title = data.get("product_name_es") or data.get("product_name") or ""
                    if title:
                        product.title = title
                        product.brand = data.get("brands", "") or ""
                        product.image_url = data.get("image_front_url") or data.get("image_url") or ""
                        product.source, product.status = source, "FOUND"
                        states.append(SourceStatus(source, "FOUND", "Producto identificado", url))
                        break
                states.append(SourceStatus(source, "NOT_FOUND", "Sin registro de este código", url))
            except FetchError as exc:
                states.append(SourceStatus(source, exc.code, str(exc), url))
    if kind == "INTERNAL_SKU":
        states.append(SourceStatus("Identificación", "INTERNAL_SKU", "SKU interno: sin equivalencia pública conocida"))
    return product, states
