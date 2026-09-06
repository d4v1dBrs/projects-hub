"""Router del popup de detalle de bono (HTMX).

GET  /bond/{ticker}/detail          → fragmento modal (tabs Trading / Gráfico / Quant).
GET  /bond/{ticker}/horizon-matrix  → matriz de horizonte (tab Quant, hx-get).
GET  /bond/{ticker}/price-history   → JSON para Lightweight Charts (tab Gráfico).
POST /bond/{ticker}/metrics         → calculadora precio↔TIR (el modal rediseñado ya
                                      no tiene el form; queda como API).
GET/POST /bond/{ticker}/cer         → drawer "Proyección CER" (ídem: sin botón hoy).

Reusa apps.web.bond_detail.* con los providers de app.state.
"""

from __future__ import annotations

import asyncio
import html
import logging
import math
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from apps.web.bond_detail import calculate, cer_projection, get_bond_detail, get_horizon_matrix
from apps.web.deps import get_fx, get_indices, get_provider, get_repo, get_state
from apps.web.templates import TEMPLATES as _TEMPLATES
from core.infrastructure.rem_provider import REMProvider

logger = logging.getLogger(__name__)
router = APIRouter()


# Plazo de liquidación BYMA: SOLO T+0 (CI) y T+1 (24hs) existen —
# `settlement_byma_date` levanta ValueError con cualquier otro y el handler no lo
# atrapa, así que `?lag=5` devolvía un 500 (traza en el log, modal roto). Acotarlo en
# el borde lo convierte en un 422 de validación, igual que se hizo con `?days=` en
# /cashflows. Los dos GET comparten la MISMA cota (no dos copias que se desincronizan).
#
# Va como **tipo `Annotated`**, NO como valor por defecto compartido (el viejo
# `lag: int = _LAG`): por el camino "default value" FastAPI usa el MISMO objeto
# `FieldInfo` que le pasan y lo **muta** al analizar cada path operation
# (`analyze_param`: `field_info.annotation = ...`, `field_info.in_ = ...`, el alias),
# así que un único `Query(...)` compartido por `detail` y `cer_drawer` era estado
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
           indices=Depends(get_indices), fx=Depends(get_fx)):
    d = get_bond_detail(ticker, repo, provider, indices, fx, settlement_lag=lag)
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
    return _TEMPLATES.TemplateResponse(request, "fragments/bond_detail.html", {"d": d, "lag": lag})


@router.post("/bond/{ticker}/metrics", response_class=HTMLResponse)
def metrics(ticker: str, request: Request,
            settlement_lag: int = Form(1, ge=0, le=1),
            price: Optional[float] = Form(None),
            tir_pct: Optional[float] = Form(None),
            repo=Depends(get_repo), provider=Depends(get_provider),
            indices=Depends(get_indices), fx=Depends(get_fx)):
    if tir_pct is not None and price is None:
        res = calculate(ticker, repo, provider, indices, fx, mode="from_tir",
                        tir=tir_pct / 100.0, settlement_lag=settlement_lag)
    else:
        res = calculate(ticker, repo, provider, indices, fx, mode="from_price",
                        price=price, price_mode="dirty", settlement_lag=settlement_lag)
    return _TEMPLATES.TemplateResponse(request, "fragments/calc_result.html", {"res": res})


def _to_float(raw):
    """Parse tolerante (acepta coma decimal). None si no es número."""
    if raw is None:
        return None
    try:
        return float(str(raw).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def _rem_provider():
    return REMProvider()


def _sendero(state):
    """Filas del sendero mensual BEI/REM del último cómputo BEI (o None)."""
    bei = state.bei_tables() if state is not None else None
    return (bei or {}).get("sendero") if bei else None


def _render_cer_drawer(request, data, *, ticker, lag, price, mode, unif, raw_inputs):
    unif_val = unif
    if unif_val is None and data.get("default_unif") is not None:
        unif_val = round(data["default_unif"] * 100, 2)
    return _TEMPLATES.TemplateResponse(request, "fragments/cer_drawer_body.html", {
        "d": data, "ticker": ticker, "lag": lag, "price": price,
        "mode": mode, "unif": unif_val, "raw_inputs": raw_inputs,
    })


@router.get("/bond/{ticker}/cer", response_class=HTMLResponse)
def cer_drawer(ticker: str, request: Request, lag: Lag = 1,
               price: Optional[float] = None,
               repo=Depends(get_repo), provider=Depends(get_provider),
               indices=Depends(get_indices), fx=Depends(get_fx), state=Depends(get_state)):
    """Cuerpo del cajón 'Proyección CER' (carga inicial): escenarios + valor CER
    por mes hasta el vto, con REM/BEI de referencia."""
    if price is None and state is not None:
        price = state.price_of(ticker)
    data = cer_projection(ticker, repo, provider, indices, fx,
                          price_dirty=price, settlement_lag=lag,
                          bei_sendero=_sendero(state), rem_provider=_rem_provider())
    return _render_cer_drawer(request, data, ticker=ticker, lag=lag, price=price,
                              mode="uniforme", unif=None, raw_inputs={})


@router.post("/bond/{ticker}/cer", response_class=HTMLResponse)
async def cer_drawer_calc(ticker: str, request: Request,
                          repo=Depends(get_repo), provider=Depends(get_provider),
                          indices=Depends(get_indices), fx=Depends(get_fx),
                          state=Depends(get_state)):
    """Recalcula el cajón con el escenario del usuario (uniforme o por mes)."""
    form = await request.form()
    # `or 1` NO sirve: T+0 es un plazo legítimo y `0.0` es falsy → el drawer
    # recalculaba con settlement T+1 mientras el header seguía marcando T+0.
    _lag = _to_float(form.get("lag"))
    # Acotado a T+0/T+1 como los GET (acá el form se parsea a mano, sin Query): un
    # `lag` de otro valor reventaba `settlement_byma_date` con un 500. `isfinite`
    # NO es paranoia: `_to_float` acepta 'nan'/'inf'/'1e400' (float() los parsea) y
    # sobre esos `int()` levanta ValueError/OverflowError → el mismo 500 por la
    # puerta de al lado.
    lag = (min(1, max(0, int(_lag)))
           if _lag is not None and math.isfinite(_lag) else 1)
    mode = form.get("mode", "uniforme")
    price = _to_float(form.get("price"))

    custom_infl = custom_monthly = None
    raw_inputs: dict = {}
    if mode == "custom":
        custom_monthly = {}
        for key, val in form.items():
            if not key.startswith("infl_"):
                continue
            ym = key[5:]
            raw_inputs[ym] = val
            dec = _to_float(val)
            if dec is None:
                continue
            try:
                y, m = ym.split("-")
                custom_monthly[(int(y), int(m))] = dec / 100.0
            except ValueError:
                pass
        custom_monthly = custom_monthly or None
    else:
        ci = _to_float(form.get("unif"))
        custom_infl = (ci / 100.0) if ci is not None else None

    # to_thread: `cer_projection` hace red SÍNCRONA (REM + BCRA, con timeouts de 10 s
    # cada uno). Corriendo en la corrutina congelaba el event loop entero —medido:
    # 8,5 s de lag, y hasta 40-60 s si los providers timeoutean— lo que frena TODAS
    # las conexiones SSE y el resto de los paneles de todos los clientes.
    data = await asyncio.to_thread(
        cer_projection, ticker, repo, provider, indices, fx,
        price_dirty=price, settlement_lag=lag,
        bei_sendero=_sendero(state), rem_provider=_rem_provider(),
        custom_infl_monthly=custom_infl, custom_monthly=custom_monthly)
    return _render_cer_drawer(request, data, ticker=ticker, lag=lag, price=price,
                              mode=mode, unif=form.get("unif"), raw_inputs=raw_inputs)


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
def price_history(ticker: str, provider=Depends(get_provider), repo=Depends(get_repo)):
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
        series = provider.fetch_historical_prices(ticker, days=1095)
    except Exception as exc:   # borde HTTP: cualquier fallo del provider
        logger.warning("price-history %s: %s", ticker, exc)
        return JSONResponse([], status_code=503)
    return JSONResponse([{"time": d.isoformat(), "value": p} for d, p in sorted(series.items())])
