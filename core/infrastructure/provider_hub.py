"""ProviderHub: ingesta async coordinada (deuda #6).

`refresh_all()` delega en la **fuente activa** (`MarketSource`: BYMA open / BYMA
realtime / Data912), trae sus paneles en paralelo, valida (Pydantic) y mergea SÓLO
lo bueno: si todo falla, preserva el último snapshot bueno (no wipea el cache).
La fuente se cambia en runtime con `set_source()` (hot-swap sin reiniciar los loops:
`HubMarketDataProvider` lee `snapshot()` en vivo cada ciclo).

BCRA / DolarAPI corren aparte (`prefetch()` async desde el refresh loop de app.py);
el hub sólo coordina las cotizaciones: fuente activa + piso Data912 (`_apply_floor`).
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import date
from typing import Dict, List, Optional

from core.domain.interfaces import IMarketDataProvider
from core.domain.models import MarketSnapshot
from core.infrastructure.async_http import ResilientClient
from core.infrastructure.byma.field_map import SETTLE_24, SETTLE_CI
from core.infrastructure.byma.sources import Data912Source, MarketSource
from core.infrastructure.schemas import Data912Row

logger = logging.getLogger(__name__)


def _has_rows(snaps: Dict[str, Dict[str, Data912Row]]) -> bool:
    """¿La fuente trajo algo en algún plazo este ciclo?"""
    return any(bool(rows) for rows in (snaps or {}).values())


# Campos de profundidad de mercado: valen aunque `c` venga en 0 (pre-apertura hay
# puntas y volumen sin última cotización), así que sobreviven al fallback de precio.
_DEPTH_FIELDS = ("px_bid", "px_ask", "v", "q_op")


def _good(row: Optional[Data912Row]) -> Optional[Data912Row]:
    """La fila si trae precio real (>0); None si es 0/None (esqueleto o ilíquida)."""
    return row if (row is not None and row.c and row.c > 0) else None


def _with_depth_of(base: Data912Row, live: Optional[Data912Row]) -> Data912Row:
    """Precio de `base` (cierre bueno) + profundidad viva de `live` (la fila en 0 de
    la fuente activa). Sin `live` o sin puntas vivas devuelve `base` tal cual."""
    if live is None:
        return base
    depth = {f: getattr(live, f) for f in _DEPTH_FIELDS if getattr(live, f, None) is not None}
    return base.model_copy(update=depth) if depth else base


class ProviderHub:
    # Floor Data912: cada cuántos segundos se refresca el snapshot Data912 que rellena
    # los símbolos que la fuente activa (BYMA) no lista. TTL para no duplicar la carga
    # (BYMA va cada ciclo ~5s; el cierre que aporta el floor casi no cambia intradía).
    _FLOOR_TTL_S = 25.0

    def __init__(self, client: ResilientClient, active_source: Optional[MarketSource] = None):
        self._client = client
        # Snapshot por plazo (stale-safe): {"24": {sym:row}, "CI": {sym:row}}.
        self._snap: Dict[str, Dict[str, Data912Row]] = {SETTLE_24: {}, SETTLE_CI: {}}
        self._source: Dict[str, str] = {}           # symbol → bucket (bonds/notes/corp/stocks/cedears)
        # Lock de hilos: el snapshot lo MUTA el event loop (refresh_all) y lo LEE
        # el thread pool (use_case.execute vía to_thread → snapshot()). Sin esto,
        # dict(self._snapshot) puede pegar "dictionary changed size during iteration".
        # (threading.Lock, NO asyncio.Lock: el reader corre en otro hilo.)
        self._lock = threading.Lock()
        # Default Data912 (back-compat de tests/CLI); la app setea byma_open al arrancar.
        self._active: MarketSource = active_source or Data912Source()
        # Floor Data912 (rellena lo que la activa no lista). `_active_syms` = símbolos que
        # la activa cubrió en los últimos K_ACTIVE_CYCLES ciclos. Ventana deslizante (no
        # acumulado infinito): un símbolo que la activa deja de listar sale a los K ciclos
        # y el floor vuelve a cubrirlo. Anti-flicker: dentro de la ventana la activa manda.
        self._K_ACTIVE_CYCLES: int = 3
        self._active_sym_counts: Dict[str, int] = {}   # sym → ciclos restantes antes de expirar
        self._active_syms: set = set()                  # los que tienen contador > 0
        self._last_active_rows: Dict[str, Dict[str, Data912Row]] = {}  # último valor BYMA por settle
        self._floor_snaps: Dict[str, Dict[str, Data912Row]] = {}
        self._floor_source: Dict[str, str] = {}
        self._floor_at: float = 0.0
        # Frescura por símbolo: monotonic() de la última vez que la fuente activa lo listó.
        # Solo la escribe el event-loop (refresh_all); se lee bajo lock en freshness().
        # Permite al panel distinguir precios live de rancios y habilita la purga diaria.
        self._seen_at: Dict[str, float] = {}
        # Día del último ciclo de purga (para ejecutarla 1×/día al rollover).
        self._purge_day: Optional[date] = None
        # Símbolos no vistos en más de _PURGE_MAX_DAYS días se eliminan del snapshot.
        self._PURGE_MAX_DAYS: int = 5

    # ---------------- fuente activa (hot-swap) ----------------
    @property
    def active_mode(self) -> str:
        return self._active.mode

    @property
    def active_label(self) -> str:
        return self._active.label

    @property
    def is_delayed(self) -> bool:
        return bool(getattr(self._active, "delayed", False))

    def set_source(self, source: MarketSource) -> None:
        """Cambia la fuente live. El próximo `refresh_all()` ya usa la nueva."""
        logger.info("ProviderHub: fuente activa → %s", source.mode)
        self._active = source
        self._active_syms = set()        # recalcular cobertura desde cero
        self._active_sym_counts = {}     # resetear ventana K de la nueva fuente
        self._last_active_rows = {}      # resetear cache de valores BYMA

    # ---------------- fetch live (fuente activa) ----------------
    async def refresh_all(self) -> Dict[str, Data912Row]:
        """Trae las cotizaciones live de la fuente activa (paneles en paralelo),
        mergea stale-safe por plazo y devuelve el snapshot 24hs. Punto de extensión
        para FX/BCRA."""
        try:
            snaps, source = await self._active.fetch(self._client)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 — la fuente caída no tumba el ciclo
            logger.warning("market source %s fetch failed: %s: %s",
                           self._active.mode, type(e).__name__, e)
            snaps, source = {}, {}
        # Ventana deslizante K_ACTIVE_CYCLES: un símbolo entra en _active_syms al aparecer
        # en la fuente activa y recibe un contador = K. Cada ciclo sin aparecer decrementa
        # en 1; al llegar a 0 sale del set y el floor puede cubrirlo. K ciclos consecutivos
        # de ausencia son necesarios para salir — una rueda vacía puntual no lo descarta.
        seen_this_cycle: set = set()
        for rows in (snaps or {}).values():
            seen_this_cycle.update(rows.keys())
        # Persistir los últimos valores BYMA para retención stale (anti-floor en ventana K).
        # Solo precios reales (c>0): un 0 no es dato (especie ilíquida/esqueleto) y no debe
        # quedar retenido como "último valor bueno" ni reinyectarse en un ciclo vacío.
        if seen_this_cycle:
            for settle, rows in (snaps or {}).items():
                prev = self._last_active_rows.setdefault(settle, {})
                for sym, row in rows.items():
                    if row is not None and row.c and row.c > 0:
                        prev[sym] = row
        # Actualizar contadores: visto → reset a K; ausente → decrementar.
        all_tracked = set(self._active_sym_counts) | seen_this_cycle
        new_counts: Dict[str, int] = {}
        for sym in all_tracked:
            if sym in seen_this_cycle:
                new_counts[sym] = self._K_ACTIVE_CYCLES  # reset a K: K ciclos de gracia
            else:
                cnt = self._active_sym_counts.get(sym, 0) - 1
                if cnt > 0:
                    new_counts[sym] = cnt
                # cnt <= 0 → sale del tracking (floor puede cubrirlo)
        self._active_sym_counts = new_counts
        self._active_syms = {s for s, c in new_counts.items() if c > 0}
        # Frescura: marcar timestamp de la fuente activa bajo lock + purga diaria stale.
        if seen_this_cycle:
            _now = time.monotonic()
            today = date.today()
            with self._lock:
                for sym in seen_this_cycle:
                    self._seen_at[sym] = _now
                # Purga 1×/día al rollover: borra del snapshot lo claramente muerto.
                # Invariante stale-safe: solo purga si hay datos de frescura (_seen_at
                # no vacío) y nunca ante un ciclo vacío (visto al menos 1 símbolo).
                if today != self._purge_day:
                    self._purge_day = today
                    max_age = self._PURGE_MAX_DAYS * 86400.0
                    stale = [s for s, ts in self._seen_at.items()
                             if (_now - ts) > max_age]
                    for s in stale:
                        del self._seen_at[s]
                        for settle in (SETTLE_24, SETTLE_CI):
                            self._snap.get(settle, {}).pop(s, None)
                        # `_source` acompaña a `_snap`: si no se purga acá queda
                        # afirmando la procedencia de un símbolo que ya no existe
                        # (el listado del ABM lee de ahí) y crece sin techo.
                        self._source.pop(s, None)
                    if stale:
                        logger.info("hub: purged %d stale symbols (>%dd)",
                                    len(stale), self._PURGE_MAX_DAYS)
        # Floor Data912 por símbolo: si la activa NO es Data912, Data912 rellena los
        # símbolos que la activa no lista (BYMA open en feriado/pre-market lista parcial)
        # → se muestra el universo completo con LAST/cierre. La activa manda donde lista;
        # el floor solo aporta lo que falta. Subsume el viejo backstop de board-vacío.
        if self._active.mode != Data912Source.mode:
            f_snaps, f_source = await self._data912_floor()
            if _has_rows(f_snaps):
                snaps, source = self._apply_floor(snaps, source, f_snaps, f_source)
        return self._merge(snaps, source)

    async def _data912_floor(self):
        """Snapshot Data912 cacheado (TTL `_FLOOR_TTL_S`) para rellenar lo que la fuente
        activa no lista. Ante fallo, reusa el último floor bueno (degrada, no rompe)."""
        now = time.monotonic()
        if self._floor_snaps and (now - self._floor_at) < self._FLOOR_TTL_S:
            return self._floor_snaps, self._floor_source
        try:
            snaps, source = await Data912Source().fetch(self._client)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 — el floor caído no tumba el ciclo
            logger.warning("floor Data912 falló: %s: %s", type(e).__name__, e)
            return self._floor_snaps, self._floor_source
        if _has_rows(snaps):
            self._floor_snaps, self._floor_source, self._floor_at = snaps, source, now
        return self._floor_snaps, self._floor_source

    def _apply_floor(self, active, active_src, floor, floor_src):
        """Mergea el floor Data912 BAJO la fuente activa: la activa manda DONDE TRAE PRECIO;
        el floor aporta los símbolos que la activa NO cubre (`self._active_syms`). Para
        símbolos en `_active_syms` que la activa no devolvió este ciclo (BYMA transitoriamente
        vacío), se retiene el último valor bueno de la activa (anti-clobber del floor).

        Un precio 0 de la activa NO es dato (especie ilíquida o esqueleto del catálogo, p.ej.
        ~3/4 del universo BYMA realtime viene en 0): si el floor tiene un cierre real para ese
        símbolo, gana el floor — un 0 no debe pisar un cierre bueno y dejar la fila en blanco.
        Sin floor, cae al último valor bueno de la activa: `_merge` ACUMULA sobre `_snap`, así
        que escribir el 0 borraría el precio que la fila ya tenía. Y el precio del fallback se
        combina con la profundidad VIVA de la activa (bid/ask/volumen/nº de operaciones), que
        un c=0 no invalida: pre-apertura hay puntas reales sin última cotización."""
        out = {}
        for settle in (SETTLE_24, SETTLE_CI):
            floor_rows = floor.get(settle) or {}
            active_rows = active.get(settle) or {}
            base = {}
            for sym, row in floor_rows.items():
                if sym not in self._active_syms and _good(row) is not None:
                    base[sym] = row
            # Stale retention: símbolos activos que BYMA no devolvió este ciclo → último valor
            last = self._last_active_rows.get(settle) or {}
            for sym in self._active_syms:
                if sym not in active_rows and sym in last:
                    base[sym] = last[sym]
            # La activa de este ciclo manda donde trae precio (>0). Si vino en 0 (iliquidez/
            # esqueleto) cae al cierre del floor y, si tampoco lo hay, al último valor bueno
            # de la propia activa; recién sin ninguna alternativa se muestra el 0 (mejor un 0
            # explícito que ocultar la especie).
            for sym, row in active_rows.items():
                if row is not None and row.c and row.c > 0:
                    base[sym] = row
                    continue
                fb = _good(floor_rows.get(sym)) or _good(last.get(sym))
                base[sym] = _with_depth_of(fb, row) if fb is not None else row
            out[settle] = base
        return out, {**(floor_src or {}), **(active_src or {})}

    async def fetch_data912(self) -> Dict[str, Data912Row]:
        """Atajo: fuerza un fetch Data912 a este hub (usado por tests/CLI). NO
        cambia la fuente activa."""
        snaps, source = await Data912Source().fetch(self._client)
        return self._merge(snaps, source)

    def _merge(self, snaps: Dict[str, Dict[str, Data912Row]], source: Dict[str, str]) -> Dict[str, Data912Row]:
        # Preservar stale por plazo (no wipear → el UI no queda en blanco).
        with self._lock:
            for settle, rows in (snaps or {}).items():
                if rows:
                    self._snap.setdefault(settle, {}).update(rows)
            if source:
                self._source.update(source)
            return dict(self._snap[SETTLE_24])

    # ---------------- accessors ----------------
    def sources(self) -> Dict[str, str]:
        """{symbol: bucket} del último snapshot (para el listado de faltantes del ABM)."""
        with self._lock:
            return dict(self._source)

    def snapshot(self, settle: str = SETTLE_24) -> Dict[str, Data912Row]:
        """Snapshot del plazo pedido ('24' default | 'CI'). Plazo sin datos → 24hs."""
        with self._lock:
            snap = self._snap.get(settle)
            return dict(snap if snap else self._snap[SETTLE_24])

    def freshness(self) -> Dict[str, float]:
        """Antigüedad en segundos desde que la fuente activa listó cada símbolo.
        Vacío si el hub todavía no recibió datos. Permite al panel distinguir
        precios live de rancios sin romper la firma de `snapshot()`."""
        _now = time.monotonic()
        with self._lock:
            return {sym: _now - ts for sym, ts in self._seen_at.items()}


class HubMarketDataProvider(IMarketDataProvider):
    """`IMarketDataProvider` que sirve los snapshots desde el `ProviderHub` (el
    fetch async ya lo hizo `refresh_all`) y delega el histórico (CSV en disco /
    endpoint de OHLC) a un `Data912MarketDataProvider` sync.

    Esto cablea la ingesta async en el hot-path del refresh loop sin forzar
    async dentro del motor de pricing (que sigue corriendo sync vía to_thread):
    el use-case lee `fetch_snapshots` del snapshot ya materializado por el hub."""

    def __init__(self, hub: ProviderHub, history_provider: object = None,
                 settle: str = SETTLE_24):
        self._hub = hub
        self._settle = settle  # plazo de los precios live ('24' | 'CI')
        if history_provider is None:
            from core.infrastructure.data912_provider import Data912MarketDataProvider
            history_provider = Data912MarketDataProvider()
        self._hist = history_provider

    def fetch_snapshots(self, tickers: List[str]) -> Dict[str, MarketSnapshot]:
        snap = self._hub.snapshot(self._settle)
        out: Dict[str, MarketSnapshot] = {}
        today = date.today()
        for ticker in tickers:
            t = str(ticker).upper()
            # _CER es alias de display del lado CER de los duales (TXMJ8_CER → TXMJ8).
            market_t = t[:-4] if t.endswith("_CER") else t
            row = snap.get(market_t) or snap.get(t)
            if not row:
                continue
            out[ticker] = MarketSnapshot(
                instrument=None, price=float(row.c or 0.0), last_update=today,
                bid=row.px_bid, ask=row.px_ask, volume=row.v,
                operations=row.q_op, change_pct=row.pct_change,
            )
        return out

    def fetch_historical_prices(self, ticker: str, days: int):
        return self._hist.fetch_historical_prices(ticker, days)

    def fetch_stock_history(self, ticker: str):
        return self._hist.fetch_stock_history(ticker)
