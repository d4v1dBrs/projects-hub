"""App FastAPI: web personal (`/`) + terminal de bonos (`/bonos`, HTMX SSR).

`run.py` la levanta vía uvicorn. Integra:
  - CatalogRepository (SQLite) vía Depends(get_repo).
  - Motor financiero (pricing core Strategy/Protocol) vía GenerateMonitorReport.
  - Puente CPU: `await asyncio.to_thread(use_case.execute, ...)` corre el pricing
    pesado fuera del event loop; `_bei_loop` hace lo mismo con compute_bei_tables.
  - lifespan: loops supervisados (`refresh`, `bei`, `history` si hay consumidor)
    + `_startup_reconcile`
    (1×) — ver `supervisor.py`.
  - ResilientClient + ProviderHub (async) en app.state: fuente live + piso Data912.

Routers en apps/web/routers/, templates Jinja+HTMX en apps/web/templates/.
Con MONITOR_DISABLE_LOOPS=1 los loops no arrancan (smoke tests / import limpio).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from apps.web.deps_auth import RequiresLoginException, get_current_user
from apps.web.deps import get_bondterminal, get_repo, get_state
from apps.web.routers import bonds, header, panels, personal, stream
from apps.web.routers.panels_schema import HISTORY_TYPES
from apps.web.state import AppState
from apps.web.supervisor import supervise
from config.settings import settings
from core.domain.instrument_groups import (
    BOPREALES, CER, DOLAR_LINKED, DUAL_TAMAR,
    PROVINCIALES, SOBERANOS, TAMAR, TASA_FIJA,
)
from core.infrastructure.async_http import ResilientClient
from core.infrastructure.provider_hub import ProviderHub

logger = logging.getLogger(__name__)

_ALL_TYPES = [*SOBERANOS, *BOPREALES, *TASA_FIJA, *CER, *DOLAR_LINKED, *TAMAR,
              *DUAL_TAMAR, *PROVINCIALES]



async def _refresh_loop(app: FastAPI) -> None:
    """Ingesta async: `hub.refresh_all()` trae la fuente activa (BYMA open por default,
    endpoints en paralelo, httpx + circuit breaker + pool) y le mergea el piso Data912;
    el motor de pricing corre off-loop vía `to_thread` leyendo el snapshot ya
    materializado. El pricing tarda ~0.1-0.3s por ciclo; el BEI (más pesado) va en
    `_bei_loop` para no espaciar el push SSE de los paneles."""
    from core.infrastructure.provider_hub import HubMarketDataProvider
    from core.use_cases.generate_report import GenerateMonitorReport

    repo = get_repo()
    provider = HubMarketDataProvider(app.state.hub, app.state.provider)
    first = True
    while True:
        if not first:
            await asyncio.sleep(settings.refresh_sec)
        first = False
        try:
            _t0 = time.perf_counter()
            await app.state.hub.refresh_all()  # fuente live activa (BYMA/Data912), async
            if hasattr(app.state.indices, "prefetch"):
                await app.state.indices.prefetch(app.state.client)
            if hasattr(app.state.fx, "prefetch"):
                await app.state.fx.prefetch(app.state.client)
            _t_ingest = time.perf_counter()
            use_case = GenerateMonitorReport(repo, provider,
                                             indices=app.state.indices, fx=app.state.fx,
                                             history_types=HISTORY_TYPES,
                                             cached_history_only=True)
            metrics = await asyncio.to_thread(use_case.execute, _ALL_TYPES)
            await app.state.app_state.update(metrics)   # dispara el SSE `refresh`
            _total = time.perf_counter() - _t0
            # Observabilidad del tiempo de ciclo: si un ciclo supera el intervalo de
            # refresh, los `refresh` del SSE se espacian (los paneles dejan de sentirse
            # "en vivo"). Se grita a WARNING para que quede en el log durable; en
            # operación normal (ciclo < intervalo) va a INFO.
            _lvl = logging.WARNING if _total > settings.refresh_sec else logging.INFO
            logger.log(
                _lvl,
                "refresh cycle: ingest=%.2fs price=%.2fs total=%.2fs (%d instr)",
                _t_ingest - _t0, time.perf_counter() - _t_ingest, _total, len(metrics),
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.exception("refresh loop iteration failed")
            # Observabilidad (O1): registrar el fallo para que el header lo muestre.
            # La app sigue sirviendo el último snapshot bueno (stale), pero visible.
            await app.state.app_state.record_error(f"{type(e).__name__}: {e}")


async def _wait_for_first_refresh(app: FastAPI) -> None:
    state = app.state.app_state
    while not state.last_refresh:
        await state.wait_for_change(state.revision)


async def _history_loop(app: FastAPI) -> None:
    """Warm optional returns after prices are published; never delay a refresh."""
    from core.use_cases.generate_report import GenerateMonitorReport

    state = app.state.app_state
    use_case = GenerateMonitorReport(get_repo(), app.state.provider)
    await _wait_for_first_refresh(app)
    while True:
        tickers = {
            m.snapshot.instrument.ticker for m in state.metrics()
            if m.snapshot.instrument.instrument_type in HISTORY_TYPES
        }
        for ticker in sorted(tickers):
            try:
                # One ticker per await also bounds work still running at shutdown.
                await asyncio.to_thread(use_case.prefetch_history, ticker)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("History warmup failed for %s", ticker, exc_info=True)
        # Bases are cached per day; revisit for new instruments and date rollover.
        await asyncio.sleep(300)



def _catalog_health_report(repo) -> dict:
    """Reporte publicable de la salud del catálogo, leído del repo ya cargado.

    `orphans` = bonos con un `instrument_type` que no pertenece a ningún grupo de
    `instrument_groups`: se cargan, guardan cashflows y acumulan precio, pero NINGÚN
    panel los muestra ni los precia (todo el read-path filtra por igualdad exacta).
    `defaulted` = bonos cuyo tipo se ASUMIÓ del default de una hoja ambigua (una ON
    sin `tipo` se precia como hard-dollar aunque sea dollar-linked: otra moneda de
    pago). `seed_error` = la siembra de bootstrap falló y el catálogo quedó vacío."""
    health = getattr(repo, "type_health", None) or {}
    return {
        "instruments": len(repo.get_all_instruments()),
        "orphans": [e.get("ticker", "") for e in health.get("orphans", ())],
        "defaulted": [e.get("ticker", "") for e in health.get("defaulted", ())],
        "seed_error": getattr(repo, "seed_error", None),
    }


async def _publish_catalog_health(app: FastAPI, repo) -> dict:
    """Cablea la salud del catálogo a `AppState` → `/api/health` (bloque `catalog`)
    y, si la siembra falló, al badge del header vía `record_error`.

    Este es el consumidor que faltaba: `CatalogRepository.type_health` se construyó
    para que el arranque lo publicara, pero sus únicos lectores eran los tests. Una
    señal sin consumidor es exactamente el patrón que dejó el bug original invisible
    durante meses — las filas huérfanas volvían a serlo en silencio.

    El catálogo VACÍO por una semilla ilegible sí es un error de operación (no hay
    nada que servir): va a `record_error` para que el badge lo muestre, y `AppState`
    lo retiene aparte para que el siguiente refresh 'exitoso' de 0 instrumentos no lo
    borre. Los huérfanos NO degradan el semáforo: son crónicos y lo dejarían rojo
    para siempre (ver `AppState.status`)."""
    rep = _catalog_health_report(repo)
    state = app.state.app_state
    state.set_catalog_health(**rep)
    if rep["seed_error"]:
        await state.record_error(
            f"catálogo vacío: la siembra desde el Excel falló ({rep['seed_error']})")
    if rep["orphans"]:
        logger.warning(
            "catálogo: %d bono(s) invisibles en todos los paneles (tipo huérfano) — "
            "publicado en /api/health: %s", len(rep["orphans"]),
            " ".join(rep["orphans"][:20]))
    return rep


def _reconcile_catalog(hub) -> int:
    """Sync (corre en to_thread): completa patas de moneda de soberanos + da de
    alta las acciones (solo-ticker, categoría Acciones).
    Devuelve cuántas filas se agregaron/modificaron."""
    from apps.web.instruments_abm import backfill_soberano_ccy_legs, register_stocks
    from core.domain.instrument_groups import PANEL_LIDER

    snapshot, sources = hub.snapshot(), hub.sources()
    legs = backfill_soberano_ccy_legs(set(snapshot.keys()))
    stock_syms = [s for s, src in sources.items() if src == "stocks"] + list(PANEL_LIDER)
    stocks = register_stocks(stock_syms)
    return len(legs) + len(stocks)



def _backfill_legs() -> int:
    """Completa patas cotizantes faltantes (soberanos + ON) por grupo/ISIN del universo
    BYMA (sync, corre en to_thread). Devuelve cuántas patas se agregaron."""
    from apps.web.instruments_abm import backfill_legs_from_universe
    try:
        res = backfill_legs_from_universe()
        return sum(len(r.get("added", [])) for r in res)
    except Exception:
        logger.exception("backfill de patas (universo) falló")
        return 0


async def _startup_reconcile(app: FastAPI) -> None:
    """Al arranque: usa el primer snapshot del refresh y reconcilia el catálogo —
    completa las patas de moneda (MEP/CABLE) de soberanos ya cargados (mismo bono)
    y da de alta las acciones como categoría 'Acciones'. Los tickers de renta fija
    genuinamente nuevos quedan para el alta manual (sidebar del ABM)."""
    from core.infrastructure.byma.catalog_enrich import (
        enrich_ficha_meta, enrich_isin_from_byma, enrich_isin_from_ficha,
    )
    from core.infrastructure.byma.universe import ingest_byma_catalog

    try:
        await _wait_for_first_refresh(app)
        n = await asyncio.to_thread(_reconcile_catalog, app.state.hub)
        # ISIN + metadata BYMA (emisor/tipo): primero del seed (instantáneo), luego
        # ficha en vivo para los que quedaron sin ISIN (autoritativo, AL30/DICP/etc).
        enriched = await asyncio.to_thread(enrich_isin_from_byma)
        enriched += await asyncio.to_thread(enrich_isin_from_ficha)
        # Campos ricos de la ficha (ley/moneda/amortización/interés/montos) → para
        # el ABM y el catálogo de productos. Idempotente, best-effort.
        await asyncio.to_thread(enrich_ficha_meta)
        # Universo BYMA navegable (tabla byma_catalog) para el buscador del ABM.
        universe = await asyncio.to_thread(ingest_byma_catalog)
        # Completar patas cotizantes faltantes (soberanos + ON) deduciendo el grupo
        # por el universo BYMA (mismo ISIN). Idempotente. Requiere byma_catalog cargado.
        legs = await asyncio.to_thread(_backfill_legs)
        if n or enriched or legs:
            # El reload va en su PROPIO try: es la carga del catálogo, no una
            # tarea de enriquecimiento best-effort. Si falla, los paneles siguen
            # sirviendo el cache viejo (sin las patas/ISIN recién escritos) y hasta
            # ahora eso moría en el `except` global de abajo, que sólo loguea —
            # el fallo de carga del repo no llegaba a NINGUNA superficie.
            try:
                get_repo().reload()
            except Exception as e:  # noqa: BLE001
                logger.exception("reload del catálogo falló tras el reconcile")
                await app.state.app_state.record_error(
                    f"catálogo: el reload falló — {type(e).__name__}: {e}")
        # Republicar: el reconcile pudo dar de alta filas (acciones, ONs, patas) y
        # con ellas tipos huérfanos nuevos. Corre igual si el reload falló: entonces
        # el reporte describe el cache que efectivamente se está sirviendo.
        await _publish_catalog_health(app, get_repo())
        logger.info("Startup: catálogo +%d filas, %d ISIN, %d especies BYMA, +%d patas.",
                    n, enriched, universe, legs)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("startup reconcile failed")




async def _bei_loop(app: FastAPI) -> None:
    """Loop dedicado de BEI (pesado: bootstrap + NSS fits). Corre 1× al arranque
    y luego cada bei_refresh_sec. Reemplaza el daemon _bei_refresh_loop."""
    from apps.cli.bei import compute_bei_tables
    from core.infrastructure.provider_hub import HubMarketDataProvider
    from core.use_cases.generate_report import GenerateMonitorReport

    repo = get_repo()
    bcra = app.state.indices
    provider = HubMarketDataProvider(app.state.hub, app.state.provider)
    await _wait_for_first_refresh(app)
    first = True
    while True:
        if not first:
            await asyncio.sleep(settings.bei_refresh_sec)
        first = False
        try:
            # The refresh loop owns market ingestion, including the shared indices/FX.
            use_case = GenerateMonitorReport(repo, provider,
                                             indices=app.state.indices, fx=app.state.fx,
                                             history_types=())
            tables = await asyncio.to_thread(
                compute_bei_tables, use_case=use_case, indices_provider=bcra)
            app.state.app_state.set_bei(tables)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("BEI loop iteration failed")


def _crash_reporter(app: FastAPI):
    """`on_crash` del supervisor → `AppState.record_loop_crash(name, reason)`.

    Se le pasa el nombre del loop ESTRUCTURADO, no embebido en una frase: antes esto
    armaba "loop {name} cayó ({reason}) — reiniciando" y `AppState` volvía a sacarle
    el nombre con un regex, así que cambiar una palabra del mensaje (o un `reason`
    largo, que la truncación a 300 chars cortaba antes del ')') desviaba la caída al
    canal equivocado EN SILENCIO. Función de módulo —no un closure adentro del
    lifespan— para que el wiring sea testeable sin levantar la app."""
    async def _on_crash(name: str, reason: str) -> None:
        # Que la caída deje rastro (registro por loop + badge si el loop es crítico):
        # el incidente del 2026-09-01 duró 22hs justamente por ser mudo.
        await app.state.app_state.record_loop_crash(name, reason)
    return _on_crash


@asynccontextmanager
async def lifespan(app: FastAPI):
    from core.infrastructure.bondterminal_provider import BondTerminalProvider
    from core.infrastructure.fx_provider import DolarAPIProvider
    from core.infrastructure.futures_provider import RofexProvider
    from core.infrastructure.indices_provider import BCRAIndicesProvider
    from core.infrastructure.data912_provider import Data912MarketDataProvider

    from core.infrastructure.byma.sources import make_source, Data912Source

    app.state.client = ResilientClient()
    # Fuente live inicial: settings.market_source (default byma_open). Si falla
    # (p.ej. byma_realtime sin credenciales), cae a byma_open y luego a data912.
    try:
        initial_source = make_source(settings.market_source)
    except Exception as e:  # noqa: BLE001
        logger.warning("market source %s no disponible (%s); usando byma_open.",
                       settings.market_source, e)
        try:
            initial_source = make_source("byma_open")
        except Exception:  # noqa: BLE001
            initial_source = Data912Source()
    app.state.hub = ProviderHub(app.state.client, active_source=initial_source)
    app.state.app_state = AppState()
    app.state.app_state.set_data_source(app.state.hub.active_mode,
                                        app.state.hub.active_label,
                                        app.state.hub.is_delayed)
    # Clock congelado por accidente: un MONITOR_AS_OF olvidado en .env congelaría
    # TODOS los precios a una fecha vieja sin señal visible — gritarlo al boot.
    from core.domain.clock import warn_if_frozen
    warn_if_frozen()
    # Backup del catálogo (fuente de verdad viva) ANTES de warmear el repo / migrar:
    # snapshot consistente del estado previo, best-effort (jamás bloquea el arranque).
    try:
        from core.infrastructure.db.backup import backup_db
        bak = await asyncio.to_thread(backup_db, settings.catalog_db, settings.backup_dir,
                                      keep=settings.backup_keep)
        if bak:
            logger.info("catalog backup: %s", bak.name)
    except Exception:  # noqa: BLE001
        logger.warning("backup de catalog.db falló (no bloquea el arranque)", exc_info=True)
    repo = get_repo()  # warm: carga SQLite / siembra desde Excel
    # Salud del catálogo → AppState (badge + /api/health). Incluye el fallo de la
    # SIEMBRA: `CatalogRepository` ya no lo deja explotar el arranque (mataba también
    # /api/health, o sea la superficie donde se lee el motivo), lo publica.
    await _publish_catalog_health(app, repo)
    # Providers para el popup de detalle (comparten caches class-level con el refresh).
    app.state.provider = Data912MarketDataProvider()
    app.state.indices = BCRAIndicesProvider(excel_repo=repo)
    app.state.fx = DolarAPIProvider()
    app.state.rofex = RofexProvider()  # WS Matba lazy (warmup en el 1er get_quotes)
    app.state.bondterminal = BondTerminalProvider()  # riesgo país EMBI AR (TTL 5min)
    # En tests (MONITOR_DISABLE_LOOPS=1) NO arrancamos los loops: corren pricing
    # con indices reales en background y contaminan los caches de módulo
    # (p.ej. el avg TAMAR), rompiendo la aislación del test de equivalencia.
    tasks = []
    # `stopping` distingue el shutdown de una caída: el supervisor lo mira para saber
    # si una CancelledError es legítima (apagando) o espuria (hay que reiniciar).
    stopping = asyncio.Event()
    app.state.stopping = stopping
    if not os.environ.get("MONITOR_DISABLE_LOOPS"):
        _on_crash = _crash_reporter(app)
        # `_startup_reconcile` NO se supervisa: corre una vez y terminar es su contrato.
        # Los otros loops son `while True`: terminar es una caida (ver supervisor.py).
        tasks = [asyncio.create_task(_startup_reconcile(app))]
        loop_specs = [("refresh", _refresh_loop), ("bei", _bei_loop)]
        if HISTORY_TYPES:
            loop_specs.append(("history", _history_loop))
        tasks += [
            asyncio.create_task(
                supervise(name, lambda fn=fn: fn(app), stopping=stopping,
                          on_crash=_on_crash),
                name=f"loop:{name}")
            for name, fn in loop_specs
        ]
    try:
        yield
    finally:
        stopping.set()   # ANTES de cancelar: le dice al supervisor que no reinicie
        for task in tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await app.state.client.aclose()


# Docs de OpenAPI APAGADAS por default: FastAPI las monta sobre el router raíz y
# /openapi.json publicaría el inventario completo de endpoints. Para levantarlas en
# desarrollo: MONITOR_ENABLE_DOCS=1 (NUNCA en el droplet).
_DOCS = bool(os.environ.get("MONITOR_ENABLE_DOCS"))
app = FastAPI(
    title="Monitor Renta Fija AR",
    lifespan=lifespan,
    docs_url="/docs" if _DOCS else None,
    redoc_url="/redoc" if _DOCS else None,
    openapi_url="/openapi.json" if _DOCS else None,
)
# GZip: el dataset de /fci/data es grande (~varios MB en JSON) → comprime ~6-7×.
# compresslevel=6 (default de Starlette = 9): mismo tamaño de salida en la práctica,
# ~mitad de CPU por request (medido sobre 4 MB: 107ms→43ms) — para TODA la app.
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=6)


# ── Estáticos con Cache-Control ─────────────────────────────────────────────
# Sin esto el navegador revalida ~556KB de vendor (chart/gridstack/htmx/html2canvas)
# en CADA navegación de página completa → un round-trip por asset contra el droplet
# = cambio de pestañas lento. Política:
#   • `?v=<hash/mtime>` presente (cache-busting) → immutable 1 año (la URL cambia si
#     cambia el contenido, así que cachear para siempre es seguro y un deploy se ve).
#   • `/vendor/**` (libs de terceros, no cambian entre deploys) → immutable 1 año.
#   • resto (CSS/JS propio sin versionar) → cache corto revalidable: un deploy se
#     ve enseguida, pero una ráfaga de navegación no revalida en cada clic.
_YEAR = "public, max-age=31536000, immutable"
_SHORT = "public, max-age=300"


class CachedStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            qs = scope.get("query_string", b"")
            versioned = b"v=" in qs
            is_vendor = path.startswith("vendor/") or path.startswith("vendor\\")
            response.headers["Cache-Control"] = _YEAR if (versioned or is_vendor) else _SHORT
        return response


app.mount("/static", CachedStaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="static")

@app.exception_handler(RequiresLoginException)
async def requires_login_exception_handler(request: Request, exc: RequiresLoginException):
    return JSONResponse({"detail": "authentication unavailable"}, status_code=401)

app.include_router(personal.router)

app.include_router(panels.router)
app.include_router(bonds.router)

# Parciales globales de HTMX
app.include_router(header.router)
app.include_router(stream.router)



@app.get("/api/health")
def health(repo=Depends(get_repo), state=Depends(get_state)):
    # Público (probes externos): NO expone `last_error` — es el string crudo de una
    # excepción del refresh loop (URLs/params internos de los providers). El detalle
    # del error lo ve el badge del header (/health/badge), que está detrás de login.
    st = state.status()
    return {
        # `status` habla de los PRECIOS (el refresh loop). La caída de un loop
        # lateral (bei) NO lo degrada —eso sería
        # gritar 'sin datos' con el snapshot fresco de hace 5s— pero se reporta
        # aparte en `degraded_loops` para que ops la vea. Sólo NOMBRES: el motivo
        # es el string crudo de una excepción y este endpoint es público.
        "status": "ok" if st["ok"] else "degraded",
        "instruments": len(repo.get_all_instruments()),
        "metrics_cached": len(state.metrics()),
        "is_stale": st["is_stale"],
        "age_seconds": st["age_seconds"],
        "last_refresh": st["last_refresh"],
        "degraded_loops": st["degraded_loops"],
        # Salud del CATÁLOGO: cuántos bonos quedaron invisibles (tipo huérfano),
        # cuántos tienen el tipo ASUMIDO por un default ambiguo y si la siembra de
        # bootstrap falló. Sólo CUENTAS y un booleano — el motivo crudo del fallo
        # (paths del servidor) y el inventario de tickers se quedan del lado privado.
        "catalog": st["catalog"],
        "ok": st["ok"],
    }


@app.get("/api/riesgo-pais")
def api_riesgo_pais(bt=Depends(get_bondterminal), _user=Depends(get_current_user)):
    """Riesgo país de BondTerminal: spread ponderado EMBI AR + valor Ambito, deltas, bonos.

    Endpoint de inspección (hermano de /api/health y /api/metrics): expone el payload
    COMPLETO — por-bono, sparkline, calidad del dato — que la card del header no muestra.
    La card se sirve del provider directo (`routers/header.py`), no de esta ruta."""
    data = bt.get_riesgo_pais()
    if data is None:
        return JSONResponse({"error": "no data available"}, status_code=503)
    return JSONResponse(data)


@app.get("/api/metrics")
def metrics(state=Depends(get_state), _user=Depends(get_current_user)):
    """Snapshot JSON del último refresh (prueba el wiring end-to-end del motor)."""
    out = []
    for m in state.metrics():
        inst = m.snapshot.instrument if m.snapshot else None
        out.append({
            "ticker": inst.ticker if inst else None,
            "type": inst.instrument_type if inst else None,
            "price": m.snapshot.price if m.snapshot else None,
            "tir": m.tir,
            "md": m.duration,
            "vtec": m.technical_value,
            "parity": m.parity,
        })
    return JSONResponse(out)
