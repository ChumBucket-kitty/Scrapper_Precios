"""Crawlee HTTP (sin navegador) en consultas de búsqueda autorizadas.

La lectura de fichas siempre pasa por PoliteClient, con control de redirecciones.
No se usan proxies, evasión de CAPTCHA ni navegación automática sin límites.
"""
from datetime import timedelta
from urllib.parse import urlparse

from .http import FetchError, FetchResult, PoliteClient, USER_AGENT
from .shops import Shop


def fetch_search_with_crawlee(url: str, shop: Shop, client: PoliteClient, timeout: float = 10.0) -> FetchResult:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in shop.allowed_hosts:
        raise FetchError("INVALID_URL", "Dominio de búsqueda fuera del conector")
    # robots.txt: política comprobada antes de iniciar Crawlee; si no es legible, no hay crawl.
    policy = client._policy(f"https://{parsed.hostname}")
    if policy is not None and not policy.can_fetch(USER_AGENT, url):
        raise FetchError("ROBOTS_DISALLOWED", "robots.txt prohíbe la búsqueda")
    try:
        from crawlee.crawlers import BeautifulSoupCrawler
    except ImportError as exc:
        raise FetchError("DEPENDENCY_MISSING", "Crawlee no está instalado") from exc
    import asyncio

    async def visit():
        found = []
        failed = []
        crawler = BeautifulSoupCrawler(
            max_requests_per_crawl=1,
            max_request_retries=0,
            respect_robots_txt_file=True,
            navigation_timeout=timedelta(seconds=max(timeout, 5)),
            request_handler_timeout=timedelta(seconds=max(timeout + 5, 10)),
        )

        @crawler.router.default_handler
        async def on_page(context):
            loaded = getattr(context.request, "loaded_url", None) or context.request.url
            final_host = urlparse(loaded).hostname
            if final_host not in shop.allowed_hosts:
                raise FetchError("INVALID_URL", "La tienda redirigió fuera del dominio permitido")
            found.append(FetchResult(str(context.soup), loaded, 200))

        @crawler.router.failed_request_handler
        async def on_failure(context, error):
            failed.append(str(error)[:200])

        try:
            await crawler.run([url])
        except Exception as exc:
            failed.append(f"{type(exc).__name__}: {str(exc)[:150]}")
        return found, failed

    # Streamlit normalmente llama de forma síncrona desde su hilo de ejecución.
    try:
        pages, failures = asyncio.run(visit())
    except RuntimeError as exc:
        raise FetchError("SOURCE_ERROR", f"Error al ejecutar Crawlee: {type(exc).__name__}") from exc
    if pages:
        return pages[0]
    detail = " / ".join(failures)
    if "403" in detail or "401" in detail:
        raise FetchError("SOURCE_BLOCKED", "La tienda rechazó la búsqueda (HTTP 401/403)")
    if "429" in detail:
        raise FetchError("API_LIMIT", "La tienda limitó la consulta (HTTP 429)")
    if "robots" in detail.lower():
        raise FetchError("ROBOTS_DISALLOWED", "Crawlee no pudo visitar la ruta por robots.txt")
    raise FetchError("SOURCE_ERROR", "Crawlee no obtuvo HTML. " + detail[:100])
