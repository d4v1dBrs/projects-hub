"""Router del popup de detalle de bono (HTMX).

GET  /bond/{ticker}/detail          → fragmento modal (tabs Trading / Gráfico / Quant).
GET  /bond/{ticker}/horizon-matrix  → matriz de horizonte (tab Quant, hx-get).
GET  /bond/{ticker}/price-history   → JSON para Lightweight Charts (tab Gráfico).

Reusa apps.web.bond_detail.* con los providers de app.state. (La calculadora
precio↔TIR vive en /abm/calc; el drawer "Proyección CER" se retiró con el rediseño.)
"""

from __future__ import annotations

import html
import logging
import math
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from apps.web.bond_detail import get_horizon_matrix
from apps.web.bond_history import compare_histories, history_bundle, raw_market
from apps.web.deps import get_fx, get_hub, get_indices, get_provider, get_repo, get_state
from apps.web.json_script import json_for_script
from apps.web.templates import TEMPLATES as _TEMPLATES
from core.domain.currency import ccy_from_suffix, position_currency
from core.infrastructure.provider_hub import HubMarketDataProvider

logger = logging.getLogger(__name__)
router = APIRouter()
_history_inflight = 0


async def _bounded_history_call(fn, *args):
    # Public diagnostics never occupy the whole shared worker pool. There is no
    # waiting queue: callers can retry after a short busy response. Starlette's
    # shielded worker await retains the slot until the sync network work ends.
    global _history_inflight
    if _history_inflight >= 4:
        raise HTTPException(503, "Historicos ocupados; reintentar.", headers={"Retry-After": "3"})
    _history_inflight += 1
    try:
        return await run_in_threadpool(fn, *args)
    finally:
        _history_inflight -= 1


# Plazo de liquidación BYMA: SOLO T+0 (CI) y T+1 (24hs) existen —
# `settlement_byma_date` levanta ValueError con cualquier otro y el handler no lo
# atrapa, así que `?lag=5` devolvía un 500 (traza en el log, modal roto). Acotarlo en
# el borde lo convierte en un 422 de validación, igual que se hizo con `?days=` en
# /cashflows. Los GET comparten la MISMA cota (no dos copias que se desincronizan).
#
# Va como **tipo `Annotated`**, NO como valor por defecto compartido (el viejo
# `lag: int = _LAG`): por el camino "default value" FastAPI usa el MISMO objeto
# `FieldInfo` que le pasan y lo **muta** al analizar cada path operation
# (`analyze_param`: `field_info.annotation = ...`, `field_info.in_ = ...`, el alias),
# así que un único `Query(...)` compartido entre endpoints era estado
# mutable global entre endpoints. Con `Annotated` FastAPI **copia** el `FieldInfo` por
# parámetro (`copy_field_info`, con el comentario "Copy `field_info` because we mutate
# `field_info.default` below") y cada endpoint se queda con el suyo. Ojo: con
# `Annotated` el default NO puede ir adentro de `Query(...)` (FastAPI lo asertea) —
# va en el `= 1` de cada firma.
Lag = Annotated[int, Query(ge=0, le=1,
                           description="Plazo de liquidación: 0 = CI (T+0), 1 = 24hs (T+1)")]


@router.get("/bond/{ticker}/detail", response_class=HTMLResponse)
def detail(ticker: str, request: Request, lag: Lag = 1,
           repo=Depends(get_repo), provider=Depends(get_provider),
           indices=Depends(get_indices), fx=Depends(get_fx), hub=Depends(get_hub),
           state=Depends(get_state)):
    data = _workbench(ticker, lag, {}, repo, provider, indices, fx, hub, state)
    d = data["detail"] if data else None
    if d is None:
        # `ticker` viene del path del request: ESCAPARLO siempre. Este 404 es el único
        # HTML de la capa web armado a mano (el resto va por Jinja, que autoescapa) y
        # se sirve como text/html → sin escape es XSS reflejado ejecutable.
        safe_ticker = html.escape(ticker)
        return HTMLResponse(
            f'<div class="modal-overlay" onclick="if(event.target===this)this.remove()">'
            f'<div class="modal-card"><div class="modal-head"><b>{safe_ticker}</b>'
            f'<button class="x" onclick="document.getElementById(\'modal\').innerHTML=\'\'">✕</button>'
            f'</div><div class="modal-body err">Instrumento no encontrado</div></div></div>',
            status_code=404,
        )
    return _TEMPLATES.TemplateResponse(request, "fragments/bond_detail.html", {
        "d": d, "lag": lag, "workbench_json": json_for_script(data)})


class WorkbenchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    price: float | None = Field(default=None, gt=0, le=1e9)
    nominal: float = Field(default=10000, ge=0, le=1e12)
    cost_price: float | None = Field(default=None, gt=0, le=1e9)
    yield_pct: float | None = Field(default=None, ge=-90, le=1000)
    shock_bps: float = Field(default=100, ge=-5000, le=5000)
    capital: float = Field(default=100000, gt=0, le=1e12)
    entry_fee_pct: float = Field(default=.5, ge=0, le=10)
    exit_fee_pct: float = Field(default=.5, ge=0, le=10)
    annual_fee_pct: float = Field(default=0, ge=0, le=10)
    horizon_days: int = Field(default=365, ge=1, le=10950)
    income_target: float = Field(default=0, ge=0, le=1e12)
    inflation_pct: float = Field(default=20, ge=-50, le=1000)


def _catalog_symbol(ticker, repo):
    t = ticker.upper().strip()
    if repo.get_instrument_by_ticker(t):
        return t
    base = t.rsplit("_", 1)[0] if t.endswith(("_TF", "_TAM", "_CER")) else t
    if repo.get_instrument_by_ticker(base) is None:
        raise HTTPException(status_code=404, detail="Instrumento no encontrado")
    return base


def _workbench(ticker, lag, params, repo, provider, indices, fx, hub, state):
    from apps.web.bond_workbench import build_workbench

    market = HubMarketDataProvider(hub, provider, settle="CI" if lag == 0 else "24")
    data = build_workbench(ticker, repo, market, indices, fx, settlement_lag=lag, params=params)
    if data is None:
        return None
    data["source"] = {
        "label": f"{hub.active_label} + respaldo Data912",
        "delayed": hub.is_delayed,
        "snapshot_at": state.last_refresh.isoformat() if state.last_refresh else None,
        "note": "BYMA Open: 20 min de demora. Data912 no distingue CI/24hs. "
                "La hora corresponde al refresco del monitor, no a la ultima operacion. "
                "Puntas indicativas; profundidad y ejecutabilidad no garantizadas.",
    }
    d = data["detail"]
    resolved = _catalog_symbol(ticker, repo)
    inst = repo.get_instrument_by_ticker(resolved)
    ccy = position_currency(inst.instrument_type, inst.ticker)
    peers = []
    for row in state.metrics():
        other = row.snapshot.instrument if row.snapshot else None
        if not other or other.ticker == resolved or other.instrument_type != inst.instrument_type:
            continue
        if position_currency(other.instrument_type, other.ticker) != ccy:
            continue
        if ccy == "USD" and ccy_from_suffix(other.ticker) != ccy_from_suffix(inst.ticker):
            continue
        if row.tir is None or row.duration is None or not math.isfinite(row.tir + row.duration):
            continue
        peers.append({"ticker": other.ticker, "price": row.snapshot.price,
                      "yield": row.tir, "duration": row.duration,
                      "spread_bps": (row.tir - d["metrics"]["tir"]) * 10000
                      if d["metrics"].get("tir") is not None and lag == 1 else None})
    duration = d["metrics"].get("duration") or 0
    peers.sort(key=lambda p: abs(p["duration"] - duration))
    data["peers"] = peers[:8]
    return data


@router.post("/bond/{ticker}/workbench")
def workbench(ticker: str, body: WorkbenchInput, lag: Lag = 1,
              repo=Depends(get_repo), provider=Depends(get_provider),
              indices=Depends(get_indices), fx=Depends(get_fx), hub=Depends(get_hub),
              state=Depends(get_state)):
    _catalog_symbol(ticker, repo)
    return _workbench(ticker, lag, body.model_dump(), repo, provider, indices, fx, hub, state)


@router.get("/bond/{ticker}/history-analysis")
async def history_analysis(ticker: str, compare: str | None = Query(default=None, max_length=24),
                           repo=Depends(get_repo), provider=Depends(get_provider)):
    symbol = _catalog_symbol(ticker, repo)
    other = _catalog_symbol(compare, repo) if compare else None
    def load():
        data = history_bundle(symbol, provider)
        if other:
            data = {**data, "comparison": compare_histories(data, history_bundle(other, provider))}
        return data

    return await _bounded_history_call(load)


@router.get("/bond/{ticker}/api-fields")
async def api_fields(ticker: str, lag: Lag = 1, repo=Depends(get_repo)):
    symbol = _catalog_symbol(ticker, repo)
    if symbol.endswith("_CER"):
        symbol = symbol[:-4]
    return await _bounded_history_call(raw_market, symbol, lag)


@router.get("/bond/{ticker}/horizon-matrix", response_class=HTMLResponse)
def horizon_matrix(ticker: str, request: Request, lag: Lag = 1,
                   repo=Depends(get_repo), provider=Depends(get_provider),
                   indices=Depends(get_indices), fx=Depends(get_fx)):
    """Calcula y devuelve el fragmento HTML con la matriz de análisis de horizonte (Horizon Matrix)."""
    # Usamos asyncio.to_thread si fuera muy pesado, pero la aproximación de Taylor es O(1) rápido
    data = get_horizon_matrix(ticker, repo, provider, indices, fx, settlement_lag=lag)
    if not data:
        return HTMLResponse("<div class='text-red-400 text-sm p-4'>Instrumento sin datos para análisis.</div>")

    return _TEMPLATES.TemplateResponse(request, "fragments/horizon_matrix.html", {"data": data})

@router.get("/bond/{ticker}/price-history")
async def price_history(ticker: str, provider=Depends(get_provider), repo=Depends(get_repo)):
    """Cierres diarios (máx. 3 años) en el formato de Lightweight Charts.

    El ticker se valida contra el catálogo ANTES de tocar la red: la ruta es pública y
    `fetch_historical_prices` sale a Data912 y, si trae poco, a BYMA (cliente nuevo,
    hasta 40s) por cada llamada — sin este guard cualquier string inventado disparaba
    dos requests salientes. Una falla de red vuelve como 503 con lista vacía para que
    el chart del modal degrade en vez de romper el popup entero con un 500."""
    t = ticker.upper().strip()
    base = t[:-4] if t.endswith("_CER") else t
    if repo.get_instrument_by_ticker(t) is None and repo.get_instrument_by_ticker(base) is None:
        return JSONResponse([], status_code=404)
    try:
        series = await _bounded_history_call(history_bundle, t, provider)
    except HTTPException:
        raise
    except Exception as exc:   # borde HTTP: cualquier fallo del provider
        logger.warning("price-history %s: %s", ticker, exc)
        return JSONResponse([], status_code=503)
    return JSONResponse([{"time": b["time"], "value": b["value"]} for b in series["bars"]])
