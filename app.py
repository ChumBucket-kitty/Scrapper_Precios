"""Streamlit entrypoint. Desplegar desde la raíz: streamlit run app.py"""
import pandas as pd
import streamlit as st

from radar.engine import search_product
from radar.io import MAX_BATCH, read_codes, workbook_bytes
from radar.shops import SHOPS

st.set_page_config(page_title="Radar de Precios MX", page_icon="📚", layout="wide")

TEXT_STATUS = {
    "FOUND": "Precio web localizado", "HISTORICAL_ONLY": "Solo precios históricos",
    "PARTIAL_RESULTS": "Resultados parciales o fuente inaccesible",
    "PRODUCT_FOUND_NO_PRICE": "Producto identificado; sin precio web",
    "NOT_FOUND": "Sin coincidencia en las fuentes consultadas",
    "INTERNAL_SKU": "Código interno sin correspondencia confirmada",
    "INVALID_CODE": "Código inválido", "MATCH_UNCERTAIN": "Coincidencia por confirmar",
    "SOURCE_BLOCKED": "Acceso rechazado", "ROBOTS_DISALLOWED": "Consulta no permitida por la tienda",
    "ROBOTS_UNAVAILABLE": "No se pudo verificar política del sitio",
    "API_LIMIT": "Consulta limitada por fuente", "API_ERROR": "Error de consulta", "TIMEOUT": "Tiempo agotado",
    "SKIPPED": "No se consultó", "INVALID_URL": "URL no admitida",
}


@st.cache_data(ttl=1800, show_spinner=False)
def cached_search(code: str, label: str, stores: tuple[str, ...], manual: tuple[str, ...],
                  auto_porrua: bool, low_volume: bool, open_prices: bool):
    return search_product(code, label=label, stores=stores, manual_urls=manual,
                          auto_porrua=auto_porrua, low_volume=low_volume,
                          open_prices=open_prices)


def show_results(results):
    if not results:
        st.info("Todavía no hay consultas.")
        return
    rows = []
    for r in results:
        web = [o for o in r.offers if o.kind == "ONLINE" and o.currency == "MXN"]
        rows.append({"Código": r.product.code, "Tipo": r.product.kind, "Producto": r.product.title or "—",
                     "Estado": TEXT_STATUS.get(r.status, r.status), "Ofertas web": len(web),
                     "Menor precio web MXN": min((o.price for o in web), default=None),
                     "Fuente catálogo": r.product.source or "—"})
    st.subheader("Resumen")
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    web_offers = [o for r in results for o in r.offers if o.kind == "ONLINE"]
    observations = [o for r in results for o in r.offers if o.kind == "HISTORICAL"]
    st.subheader("Ofertas web verificadas o aproximadas")
    if web_offers:
        data = pd.DataFrame([{"Código": o.code, "Tienda": o.store, "Producto": o.title,
                              "Precio MXN": o.price, "Coincidencia": o.match,
                              "Disponibilidad": o.availability, "Enlace": o.url,
                              "Consultado UTC": o.observed_at} for o in web_offers])
        st.dataframe(data.sort_values("Precio MXN"), hide_index=True, use_container_width=True,
                     column_config={"Enlace": st.column_config.LinkColumn("Enlace")})
        if any(o.match != "EXACT" for o in web_offers):
            st.warning("Las filas URL_ONLY se verificaron solo por la URL, no por un identificador estructurado. Revísalas antes de comparar.")
    else:
        st.info("No se pudieron verificar precios web actuales en las fuentes disponibles. Los enlaces de búsqueda están abajo.")

    if observations:
        st.subheader("Registros históricos comunitarios")
        st.caption("Open Prices: precios observados anteriormente, NO necesariamente ofertas vigentes. Pueden ser tiendas físicas.")
        st.dataframe(pd.DataFrame([{"Código": o.code, "Comercio": o.store, "Precio observado MXN": o.price,
                                    "Fecha observación": o.published_at, "Fuente": o.source} for o in observations]),
                     hide_index=True, use_container_width=True)

    with st.expander("Diagnóstico por fuente", expanded=not web_offers):
        errors = [{"Código": r.product.code, "Fuente": s.source,
                   "Estado": TEXT_STATUS.get(s.code, s.code), "Detalle": s.message,
                   "URL": s.url} for r in results for s in r.statuses]
        if errors:
            st.dataframe(pd.DataFrame(errors), hide_index=True, use_container_width=True)

    with st.expander("Enlaces para revisar tiendas", expanded=not web_offers):
        links = [{"Código": r.product.code, "Tienda": name, "Abrir búsqueda": url}
                 for r in results for name, url in r.search_links]
        if links:
            st.dataframe(pd.DataFrame(links), hide_index=True, use_container_width=True,
                         column_config={"Abrir búsqueda": st.column_config.LinkColumn("Abrir búsqueda")})
        else:
            st.info("Selecciona tiendas en el panel lateral para generar enlaces.")

    st.download_button("⬇️ Descargar resultados XLSX", data=workbook_bytes(results),
                       file_name="radar_precios_mx.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       type="primary")


st.title("📚 Radar de Precios MX")
st.caption("Búsqueda por ISBN, EAN, UPC o SKU · Sin servicios de pago, créditos de prueba ni claves API")
st.info("No existe una API abierta que proporcione todos los precios de Google Shopping, Amazon y Mercado Libre. "
        "Esta versión consulta fuentes públicas gratuitas, intenta recuperar ofertas accesibles de tiendas permitidas "
        "y genera enlaces de búsqueda cuando no es posible obtener un precio. Nunca inventa resultados.")

with st.sidebar:
    st.header("Fuentes y tiendas")
    default_shops = ["Porrúa", "Gandhi", "El Sótano", "Amazon México", "Mercado Libre", "Walmart México"]
    selected = st.multiselect("Tiendas para generar enlaces", [s.name for s in SHOPS], default=default_shops)
    st.caption("Los enlaces para Amazon y Mercado Libre son de búsqueda manual: no son APIs de precios.")
    use_openprices = st.checkbox("Open Prices (observaciones históricas)", value=True)
    auto_porrua = st.checkbox("Intentar búsqueda automática en Porrúa", value=False,
                              help="Solo ISBN; respeta robots.txt. Si hay 403, informa del bloqueo sin intentar eludirlo.")
    st.caption("Metadatos gratuitos: Open Library (ISBN, búsquedas individuales), Open Products Facts y Open Food Facts (EAN/UPC).")
    st.divider()
    st.caption("Respeta los límites de las fuentes y utiliza este comparador de forma moderada.")

left, right = st.tabs(["🔎 Consulta individual", "📄 Consulta por archivo"])
with left:
    with st.form("single"):
        code = st.text_input("ISBN / EAN / UPC / SKU", value="9786073842839", max_chars=70)
        label = st.text_input("Descripción opcional (útil para SKUs internos)", max_chars=200)
        urls = st.text_area("URLs exactas de producto, opcionales (una por línea)", height=90,
                            placeholder="https://porrua.mx/superdeportistas-mexicanos-9786073842839.html")
        submitted = st.form_submit_button("Buscar", type="primary")
    if submitted:
        try:
            with st.spinner("Consultando fuentes públicas..."):
                st.session_state["last_results"] = [cached_search(code, label, tuple(selected),
                                        tuple(urls.splitlines()[:8]), auto_porrua, True, use_openprices)]
        except Exception as exc:
            st.error(f"Error inesperado controlado: {type(exc).__name__}. Revisa el diagnóstico o el registro de Streamlit.")
    if "last_results" in st.session_state:
        show_results(st.session_state["last_results"])

with right:
    st.caption("Excel o CSV con columna ISBN, EAN, UPC, SKU, Materiales o Código. Se conserva el identificador como texto.")
    file = st.file_uploader("Archivo", type=["xlsx", "csv"], key="batch_file")
    if file:
        try:
            entries = read_codes(file.name, file.getvalue(), MAX_BATCH)
            st.write(f"Códigos únicos listos: **{len(entries)}** · límite prudente: {MAX_BATCH} por ejecución")
            st.dataframe(pd.DataFrame(entries, columns=["Código", "Descripción opcional"]), hide_index=True)
            if st.button("Consultar archivo", type="primary", disabled=not entries):
                results = []
                bar = st.progress(0)
                for idx, (item_code, item_title) in enumerate(entries, 1):
                    try:
                        r = cached_search(item_code, item_title, tuple(selected), (), auto_porrua, False, use_openprices)
                        results.append(r)
                    except Exception as exc:
                        from radar.codes import classify_code
                        from radar.models import Product, SearchResult, SourceStatus
                        cleaned, kind = classify_code(item_code)
                        results.append(SearchResult(Product(cleaned, kind, title=item_title),
                                        statuses=[SourceStatus("Aplicación", "API_ERROR", type(exc).__name__)]))
                    bar.progress(idx / len(entries))
                st.session_state["batch_results"] = results
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"No se pudo leer el archivo ({type(exc).__name__}). Comprueba el formato.")
    if "batch_results" in st.session_state:
        show_results(st.session_state["batch_results"])

st.divider()
st.caption("Fuentes: Open Library, Open Products Facts, Open Food Facts y Open Prices (datos abiertos sujetos a sus licencias y políticas). "
           "Un precio histórico no se mezcla con una oferta web actual. Resultados sujetos a disponibilidad de las fuentes.")
