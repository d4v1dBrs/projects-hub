"""Lazy, bounded history and diagnostics for the bond workbench, never the refresh loop."""

from __future__ import annotations

import math
import threading
import time
from collections import Counter, OrderedDict
from datetime import date, datetime, timedelta, timezone

import httpx
import numpy as np

from core.infrastructure._tls import should_verify
from core.infrastructure.byma.chart_history import _unix
from core.infrastructure.byma.sources import BymaOpenSource
from core.holiday_engine import es_habil

_CACHE: OrderedDict = OrderedDict()
_LOCKS = [threading.Lock() for _ in range(16)]
_CACHE_LOCK = threading.Lock()
HISTORY_URL = BymaOpenSource.BASE + "/chart/historical-series/history"
MARKET_URL = BymaOpenSource.BASE + "/get-market-data"


def _cached(key, loader):
    # Striped locks collapse concurrent requests without an unbounded lock registry.
    with _LOCKS[hash(key) % len(_LOCKS)]:
        with _CACHE_LOCK:
            hit = _CACHE.get(key)
            if hit and hit[0] > time.monotonic():
                _CACHE.move_to_end(key)
                return hit[1]
        value, ttl = loader()
        with _CACHE_LOCK:
            _CACHE[key] = (time.monotonic() + ttl, value)
            _CACHE.move_to_end(key)
            while len(_CACHE) > 96:
                _CACHE.popitem(last=False)
        return value


def _number(value, *, zero=False):
    try:
        n = float(value)
        return n if math.isfinite(n) and (n >= 0 if zero else n > 0) else None
    except (TypeError, ValueError):
        return None


def _bar(day, close, source, *, opened=None, high=None, low=None, volume=None):
    c = _number(close)
    if not c:
        return None
    result = {"time": day.isoformat(), "value": c, "source": source}
    o, h, low = _number(opened), _number(high), _number(low)
    if o and h and low and low <= min(o, c) <= max(o, c) <= h:
        result.update(open=o, high=h, low=low, close=c)
    v = _number(volume, zero=True)
    if v is not None:
        result["volume"] = v
    return result


def history_bundle(ticker, provider):
    """3 calendar years requested, real coverage returned; OHLC is never fabricated."""
    symbol = ticker.upper().strip()
    for suffix in ("_CER", "_TAM", "_TF"):
        if symbol.endswith(suffix):
            symbol = symbol[:-len(suffix)]
            break
    today = date.today()
    try:
        cutoff = today.replace(year=today.year - 3)
    except ValueError:
        cutoff = today.replace(year=today.year - 3, day=28)

    def load():
        merged, errors = {}, []
        # Local legacy closes only fill holes; API bars take precedence by date.
        for day, close in provider._load_history().get(symbol, {}).items():
            if cutoff <= day <= today:
                bar = _bar(day, close, "CSV local")
                if bar:
                    merged[bar["time"]] = bar
        raw_data912 = provider.fetch_bond_history(symbol)
        for raw in raw_data912:
            try:
                day = date.fromisoformat(raw["date"][:10])
            except (KeyError, TypeError, ValueError):
                continue
            if cutoff <= day <= today:
                bar = _bar(day, raw.get("c"), "Data912", opened=raw.get("o"),
                           high=raw.get("h"), low=raw.get("l"), volume=raw.get("v"))
                if bar:
                    merged[bar["time"]] = bar
        # BYMA adds missing dates and provides independent observed OHLCV. The
        # primary market series wins on overlaps; never mix fields from two bars.
        request_params = {"symbol": f"{symbol} 24HS", "resolution": "D",
                          "from": _unix(cutoff), "to": _unix(today + timedelta(days=1))}
        payload = {}
        try:
            with httpx.Client(timeout=8.0, verify=should_verify(HISTORY_URL)) as client:
                response = client.get(HISTORY_URL, params=request_params,
                                      headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
                response.raise_for_status()
                payload = response.json()
            if not isinstance(payload, dict) or payload.get("s") != "ok":
                payload = {}
                errors.append("BYMA no devolvio una serie para esta especie.")
        except (httpx.HTTPError, ValueError):
            errors.append("BYMA no disponible; se conserva la cobertura de respaldo.")
        for i, timestamp in enumerate(payload.get("t", [])):
            def field(key):
                values = payload.get(key) or []
                return values[i] if i < len(values) else None

            try:
                day = datetime.fromtimestamp(int(timestamp), timezone.utc).date()
            except (ValueError, TypeError, OverflowError, OSError):
                continue
            if cutoff <= day <= today:
                bar = _bar(day, field("c"), "BYMA Open", opened=field("o"),
                           high=field("h"), low=field("l"), volume=field("v"))
                if bar:
                    merged[bar["time"]] = bar
        bars = sorted(merged.values(), key=lambda b: b["time"])
        source_counts = dict(Counter(b["source"] for b in bars))
        value = {"ticker": symbol, "settlement": "24hs", "bars": bars,
                 "requested_from": cutoff.isoformat(), "requested_to": today.isoformat(),
                 "from": bars[0]["time"] if bars else None,
                 "to": bars[-1]["time"] if bars else None,
                 "count": len(bars), "sources": source_counts,
                 "ohlc_count": sum("open" in b for b in bars),
                 "volume_count": sum("volume" in b for b in bars),
                 "fetched_at": datetime.now(timezone.utc).isoformat(),
                 "endpoint": HISTORY_URL, "request": request_params, "warnings": errors,
                 "methodology": "Precios sin ajustar por cupones, amortizaciones o inflacion. "
                    "Retornos de precio, no retorno total. Volumen en unidades del proveedor, "
                    "sin equipararlo a VN. Historico de 24hs incluso al seleccionar CI."}
        value["quant"] = price_statistics(bars)
        return value, 1800 if bars else 30

    return _cached(("history", symbol, today), load)


def price_statistics(bars):
    """Daily returns require consecutive BYMA sessions, not adjacent stored rows."""
    empty = {"observations": 0, "returns": [], "volatility": [], "drawdown": [], "histogram": []}
    if len(bars) < 3:
        return empty
    returns, drawdown, volatility = [], [], []
    peak = bars[0]["value"]
    for i, bar in enumerate(bars):
        peak = max(peak, bar["value"])
        drawdown.append({"time": bar["time"], "value": (bar["value"] / peak - 1) * 100})
        day = date.fromisoformat(bar["time"])
        previous = date.fromisoformat(bars[i-1]["time"]) if i else day
        gap = (day - previous).days
        consecutive = (i and gap > 0 and es_habil(previous) and es_habil(day) and
                       not any(es_habil(previous + timedelta(days=n)) for n in range(1, gap)))
        if consecutive:
            returns.append({"time": bar["time"], "from": bars[i-1]["time"],
                            "value": (bar["value"] / bars[i-1]["value"] - 1) * 100})
            if len(returns) >= 20:
                values = [r["value"] for r in returns[-20:]]
                volatility.append({"time": bar["time"], "value": float(np.std(values, ddof=1) * np.sqrt(252))})
    if len(returns) < 2:
        return {**empty, "drawdown": drawdown}
    a = np.array([r["value"] for r in returns])
    q = float(np.quantile(a, .05))
    counts, edges = np.histogram(a, bins=min(24, max(4, int(np.sqrt(len(a))))))
    return {"observations": len(a), "price_return_pct": (bars[-1]["value"] / bars[0]["value"] - 1) * 100,
            "annual_vol_pct": float(np.std(a, ddof=1) * np.sqrt(252)),
            "mean_daily_pct": float(np.mean(a)), "var95_pct": max(0.0, -q),
            "cvar95_pct": max(0.0, -float(np.mean(a[a <= q]))),
            "max_drawdown_pct": min(d["value"] for d in drawdown),
            "best_day_pct": float(a.max()), "worst_day_pct": float(a.min()),
            "positive_days_pct": float(np.mean(a > 0) * 100),
            "large_moves": [r for r in returns if abs(r["value"]) >= 20],
            "returns": returns, "volatility": volatility, "drawdown": drawdown,
            "histogram": [{"from": float(edges[i]), "to": float(edges[i+1]), "count": int(n)}
                          for i, n in enumerate(counts)],
            "excluded_intervals": len(bars) - 1 - len(returns),
            "methodology": "Retornos simples entre ruedas BYMA consecutivas; se excluyen "
                "intervalos con ruedas faltantes y cierres fuera de calendario. "
                "Volatilidad muestral x raiz(252); movil de 20 observaciones. "
                "VaR/CVaR historicos 95%, una observacion, expresados como perdida positiva. "
                "Los cortes de cupon y cambios de fuente pueden distorsionar estas medidas."}


def compare_histories(left, right):
    a = {(r["from"], r["time"]): r["value"] for r in left["quant"]["returns"]}
    b = {(r["from"], r["time"]): r["value"] for r in right["quant"]["returns"]}
    common = sorted(a.keys() & b.keys())
    correlation = beta = None
    if len(common) >= 20:
        x, y = np.array([a[d] for d in common]), np.array([b[d] for d in common])
        if np.std(x) > 0 and np.std(y) > 0:
            correlation = float(np.corrcoef(x, y)[0, 1])
            beta = float(np.cov(x, y, ddof=1)[0, 1] / np.var(y, ddof=1))
    return {"ticker": right["ticker"], "observations": len(common),
            "correlation": correlation, "beta": beta,
            "from": common[0][0] if common else None, "to": common[-1][1] if common else None}


FIELD_NOTES = {
    "symbol": ("Especie", "ticker"), "trade": ("Ultimo operado", "precio"),
    "bidPrice": ("Mejor demanda", "precio"), "offerPrice": ("Mejor oferta", "precio"),
    "volumeAmount": ("Monto negociado", "importe; no nominales"),
    "numberOfOrders": ("Operaciones informadas", "cantidad"),
    "imbalance": ("Variacion respecto del cierre; no desequilibrio del libro", "fraccion"),
    "settlementType": ("Liquidacion: 1=CI, 2=24hs", "codigo"),
    "closingPrice": ("Cierre", "precio"), "previousClosingPrice": ("Cierre previo", "precio"),
}


def raw_market(ticker, lag):
    """Fixed public endpoint; only expose rows of the catalog-validated instrument."""
    def load():
        rows, attempts = [], []
        for flag in ("btnTitPublicos", "btnLetras"):
            body = {"excludeZeroPxAndQty": False, "page_number": 1, "page_size": 5000,
                    flag: True, "T0": True, "T1": True}
            status = None
            try:
                with httpx.Client(timeout=6.0, verify=should_verify(MARKET_URL)) as client:
                    response = client.post(MARKET_URL, json=body,
                                           headers=BymaOpenSource()._headers("renta-fija"))
                    status = response.status_code
                    response.raise_for_status()
                    payload = response.json()
                data = payload.get("data", []) if isinstance(payload, dict) else payload
                if isinstance(data, list):
                    rows = [r for r in data if isinstance(r, dict) and
                            str(r.get("symbol", "")).upper().strip() == ticker and
                            str(r.get("settlementType", "")) == ("1" if lag == 0 else "2")]
                attempts.append({"body": body, "status": status, "matching_rows": len(rows)})
            except (httpx.HTTPError, ValueError):
                attempts.append({"body": body, "status": status, "matching_rows": 0})
            if rows:
                break
        observed = rows[0] if rows else {key: None for key in FIELD_NOTES}
        fields = [{"field": k, "value": v, "description": FIELD_NOTES.get(k, ("Campo sin mapear", "no confirmada"))[0],
                   "unit": FIELD_NOTES.get(k, ("", "no confirmada"))[1],
                   "available": v is not None} for k, v in observed.items()]
        result = {"endpoint": MARKET_URL, "method": "POST", "attempts": attempts,
                  "fetched_at": datetime.now(timezone.utc).isoformat(), "ticker": ticker,
                  "settlement": "CI" if lag == 0 else "24hs", "fields": fields, "raw": rows,
                  "message": "BYMA Open: demora publicada de 20 minutos. Sin garantia de puntas ejecutables."
                    if rows else "BYMA Open no entrego una fila para esta especie/plazo. "
                    "El precio del monitor puede provenir de Data912. No se inventan campos faltantes."}
        return result, 60 if rows else 30

    return _cached(("raw", ticker, lag), load)
