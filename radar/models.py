"""Objetos sencillos que comparten los conectores y la interfaz."""
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class SourceStatus:
    source: str
    code: str
    message: str
    url: str = ""
    checked_at: str = field(default_factory=now_utc)


@dataclass
class Product:
    code: str
    kind: str
    title: str = ""
    brand: str = ""
    publisher: str = ""
    image_url: str = ""
    source: str = ""
    status: str = "NOT_FOUND"


@dataclass
class Offer:
    code: str
    store: str
    title: str
    price: float
    currency: str
    url: str
    source: str
    match: str
    kind: str = "ONLINE"
    observed_at: str = field(default_factory=now_utc)
    published_at: str = ""
    availability: str = ""
    evidence: str = ""


@dataclass
class SearchResult:
    product: Product
    offers: list[Offer] = field(default_factory=list)
    statuses: list[SourceStatus] = field(default_factory=list)
    search_links: list[tuple[str, str]] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.product.kind == "INVALID_CODE":
            return "INVALID_CODE"
        if self.offers:
            if all(o.kind == "HISTORICAL" for o in self.offers):
                return "HISTORICAL_ONLY"
            if any(o.match != "EXACT" for o in self.offers):
                return "MATCH_UNCERTAIN" if not any(o.match == "EXACT" for o in self.offers) else "PARTIAL_RESULTS"
            return "FOUND" if all(s.code in ("FOUND", "NOT_FOUND", "SKIPPED") for s in self.statuses) else "PARTIAL_RESULTS"
        error_codes = {"SOURCE_BLOCKED", "API_ERROR", "API_LIMIT", "TIMEOUT", "ROBOTS_DISALLOWED", "ROBOTS_UNAVAILABLE"}
        if any(s.code in error_codes for s in self.statuses):
            return "PARTIAL_RESULTS"
        if self.product.status == "FOUND":
            return "PRODUCT_FOUND_NO_PRICE"
        if self.product.kind == "INTERNAL_SKU":
            return "INTERNAL_SKU"
        return "NOT_FOUND"

    def as_dict(self) -> dict:
        return {"product": asdict(self.product), "offers": [asdict(o) for o in self.offers],
                "statuses": [asdict(s) for s in self.statuses], "search_links": self.search_links,
                "status": self.status}
