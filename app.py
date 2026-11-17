"""Radar de Precios MX 2.0 — comparador web gratuito para Streamlit."""
from pathlib import Path
import sys

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Radar de Precios MX", page_icon="🔎", layout="wide")
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REQUIRED = ["engine.py", "shops.py", "crawler.py", "retail.py", "discovery.py", "io.py", "models.py"]
missing = [f"radar/{name}" for name in REQUIRED if not (ROOT / "radar" / name).exists()]
if missing:
    st.error("Faltan archivos en la carpeta radar/ del repositorio.")
    st.code("\n".join(missing))
    st.stop()

try:
    from radar.engine import search_product
    from radar.io import read_codes, workbook_bytes, MAX_BATCH
    from radar.shops import SHOPS
    from radar.codes import classify_code
    from radar.models import Product, SearchResult, SourceStatus
except ModuleNotFoundError as exc:
    st.error("Error de importación. Verifica requirements.txt y la carpeta radar/.")
    st.code(f"Módulo que falta: {exc.name}")
    st.stop()

DESCRIPTIONS = {
    "FOUND": "Encontrado", "NOT_FOUND": "Sin coincidencia comprobada",
    "PARTIAL_RESULTS": "Consulta parcial", "MATCH_UNCERTAIN": "Coincidencia pendiente",
    "PRODUCT_FOUND_NO_PRICE": "Producto sin precio verificable", "HISTORICAL_ONLY": "Solo observaciones históricas",
    "INTERNAL_SKU": "SKU interno/no identificado", "INVALID_CODE": "Código inválido",
    "SOURCE_BLOCKED": "Bloqueo del sitio", "ROBOTS_DISALLOWED": "No permitido por robots.txt",
    "ROBOTS_UNAVAILABLE": "Política de acceso no comprobada", "SOURCE_ERROR": "Error de consulta",
    "DEPENDENCY_MISSING": "Dependencia no instalada", "TIMEOUT": "Tiempo agotado",
    "API_ERROR": "Error en servicio externo", "API_LIMIT": "Límite de consultas",
    "SKIPPED": "Omitida", "INVALID_URL": "Enlace no admitido"
}


@st.cache_data(ttl=900, show_spinner=False)
def cached_search(code, title, selected, automatic, urls, engine, metadata, historical):
    return search_product(code, label=title, stores=selected, automatic=automatic,
                          manual_urls=urls, use_crawlee=(engine == "Crawlee"),
                          metadata=metadata, observed_prices=historical)


def render_results(results, namespace):
    if not results:
        st.info("No hay consultas todavía.")
        return
    summary = []
    for result in results:
        exact = [x for x in result.offers if x.kind == "ONLINE" and x.match == "EXACT" and x.currency == "MXN"]
        provisional = [x for x in result.offers if x.kind == "ONLINE" and x.match != "EXACT"]
        summary.append({"Código": result.product.code, "Tipo": result.product.kind,
                        "Título": result.product.title or "—", "Estado": DESCRIPTIONS.get(result.status, result.status),
                        "Precios exactos": len(exact), "Por verificar": len(provisional),
                        "Mínimo confirmado MXN": min((x.price for x in exact), default=None)})
    st.subheader("Productos consultados")
    st.dataframe(pd.DataFrame(summary), hide_index=True, use_container_width=True)

    online = [o for r in results for o in r.offers if o.kind == "ONLINE"]
    confirmed = [o for o in online if o.match == "EXACT"]
    tentative = [o for o in online if o.match != "EXACT"]

    st.subheader("Precios publicados en comercios")
    if online:
        data = pd.DataFrame([{"Código": o.code, "Tienda": o.store,
                             "Producto": o.title, "Precio MXN": o.price,
                             "Nivel": "ISBN/GTIN confirmado" if o.match == "EXACT" else "Verificar coincidencia",
                             "Disponibilidad": o.availability or "No indicada", "Método": o.source,
                             "URL": o.url, "Fecha de consulta UTC": o.observed_at} for o in online])
        st.dataframe(data.sort_values("Precio MXN"), hide_index=True, use_container_width=True,
                     column_config={"URL": st.column_config.LinkColumn("URL"),
                                    "Precio MXN": st.column_config.NumberColumn("Precio MXN", format="$%.2f")})
        c1, c2, c3 = st.columns(3)
        c1.metric("Ofertas con identificador confirmado", len(confirmed))
        c2.metric("Coincidencias por verificar", len(tentative))
        c3.metric("Precio mínimo confirmado", f"${min(o.price for o in confirmed):,.2f} MXN" if confirmed else "Sin datos")
        if tentative:
            st.warning("Los resultados identificados solo por título/URL son provisionales y no entran en el mínimo confirmado.")
    else:
        st.warning("No se obtuvo ningún precio web verificable. Consulta el diagnóstico: puede ser bloqueo, falta de ficha o ausencia de datos de precio.")

    historical = [o for r in results for o in r.offers if o.kind == "HISTORICAL"]
    if historical:
        with st.expander("Precios comunitarios históricos (no son ofertas actuales)"):
            st.dataframe(pd.DataFrame([{"Código": o.code, "Comercio": o.store, "Importe MXN": o.price,
                                        "Fecha observada": o.published_at, "Fuente": o.source} for o in historical]),
                         hide_index=True, use_container_width=True)

    with st.expander("Diagnóstico por fuente", expanded=not bool(confirmed)):
        diagnostics = [{"Código": r.product.code, "Fuente": state.source, "Estado": state.code,
                        "Explicación": state.message, "URL": state.url} for r in results for state in r.statuses]
        if diagnostics:
            st.dataframe(pd.DataFrame(diagnostics), hide_index=True, use_container_width=True,
                         column_config={"URL": st.column_config.LinkColumn("URL")})

    with st.expander("Enlaces de búsqueda para revisión manual", expanded=not bool(online)):
        links = [{"Código": r.product.code, "Tienda": shop, "Búsqueda": url} for r in results for shop, url in r.search_links]
        if links:
            st.dataframe(pd.DataFrame(links), hide_index=True, use_container_width=True,
                         column_config={"Búsqueda": st.column_config.LinkColumn("Búsqueda")})

    st.download_button("Descargar Excel (productos, ofertas, errores y enlaces)",
                       data=workbook_bytes(results), file_name=f"radar_precios_mx_{namespace}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"download_{namespace}",
                       type="primary")


st.title("🔎 Radar de Precios MX")
st.caption("v2.0 · Extracción open source · Precios MXN · Sin APIs comerciales, pagos ni cuentas obligatorias")
st.info("Los precios se leen de las fichas públicas que permitan consulta automatizada. No se realiza scraping de Google, "
        "Amazon ni Mercado Libre a través de sus buscadores; esos comercios cuentan con enlaces manuales. "
        "No hay garantía de resultados en todos los sitios.")

with st.sidebar:
    st.header("Comercios")
    chosen = st.multiselect("Mostrar tiendas", [s.name for s in SHOPS],
                            default=["Porrúa", "Gandhi", "El Sótano", "Gonvill", "Sanborns", "Walmart México"])
    options = [s.name for s in SHOPS if s.search_template and s.name in chosen]
    automatic = st.multiselect("Buscar automáticamente (experimental)", options,
                               default=[s for s in ("Porrúa", "Gandhi") if s in options],
                               help="Porrúa usa la URL de búsqueda conocida; Gandhi usa una plantilla experimental. "
                                    "Para otras tiendas puedes pegar URLs exactas de fichas.")
    engine = st.selectbox("Motor de búsqueda", ["Crawlee", "HTTP ligero"], index=0,
                          help="Crawlee gestiona las páginas de resultados. HTTP ligero requiere menos recursos.")
    metadata = st.checkbox("Identificar ISBN/GTIN con catálogos abiertos", value=True)
    historical = st.checkbox("Mostrar precios comunitarios históricos", value=False)
    st.caption("Robots.txt y restricciones de acceso se respetan; no se usan proxies, CAPTCHAs ni servicios freemium.")
    st.divider()
    st.caption("Para pruebas rápidas, utiliza HTTP ligero y una sola tienda. En Streamlit Cloud las páginas pueden bloquear peticiones.")

single, batch = st.tabs(["🔎 Búsqueda individual", "📄 Importación por Excel / CSV"])
with single:
    with st.form("search_form"):
        code = st.text_input("ISBN, EAN, UPC, código interno o nombre", "9786073842839", max_chars=70)
        title = st.text_input("Descripción / modelo opcional", max_chars=200,
                              help="Útil para códigos internos: ayuda a identificar coincidencias por título, siempre provisionales.")
        urls = st.text_area("URLs exactas de productos (opcional; una por línea)", height=85,
                            placeholder="https://porrua.mx/superdeportistas-mexicanos-9786073842839.html")
        submit = st.form_submit_button("Consultar precios", type="primary")
    if submit:
        try:
            with st.spinner("Buscando fichas y verificando sus precios..."):
                st.session_state["single_results"] = [cached_search(code, title, tuple(chosen), tuple(automatic),
                                                                     tuple(urls.splitlines()[:8]), engine, metadata, historical)]
        except Exception as exc:
            st.error(f"Ocurrió un error inesperado: {type(exc).__name__}. Consulta los registros de Streamlit.")
    if "single_results" in st.session_state:
        render_results(st.session_state["single_results"], "individual")

with batch:
    st.caption("El archivo necesita una columna ISBN, EAN, UPC, Materiales, SKU o Código. "
               "Los códigos de texto y sus ceros iniciales se conservan.")
    upload = st.file_uploader("Selecciona .xlsx o .csv", type=["xlsx", "csv"])
    if upload is not None:
        try:
            codes = read_codes(upload.name, upload.getvalue(), MAX_BATCH)
            st.write(f"Códigos detectados: **{len(codes)}**. Límite de seguridad: {MAX_BATCH} por lote.")
            st.dataframe(pd.DataFrame(codes, columns=["Código", "Descripción"]), hide_index=True, use_container_width=True)
            if st.button("Consultar lista", type="primary", disabled=not bool(codes)):
                progress = st.progress(0)
                results = []
                for index, (item_code, item_title) in enumerate(codes, 1):
                    try:
                        results.append(cached_search(item_code, item_title, tuple(chosen), tuple(automatic),
                                                     (), engine, metadata, historical))
                    except Exception as exc:
                        raw, kind = classify_code(item_code)
                        results.append(SearchResult(Product(raw, kind, title=item_title), statuses=[
                            SourceStatus("Aplicación", "SOURCE_ERROR", type(exc).__name__)]))
                    progress.progress(index / len(codes))
                st.session_state["batch_results"] = results
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Error al cargar el archivo ({type(exc).__name__}).")
    if "batch_results" in st.session_state:
        render_results(st.session_state["batch_results"], "lote")

st.divider()
st.caption("Fuentes: comercios públicos seleccionados, Open Library, Open Products Facts y Open Food Facts. "
           "Los precios reflejan el momento de consulta, no son cotizaciones garantizadas.")
