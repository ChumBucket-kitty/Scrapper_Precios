"""Validación estricta de identificadores; nunca se convierten a números."""
import re


def clean_code(value: str) -> str:
    """Quita separadores solo en ISBN/códigos numéricos; preserva SKUs."""
    original = str(value or "").strip().upper()
    if re.fullmatch(r"[0-9X\s-]+", original):
        return re.sub(r"[\s-]", "", original)
    return original


def ean_valid(digits: str) -> bool:
    if not digits.isdigit() or len(digits) not in (8, 12, 13):
        return False
    # EAN-8, UPC-A y EAN-13 comparten el algoritmo módulo 10.
    total = sum(int(x) * (3 if i % 2 == 0 else 1)
                for i, x in enumerate(reversed(digits[:-1])))
    return (10 - total % 10) % 10 == int(digits[-1])


def isbn10_valid(code: str) -> bool:
    if not re.fullmatch(r"\d{9}[\dX]", code):
        return False
    return sum((10 - i) * (10 if d == "X" else int(d)) for i, d in enumerate(code)) % 11 == 0


def classify_code(value: str) -> tuple[str, str]:
    code = clean_code(value)
    if not code or len(code) > 70 or not re.fullmatch(r"[A-Z0-9._/\- ]+", code):
        return code, "INVALID_CODE"
    if len(code) == 10 and re.fullmatch(r"\d{9}[\dX]", code):
        return code, "ISBN10" if isbn10_valid(code) else "INVALID_CODE"
    if code.isdigit() and len(code) in (8, 12, 13):
        if not ean_valid(code):
            return code, "INVALID_CODE"
        if len(code) == 13 and code.startswith(("978", "979")):
            return code, "ISBN13"
        return code, {8: "EAN8", 12: "UPC", 13: "EAN13"}[len(code)]
    # SKU interno: no inferimos ISBN ni buscador comercial por validación de longitud.
    return code, "INTERNAL_SKU"
