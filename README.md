# Radar de Precios MX 2.0

Comparador de precios **gratuito, de código abierto y sin claves API** desarrollado con Python y Streamlit. Busca fichas de tiendas mexicanas y extrae los precios públicos declarados en JSON-LD Schema.org, microdatos o metatags de precio. No contrata servicios de terceros, no utiliza APIs de prueba ni usa proxies para eludir restricciones.

> **Limitación esencial:** gratuito no significa acceso garantizado. Algunas tiendas bloquean solicitudes automáticas, publican precios con JavaScript, restringen `robots.txt` o cambian sus sitios. La app informa del problema, nunca inventa precios. No se garantiza disponibilidad de ningún comercio.

## Funciones

- ISBN-10, ISBN-13, EAN-8, EAN-13, UPC y códigos internos.
- Identificación bibliográfica de ISBN y consulta abierta de algunos códigos EAN/UPC.
- Dos rutas de descubrimiento automático: **Porrúa**, URL de búsqueda conocida, y **Gandhi**, plantilla experimental. Cada tienda puede cambiar sus URLs; ningún enlace se presenta como API oficial.
- Fichas directas de cualquiera de los 12 comercios configurados (pegar URL del producto).
- **Crawlee HTTP** para consultar páginas de búsqueda; motor HTTP ligero como alternativa. **Extruct** para datos estructurados.
- Validación de coincidencias exactas por ISBN/GTIN/SKU, coincidencias provisionales por URL y por título (separadas en la interfaz).
- Diagnóstico por fuente con estados `FOUND`, `NOT_FOUND`, `SOURCE_BLOCKED`, `ROBOTS_DISALLOWED`, `TIMEOUT`, `MATCH_UNCERTAIN`, `PRODUCT_FOUND_NO_PRICE`, etc.
- Excel/CSV por lotes, exportación Excel con cuatro hojas, códigos guardados como texto.
- Caché de consultas de 15 minutos, máximo tres fichas por tienda por código, límite conservador para lotes.

## Despliegue en Streamlit Community Cloud

1. Crea un repositorio GitHub y coloca **todo el contenido de esta carpeta en la raíz**.
2. Desde [share.streamlit.io](https://share.streamlit.io/) selecciona tu repositorio y `app.py`.
3. Usa **Python 3.12** en la configuración avanzada (recomendado).
4. No agregues ninguna API key. `requirements.txt` instala las dependencias y el paquete local `radar`.
5. Para un despliegue con menos consumo, elige **HTTP ligero** en el panel lateral. Crawlee requiere más recursos.

## Ejecución local

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Pruebas de regresión:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Dónde están los conectores

- `radar/shops.py`: comercios, dominios, enlaces manuales y URL de búsqueda automáticas.
- `radar/discovery.py`: encuentra URLs candidatas en resultados de búsqueda.
- `radar/crawler.py`: Crawlee, limitado a una página por tienda y con `robots.txt`.
- `radar/http.py`: cliente HTTP prudente, valida HTTPS, dominios, robots y redirecciones.
- `radar/retail.py`: extractor de precios (Extruct y metatags) y comprobación de identidad.
- `radar/engine.py`: coordinador con control de errores independiente por fuente.
- `radar/catalog.py`: datos bibliográficos, **no** precios.
- `radar/openprices.py`: observaciones **históricas**, opcionales y separadas de precios web actuales.
- `radar/io.py`: entrada y salida Excel/CSV.

## Cómo añadir una tienda

1. Añade un `Shop(...)` a `radar/shops.py` con su dominio y, **solo si has verificado el patrón de búsqueda**, `search_template`.
2. Comprueba que el sitio permite acceso automático a la ruta y que su HTML contiene fichas identificables.
3. Valida su página de producto mediante un ejemplo real y agrega una prueba a `tests/`. Si usa JavaScript sin datos estructurados, necesitarás un conector autorizado específico: no se simula una oferta.

## Códigos y calidad de resultados

- `EXACT`: ISBN, EAN o SKU explícito e idéntico en la ficha del producto.
- `URL_ONLY`: código presente en la ruta de la ficha, pero no confirmado por metadatos.
- `TITLE_MATCH`: título similar, sin identificador confirmado.

Solo los `EXACT` entran en el precio mínimo **confirmado**. Si un código parece interno, se etiqueta `INTERNAL_SKU` hasta que haya evidencia de producto y precio. Si un sitio niega acceso, se informa `SOURCE_BLOCKED` y no `NOT_FOUND`. Un resultado provisional se debe verificar manualmente.

## Alcance y advertencias

No se consultan precios mediante Google Shopping, Amazon ni Mercado Libre automáticamente, ya que no hay acceso gratuito público y garantizado a sus APIs generales de competencia. Sus enlaces sirven para revisión manual. No incluye navegador con Playwright ni elusión de CAPTCHA por defecto, para reducir requisitos en Streamlit Cloud. Algunas tiendas pueden tener condiciones adicionales que impidan la automatización: respétalas.

**Licencia:** MIT (código de este repositorio); los datos y páginas de terceros mantienen sus condiciones originales. El proyecto no almacena datos permanentes ni registra un histórico privado por defecto.
