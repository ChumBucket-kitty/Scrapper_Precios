# Radar de Precios MX 📚

**Aplicación Streamlit gratis y sin cuentas, claves de API, créditos promocionales o suscripciones.** Compara productos por ISBN/EAN/UPC/SKU, conserva códigos largos como texto y exporta a Excel. Orientada a México.

## Qué funciona

- Identificación de ISBN **individuales** por Open Library (datos bibliográficos, no precios).
- EAN/UPC mediante Open Products Facts y Open Food Facts (catálogos abiertos, cobertura desigual).
- Precios comunitarios **históricos** por Open Prices, cuando existan registros en MXN. **No representan precios actuales de competencia**.
- Extracción de precios de **fichas HTML públicas** mediante `Product` + `Offer` en JSON-LD, siempre que una tienda permita la consulta y publique `priceCurrency: MXN`, y que el código coincida.
- URLs exactas aportadas por el usuario (solo dominios de tiendas configuradas), validadas antes de leer.
- Conector experimental para búsqueda automatizada de **Porrúa** por ISBN; si hay bloqueo/robots, reporta el error. No esquiva protecciones.
- Enlaces para **búsqueda manual** en Porrúa, Gandhi, El Sótano, Gonvill, Sanborns, Liverpool, Walmart MX, Office Depot, Coppel, Cyberpuerta, Amazon MX y Mercado Libre.
- Archivo CSV/XLSX de hasta 30 códigos por consulta, resumen, ofertas, estados y enlaces exportables en 4 hojas XLSX.
- Respuestas de error por fuente; caché de consultas 30 minutos; ISBN, UPC, EAN con checksum.

## Limitaciones esenciales

**No existe una API gratuita, pública y universal que ofrezca los precios actuales de todas estas tiendas.** Google Shopping, Amazon, Mercado Libre y las grandes tiendas requieren distintos permisos, pueden cobrar por herramientas de terceros o bloquear robots. Por ello **esta app no simula precios**, ni presenta el enlace de búsqueda como una oferta capturada. La ausencia de resultados no prueba que un artículo no se venda.

- Las rutas de búsqueda de terceros son **enlaces para el usuario**, no endpoints API. Solo el conector experimental de Porrúa intenta automáticamente la página de resultados.
- Los bloqueos HTTP 403/429, restricciones de robots o páginas dinámicas se comunican claramente.
- No utiliza Google Books, SerpApi, Serper, UPCitemdb, proxies, CAPTCHA solvers ni servicios que solo ofrecen pruebas o cuotas freemium.
- Open Library limita la frecuencia y no debe actuar como backend comercial masivo: solo se consulta para ISBN **individuales**; en lote está desactivada. Consultar [su política](https://openlibrary.org/developers/api) antes de un uso comercial frecuente.
- Datos Open Food Facts / Open Products Facts / Open Prices están sujetos a licencias **ODbL** (atribución y eventual reciprocidad si redistribuyes bases derivadas); consultar términos al reutilizar o exportar.
- Muchos comercios no exponen JSON-LD con GTIN ni permiten leer sus páginas desde Streamlit Community Cloud. El estado `PARTIAL_RESULTS` es una posibilidad normal, no un fallo del despliegue.
- El modo de lectura pública no usa cookies de sesión ni inicia sesión en tiendas, y no promete verificar existencias en tiempo real.
- **SKU interno:** sin un catálogo de equivalencias no se asume que sea un EAN/ISBN. Puedes proporcionar descripción y buscarla manualmente.
- Para resultados web de coincidencia por URL únicamente se marca `URL_ONLY` y se requiere revisión humana.

## Desplegar en Streamlit Community Cloud

1. Crea un repositorio en GitHub, por ejemplo `radar-precios-mx`.
2. **Sube el contenido de esta carpeta a la raíz del repositorio** (es decir, `app.py` y `requirements.txt` deben quedar en el nivel superior, no dentro de otra carpeta).
3. En <https://share.streamlit.io/> crea una aplicación usando ese repositorio, rama `main` y archivo principal **`app.py`**. Usa Python **3.12** si se ofrece.
4. Haz clic en **Deploy**. **No hay que configurar Secrets**.

### Ejecutar localmente

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

### Ejecutar pruebas

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Entradas

- **Consulta individual:** introduce código, título opcional, y hasta 8 URLs exactas de ficha para intentar extraer el precio (solo dominios configurados).
- **Excel/CSV:** columna `ISBN`, `EAN`, `UPC`, `SKU`, `Materiales` o `Código`; la descripción puede estar en `Descripción`, `Título` o `Nombre`. Se leen hasta 30 códigos únicos por ejecución.
- Los identificadores de 13 dígitos deben estar guardados **como texto** en Excel; Excel puede haber redondeado los que se guardaron previamente como números grandes. No es posible reparar automáticamente un código ya alterado.

## Estructura

```text
radar-precios-mx/
├── app.py                        # Interfaz Streamlit
├── radar/
│   ├── __init__.py
│   ├── models.py                 # Datos y estados
│   ├── codes.py                  # ISBN/EAN/UPC/SKU
│   ├── http.py                   # Respeto robots.txt, límites y errores
│   ├── catalog.py                # Open Library / Open * Facts
│   ├── openprices.py             # Precios comunitarios históricos
│   ├── shops.py                  # Comercios y enlaces manuales
│   ├── retail.py                 # JSON-LD Producto/Oferta
│   ├── engine.py                 # Consulta y unificación
│   └── io.py                     # Importación y exportación XLSX/CSV
├── tests/                        # Pruebas automáticas offline
├── .streamlit/config.toml
├── .github/workflows/tests.yml
├── requirements.txt
├── requirements-dev.txt
├── .gitignore
└── LICENSE
```

## Códigos de estado

| Código | Interpretación |
|---|---|
| `FOUND` | Oferta online extraída y validada |
| `HISTORICAL_ONLY` | Solo precios históricos comunitarios |
| `PRODUCT_FOUND_NO_PRICE` | Producto identificado, sin oferta web validada |
| `NOT_FOUND` | Fuentes respondieron sin coincidencias; no implica inexistencia comercial |
| `INTERNAL_SKU` | Código no identificable como EAN/UPC/ISBN público |
| `INVALID_CODE` | Identificador mal formado o checksum incorrecto |
| `MATCH_UNCERTAIN` | Código solo en URL o coincidencia dudosa |
| `PARTIAL_RESULTS` | Falla de al menos una fuente relevante / coincidencias incompletas |
| `SOURCE_BLOCKED` | Tienda rechaza acceso (401/403) |
| `ROBOTS_DISALLOWED` | robots.txt prohíbe la ruta |
| `ROBOTS_UNAVAILABLE` | No se pudo verificar política, lectura omitida |
| `API_LIMIT` | Fuente aplica limitación 429 |
| `TIMEOUT` | Solicitud excedió tiempo |
| `API_ERROR` | Red, formato o servicio inesperado |
| `INVALID_URL` | Ficha fuera de dominios admitidos |

## Ampliar fuentes

Para agregar una tienda: añadirla a `SHOPS` en `radar/shops.py`, implementar un extractor propio independiente en `radar/retail.py` o nuevo módulo, y registrar sus estados en `radar/engine.py`. Nunca atribuir un precio sin confirmar producto, moneda, URL y fecha. Revisar robots y términos del dominio; evitar intentos de evadir bloqueos.

## Fuentes y atribución

- [Open Library API](https://openlibrary.org/developers/api) — metadatos de libros, consultas esporádicas.
- [Open Products Facts](https://world.openproductsfacts.org/) y [Open Food Facts API](https://openfoodfacts.github.io/documentation/docs/Product-Opener/api/) — datos abiertos de productos, ODbL.
- [Open Prices](https://prices.openfoodfacts.org/api/docs) — precios comunitarios históricos, ODbL.
- [Streamlit Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) — despliegue gratuito con sus restricciones actuales.

Código MIT; **las licencias de las fuentes de datos siguen siendo las de cada proyecto**.
