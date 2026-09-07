"""Router de paneles de bonos (HTMX SSR).

`GET /bonos` → página index con los paneles de bonos (PANEL_ORDER).
`GET /panels/{id}/rows` → fragmento <tbody> que HTMX refresca cada 5s.

Reemplaza el polling global de `/api/snapshot` + el render JS de `app.js` por
fragmentos server-side. Reusa los InstrumentMetrics ya calculados en AppState
(motor Fase 1) y el column-schema del http.server original.

Row-building logic lives in `apps/web/panels_rows.py`; this module only wires
FastAPI routes, dependency injection, and the CI-metrics memoization cache.
"""

from __future__ import annotations

import threading
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from apps.web.json_script import json_for_script
from apps.web.deps import get_fx, get_indices, get_provider, get_repo, get_rofex, get_state
from apps.web.dashboard_layout import (
    DEFAULT_DASHBOARD_STATE,
    GRID_CELL_HEIGHT,
    GRID_COLUMNS,
    GRID_MARGIN,
)
from apps.web.templates import TEMPLATES as _TEMPLATES
from apps.web.panels_rows import (
    _build_futuros_rows, _build_futuros_share, _build_rows, _chart_payload,
    _drop_empty_share_cols, _share_full_cols, panel_columns,
)
from core.holiday_engine import settlement_byma_date
from core.infrastructure.provider_hub import HubMarketDataProvider
from core.use_cases.generate_report import GenerateMonitorReport

# Schema declarativo (columnas + registro PANELS + filtros) -> panels_schema.py.
from apps.web.routers.panels_schema import (  # noqa: E402
    PANELS, PANEL_ORDER, CCY_FILTER_PANELS, SETTLE_FILTER_PANELS,
    LEY_FILTER_PANELS, HISTORY_TYPES, _HL_COL_KEY,
)

router = APIRouter()


# ── CI metrics: memoización por (revision, panel_id) ────────────────────────

_CI_METRICS_CACHE: dict = {}
# `panel_rows` es un handler SYNC → FastAPI lo corre en el threadpool de anyio, y los
# dos paneles con selector CI disparan su hx-get con el MISMO evento sse:refresh: hay
# dos hilos dentro de `_ci_metrics` en cada ciclo. Sin este lock la lectura y la purga
# eran read-modify-write no atómicos (doble `del` → KeyError, iteración mientras el
# otro borra → RuntimeError) y el fragmento salía 500. Mismo patrón que fci_service.
_CI_METRICS_LOCK = threading.Lock()


def _ci_metrics(panel_id: str, request: Request, hist_provider,
                revision: int = -1) -> Optional[list]:
    """Métricas on-demand del plazo CI (T+0): corre el motor para los tipos del panel
    leyendo el snapshot CI del hub. Todo en memoria (el hub ya tiene CI del refresh,
    sin red extra). None si el panel no tiene tipos (no aplica).

    Memoizado por (revision, panel_id): si el AppState no cambió desde la última
    llamada para este panel devuelve el resultado cacheado sin reejecutar el motor."""
    types = PANELS[panel_id][1]
    if not types:
        return None

    cache_key = (revision, panel_id)
    with _CI_METRICS_LOCK:               # get() en vez de `in` + []: una sola lectura
        hit = _CI_METRICS_CACHE.get(cache_key)
    if hit is not None:                  # (una lista vacía también es un hit válido)
        return hit

    hub = request.app.state.hub
    ci_provider = HubMarketDataProvider(hub, hist_provider, settle="CI")
    # CI (T+0): settle_date=hoy descuenta TIR/MD desde hoy; settle_lag=0 mueve el ref
    # CER de la V.Téc a T+0 también → todo el cálculo en consonancia con el precio CI.
    app_state = request.app.state
    result = GenerateMonitorReport(
        get_repo(), ci_provider,
        indices=getattr(app_state, "indices", None),
        fx=getattr(app_state, "fx", None),
        history_types=HISTORY_TYPES, cached_history_only=True,
    ).execute(list(types), settle_date=date.today(), settle_lag=0)
    with _CI_METRICS_LOCK:
        # Purgar entradas de revisiones anteriores (revision es monótonamente creciente).
        for k in [k for k in _CI_METRICS_CACHE if k[0] != revision]:
            _CI_METRICS_CACHE.pop(k, None)
        _CI_METRICS_CACHE[cache_key] = result
    return result


# ── FastAPI route handlers ───────────────────────────────────────────────────

@router.get("/bonos", response_class=HTMLResponse)
def index(request: Request, state=Depends(get_state)):
    panels = [{"id": pid, "title": PANELS[pid][0], "columns": panel_columns(pid),
               "ccy_filter": pid in CCY_FILTER_PANELS,
               "ley_filter": pid in LEY_FILTER_PANELS,
               "settle_filter": pid in SETTLE_FILTER_PANELS,
               "hl_key": _HL_COL_KEY.get(pid),
               "chartable": bool(PANELS[pid][1]),
               "rows": []} for pid in PANEL_ORDER]
    return _TEMPLATES.TemplateResponse(
        request, "pages/index.html",
        {"panels": panels, "last_refresh": state.last_refresh,
         "default_layout": json_for_script(DEFAULT_DASHBOARD_STATE),
         "grid_columns": GRID_COLUMNS, "grid_cell_height": GRID_CELL_HEIGHT,
         "grid_margin": GRID_MARGIN},
    )


@router.get("/panels/{panel_id}/rows", response_class=HTMLResponse)
def panel_rows(panel_id: str, request: Request, settle: str = "24", state=Depends(get_state),
               provider=Depends(get_provider), rofex=Depends(get_rofex),
               fx=Depends(get_fx), indices=Depends(get_indices)):
    cols = panel_columns(panel_id)
    if panel_id == "futuros":
        rows = _build_futuros_rows(rofex, fx, indices)
    elif settle.upper() == "CI" and panel_id in SETTLE_FILTER_PANELS:
        metrics = _ci_metrics(panel_id, request, provider, revision=state.revision)
        rows = _build_rows(panel_id, state, provider, metrics_override=metrics or [])
    else:
        rows = _build_rows(panel_id, state, provider)
    return _TEMPLATES.TemplateResponse(
        request, "fragments/panel_rows.html",
        {"rows": rows, "ncols": len(cols),
         "bond_lag": 0 if settle.upper() == "CI" and panel_id in SETTLE_FILTER_PANELS else 1},
    )


@router.get("/panels/{panel_id}/chart", response_class=HTMLResponse)
def panel_chart(panel_id: str, request: Request, ccy: str = "", ley: str = "",
                state=Depends(get_state)):
    ccy_set = {c.strip().upper() for c in ccy.split(",") if c.strip()} or None
    ley_set = {s.strip().upper() for s in ley.split(",") if s.strip()} or None
    datasets = _chart_payload(panel_id, state, ccy_set, ley_set)
    title = PANELS.get(panel_id, (panel_id,))[0]
    y_label = "TNA" if panel_id == "tasa_fija" else "TIR"
    return _TEMPLATES.TemplateResponse(
        request, "fragments/panel_chart.html",
        {"title": title, "datasets_json": json_for_script(datasets), "y_label": y_label},
    )


# Bajada (subtítulo) por panel para la foto — da contexto al cliente.
_PANEL_DESC = {
    "bonares": "Soberanos en dólares · ley local y NY",
    "bopreales": "Bopreales (BCRA) · hard-dollar",
    "cer": "Pesos ajustados por inflación (CER)",
    "tasa_fija": "Pesos a tasa fija",
    "tamar": "Tasa variable TAMAR / Dual",
    "dolar_linked": "Atados al dólar oficial",
}

# Reparto del alto gráfico:tabla en la foto, por panel.
_SHARE_CHART_MULT = {"tasa_fija": 1.0}
_SHARE_CHART_MULT_DEFAULT = 0.5


@router.get("/panels/{panel_id}/share", response_class=HTMLResponse)
def panel_share(panel_id: str, request: Request, ccy: str = "", ley: str = "",
                state=Depends(get_state),
                provider=Depends(get_provider), rofex=Depends(get_rofex),
                fx=Depends(get_fx), indices=Depends(get_indices)):
    """Popup 'compartir' para WhatsApp: tabla + curva TIR×MD arriba (solo paneles
    chartables), en la MONEDA elegida en el panel (`ccy`, ej. MEP)."""
    if panel_id == "futuros":
        data = _build_futuros_share(rofex, fx, indices, state)
        resp = _TEMPLATES.TemplateResponse(
            request, "fragments/futuros_share.html",
            {"contracts_json": json_for_script(data.get("contracts", [])),
             "spot_txt": (f"{data['spot']:,.2f}" if data.get("spot") else "—"),
             "has_peso_curve": data.get("has_peso_curve", False)},
        )
        resp.headers["Cache-Control"] = "no-store"
        return resp

    today = date.today()
    try:
        settle = settlement_byma_date(today, 1).strftime("%d/%m/%Y")
    except Exception:
        settle = ""
    title, _types, full_cols = PANELS.get(panel_id, (panel_id, set(), []))
    if _types:
        cols = _share_full_cols(full_cols, panel_id)
        rows = _build_rows(panel_id, state, provider, cols_override=cols)
    else:
        cols = list(full_cols)
        rows = _build_rows(panel_id, state, provider)
    ccy_set = {c.strip().upper() for c in ccy.split(",") if c.strip()} or None
    if panel_id in CCY_FILTER_PANELS:
        if ccy_set is None:
            ccy_set = {"MEP"}
        ccy_label = " + ".join(sorted(ccy_set))
    else:
        ccy_set, ccy_label = None, ""
    if ccy_set is not None:
        rows = [r for r in rows if r.get("ccy") is None or r["ccy"] in ccy_set]
    ley_set = {s.strip().upper() for s in ley.split(",") if s.strip()} or None
    if panel_id not in LEY_FILTER_PANELS:
        ley_set = None
    if ley_set is not None:
        rows = [r for r in rows if r.get("ley") is None or r["ley"] in ley_set]
        ccy_label = (ccy_label + " · " if ccy_label else "") + \
            "Ley " + "+".join(sorted(ley_set))
    cols, rows = _drop_empty_share_cols(cols, rows)
    datasets = _chart_payload(panel_id, state, ccy_set, ley_set)
    y_label = "TNA" if panel_id == "tasa_fija" else "TIR"
    resp = _TEMPLATES.TemplateResponse(
        request, "fragments/panel_share.html",
        {"title": title, "columns": cols, "rows": rows,
         "hl_key": _HL_COL_KEY.get(panel_id),
         "chart_mult": _SHARE_CHART_MULT.get(panel_id, _SHARE_CHART_MULT_DEFAULT),
         "desc": _PANEL_DESC.get(panel_id, ""), "ccy_label": ccy_label,
         "asof": today.strftime("%d/%m/%Y"), "settle": settle,
         "badge": ("%s vs Duración" % y_label),
         "datasets_json": json_for_script(datasets), "has_chart": bool(datasets),
         "y_label": y_label},
    )
    resp.headers["Cache-Control"] = "no-store"
    return resp
