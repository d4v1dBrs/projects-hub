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
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from apps.web.bond_detail import get_bond_detail, get_horizon_matrix
from apps.web.deps import get_fx, get_indices, get_provider, get_repo
from apps.web.templates import TEMPLATES as _TEMPLATES

logger = logging.getLogger(__name__)
router = APIRouter()


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
