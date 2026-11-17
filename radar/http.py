"""Cliente prudente: sin elusión de CAPTCHA, sin proxy y con respeto por robots.txt."""
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import requests
import time

USER_AGENT = "RadarPreciosMX/1.0 (Streamlit; consulta manual, sin scraping masivo)"


class FetchError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass
class FetchResult:
    text: str
    url: str
    status: int


class PoliteClient:
    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT,
                                     "Accept": "text/html,application/json;q=0.9,*/*;q=0.7"})
        self._robots: dict[str, tuple[float, RobotFileParser | None, str]] = {}
        self._last: dict[str, float] = {}

    def get_json(self, url: str, params: dict | None = None) -> dict:
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
        except requests.Timeout as exc:
            raise FetchError("TIMEOUT", "El servicio no respondió dentro del tiempo límite") from exc
        except requests.RequestException as exc:
            raise FetchError("API_ERROR", f"Error de conexión: {str(exc)[:120]}") from exc
        self._check_status(resp.status_code)
        try:
            obj = resp.json()
        except ValueError as exc:
            raise FetchError("API_ERROR", "La API no devolvió JSON válido") from exc
        if not isinstance(obj, dict):
            raise FetchError("API_ERROR", "Respuesta inesperada de la API")
        return obj

    @staticmethod
    def _check_status(status: int) -> None:
        if status == 403 or status == 401:
            raise FetchError("SOURCE_BLOCKED", f"El sitio rechazó la petición (HTTP {status})")
        if status == 429:
            raise FetchError("API_LIMIT", "El sitio limitó las peticiones (HTTP 429)")
        if status >= 500:
            raise FetchError("API_ERROR", f"Error HTTP {status} del sitio")
        if status >= 400:
            raise FetchError("NOT_FOUND" if status == 404 else "API_ERROR", f"HTTP {status}")

    def _policy(self, root: str) -> RobotFileParser | None:
        cached = self._robots.get(root)
        if cached and time.monotonic() - cached[0] < 3600:
            if cached[2]:
                raise FetchError("ROBOTS_UNAVAILABLE", cached[2])
            return cached[1]
        try:
            response = self.session.get(root + "/robots.txt", timeout=min(self.timeout, 6), allow_redirects=False)
            if response.status_code == 404 or response.status_code == 410:
                self._robots[root] = (time.monotonic(), None, "")
                return None
            if response.status_code != 200:
                raise FetchError("ROBOTS_UNAVAILABLE", f"No se pudo verificar robots.txt (HTTP {response.status_code})")
            parser = RobotFileParser()
            parser.parse(response.text.splitlines())
            self._robots[root] = (time.monotonic(), parser, "")
            return parser
        except requests.RequestException as exc:
            err = "No se pudo verificar robots.txt"
            self._robots[root] = (time.monotonic(), None, err)
            raise FetchError("ROBOTS_UNAVAILABLE", err) from exc
        except FetchError as exc:
            self._robots[root] = (time.monotonic(), None, str(exc))
            raise

    def get_public_html(self, url: str, allowed_hosts: set[str]) -> FetchResult:
        current = url
        for _ in range(4):
            parsed = urlparse(current)
            host = (parsed.hostname or "").lower()
            if (parsed.scheme != "https" or host not in allowed_hosts or parsed.port not in (None, 443)
                    or parsed.username is not None or parsed.password is not None):
                raise FetchError("INVALID_URL", "URL fuera de los comercios permitidos o no HTTPS")
            root = f"https://{host}"
            robot = self._policy(root)
            if robot is not None and not robot.can_fetch(USER_AGENT, current):
                raise FetchError("ROBOTS_DISALLOWED", "El sitio no permite esta ruta en robots.txt")
            elapsed = time.monotonic() - self._last.get(host, 0)
            if elapsed < 1.2:
                time.sleep(1.2 - elapsed)
            self._last[host] = time.monotonic()
            try:
                resp = self.session.get(current, timeout=self.timeout, allow_redirects=False)
            except requests.Timeout as exc:
                raise FetchError("TIMEOUT", "Tiempo agotado al consultar la tienda") from exc
            except requests.RequestException as exc:
                raise FetchError("API_ERROR", f"Error de red: {str(exc)[:120]}") from exc
            if resp.status_code in (301, 302, 303, 307, 308):
                from urllib.parse import urljoin
                current = urljoin(current, resp.headers.get("Location", ""))
                continue
            self._check_status(resp.status_code)
            if "html" not in resp.headers.get("Content-Type", "text/html").lower():
                raise FetchError("API_ERROR", "La URL no devuelve una página HTML")
            if len(resp.content) > 4_000_000:
                raise FetchError("API_ERROR", "Página demasiado grande")
            return FetchResult(resp.text, current, resp.status_code)
        raise FetchError("API_ERROR", "Demasiadas redirecciones")
