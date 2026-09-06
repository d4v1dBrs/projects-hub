"""Backend del popup de detalle de bono (tabs Detalles + Chart + Calculadora).

Dos endpoints:
  - get_bond_detail(ticker)   → snapshot estática: Excel fields + cashflows
                                futuros + métricas vivas (TIR/MD/V.Téc/etc.).
                                Sirve para tab "Detalles" y para inicializar
                                la tab "Calculadora".
  - calculate(ticker, ...)    → recomputa todas las métricas dado un precio
                                (clean|dirty) o un TIR objetivo. Sirve para la
                                tab "Calculadora" cada vez que el usuario
                                tipea un valor.

Reusa los singletons del refresh loop (provider/repo/fx/bcra) si se pasan;
sino instancia copias propias — un detalle por click no justifica overhead
de coordinación, y el caching class-level absorbe la duplicación.
"""

from __future__ import annotations

import logging
import math
from datetime import date
from typing import Any, Dict, List, Optional

from core.domain.models import Instrument, MarketSnapshot
from core.domain.currency import position_currency
from core.domain.clock import today as _domain_today
from core.domain.services import FinancialEngine, _is_cer_type
from core.holiday_engine import settlement_byma

logger = logging.getLogger(__name__)


def _iso(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d else None


def _safe(v) -> Any:
    """JSON-safe: NaN/Inf → None."""
    if v is None:
        return None
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return v


def _is_usd_quoted(instrument: Instrument) -> bool:
    """¿El precio de esta especie cotiza en USD (no en pesos)?"""
    return position_currency(instrument.instrument_type, instrument.ticker) == "USD"


_TAMAR_TYPES = frozenset({"PURO", "DUAL", "DUAL_CER_TAMAR"})

_VALID_LEGS = frozenset({"TF", "TAM", "CER"})


def _nominal_tna(instrument, tea):
    """TNA "Tir Nominal" alineada al informe IAMC, seleccionada por tipo:
    - bonos CON cupón (hard-dollar/ON/soberanos/tasa fija): m = frecuencia de pago
      (semestral → 2) vía `tea_to_tna_freq` — la convención del informe.
    - TAMAR/DUAL y capitalizables peso (LECAP/BONCAP/LECER): m = 12 (mensual), que
      es lo que IAMC rotula como 'Tasa Nominal' para esos.
    (El `tea_to_tna` base-365 que se mostraba antes sub-representaba el nominal del
    cupón → daba la 'Tir Nominal' sistemáticamente baja vs el informe.)"""
    if tea is None:
        return None
    itype = (instrument.instrument_type or "").upper().strip()
    if itype in _TAMAR_TYPES or any(t in itype for t in ("LECAP", "BONCAP", "LECER")):
        return FinancialEngine.tea_to_tna_monthly(tea)
    freq = getattr(instrument, "payment_frequency", 2) or 2
    return FinancialEngine.tea_to_tna_freq(tea, freq)


class _ZeroTamar:
    """Indices provider stub que fuerza TAMAR=0 para el leg de tasa fija."""
    _cache_tamar: dict = {}

    def get_tamar(self, d=None):
        return 0.0


def _parse_leg_ticker(ticker_u: str):
    """'TTJ26_TF' → ('TTJ26', 'TF').  Sin sufijo reconocido → (ticker, None)."""
    if "_" in ticker_u:
        base, suffix = ticker_u.rsplit("_", 1)
        if suffix in _VALID_LEGS:
            return base, suffix
    return ticker_u, None


def _apply_leg(instrument: Instrument, leg: Optional[str]):
    """Transforma el instrumento según el leg solicitado.

    - TAM: clona como PURO (sin floor) — TAMAR puro.
    - TF:  mantiene el instrumento DUAL pero devuelve _ZeroTamar como indices
           override, de modo que max(TAMAR=0, floor) = floor siempre.
    - CER: sin transformación (devuelve el instrumento original).

    Retorna (instrument_efectivo, indices_override_o_None).
    """
    if leg is None:
        return instrument, None
    if leg == "TAM":
        return instrument.model_copy(update={
            "instrument_type": "PURO", "floor_rate_monthly": None,
        }), None
    if leg == "TF":
        return instrument, _ZeroTamar()
    return instrument, None


def _resolve_instrument_and_leg(ticker: str, repo, indices):
    """Resuelve un ticker a (base_ticker, instrumento_efectivo, indices_efectivos).

    Da prioridad a instrumentos standalone (ej. TXMJ8_CER en la hoja CER) sobre
    el parsing de leg (sufijos _TAM/_TF). Aplica el leg y, si corresponde, usa el
    indices_override (ej. _ZeroTamar para la pata TF). None si el ticker no existe.
    """
    ticker_u = ticker.upper().strip()
    if repo.get_instrument_by_ticker(ticker_u) is not None:
        base_ticker, leg = ticker_u, None
    else:
        base_ticker, leg = _parse_leg_ticker(ticker_u)
    instrument = repo.get_instrument_by_ticker(base_ticker)
    if instrument is None:
        return None
    instrument, indices_override = _apply_leg(instrument, leg)
    indices_eff = indices_override if indices_override is not None else indices
    return base_ticker, instrument, indices_eff, leg, ticker_u


def _cupon_label(instrument: Instrument) -> str:
    """Etiqueta legible del cupón para mostrar en Descripción Técnica."""
    itype = (instrument.instrument_type or "").upper().strip()
    sp = instrument.spread_rate
    floor = instrument.floor_rate_monthly
    cer_sp = instrument.cer_spread

    if itype == "PURO":
        return f"TAMAR + {(sp or 0)*100:.3f}%"
    if itype == "DUAL":
        sp_part = f"TAMAR + {(sp or 0)*100:.3f}%"
        floor_part = f"floor {(floor or 0)*100:.2f}% mensual" if floor else "sin floor"
        return f"max({sp_part}, {floor_part})"
    if itype == "DUAL_CER_TAMAR":
        return f"max(TAMAR + {(sp or 0)*100:.3f}%, CER + {(cer_sp or 0)*100:.3f}%)"
    if any(t in itype for t in ("LECAP", "BONCAP")):
        tem = getattr(instrument, "floor_rate_monthly", None)
        if tem:
            return f"Capitalizable TEM {tem * 100:.3f}% mensual"
        return "Capitalizable (TEM licitación)"
    if any(t in itype for t in ("LECER",)):
        return "CER ajustado (zero cupón)"
    if any(t in itype for t in ("BONCER", "CER", "CON CUPON", "STEP-UP")):
        return "CER ajustado"
    if "DOLAR" in itype:
        return "Dólar Linked"
    if itype in ("BONAR", "GLOBAL", "BOPREAL"):
        # Backear el cupón anual desde el próximo cashflow con interés:
        # annual_rate = next.interest × freq / residual_at_settlement.
        # Aproximado pero útil — soberanos AR pagan semestral.
        return _infer_coupon_rate_label(instrument)
    return "—"


def _infer_coupon_rate_label(instrument: Instrument) -> str:
    """Backea el cupón anual % desde los cashflows. Útil para soberanos
    BONAR/GLOBAL/BOPREAL — el Instrument no carga el cupón explícito pero
    se puede recuperar desde el próximo flow con interés."""
    cfs = sorted(instrument.cashflows or [], key=lambda c: c.date)
    today = _domain_today()
    next_cf = next((c for c in cfs if c.date >= today and c.interest > 0), None)
    if next_cf is None:
        return "Tasa fija"
    freq = getattr(instrument, "payment_frequency", 2) or 2
    # Residual al settlement = suma de futuros amorts.
    future_amort = sum(c.amortization for c in cfs if c.date >= today)
    residual = future_amort if future_amort > 0 else 100.0
    if residual <= 0:
        return "Tasa fija"
    annual_pct = next_cf.interest * freq / residual * 100.0
    return f"Tasa fija {annual_pct:.3f}% anual"


def _bond_metadata(instrument: Instrument, *, leg: Optional[str] = None) -> Dict[str, Any]:
    """Campos descriptivos derivados del Instrument para tab Detalles.

    CER base/lag se incluyen sólo para bonos CER-adjusted (la columna existe
    en el modelo con default 10/None pero no tiene sentido en BONAR/GLOBAL/
    BOPREAL/TASA_FIJA/DL/TAMAR PURO). Mismo criterio para spread TAMAR/CER
    y floor mensual — sólo se exponen para los tipos que realmente los usan.

    `leg` permite sobrescribir la vista cuando se abre el detalle de un leg
    específico de un bono DUAL (TF / TAM / CER).
    """
    is_usd = _is_usd_quoted(instrument)
    itype = (instrument.instrument_type or "").upper().strip()
    is_cer = _is_cer_type(itype)
    is_dual_cer = itype == "DUAL_CER_TAMAR"
    is_tamar_family = itype in _TAMAR_TYPES
    is_dual = itype == "DUAL"

    # Leg TF: el floor actúa como tasa fija — no es TAMAR family a efectos de display.
    if leg == "TF":
        is_tamar_family = False
        floor = instrument.floor_rate_monthly
        cupon = (
            f"Tasa fija (floor) {(floor or 0) * 100:.3f}% mensual"
            if floor
            else "Tasa fija (leg TF)"
        )
    else:
        cupon = _cupon_label(instrument)

    meta: Dict[str, Any] = {
        "ticker": instrument.ticker,
        "short_name": instrument.short_name,
        "instrument_type": instrument.instrument_type,
        "category": instrument.category,
        "currency": "USD" if is_usd else "ARS",
        "fecha_emision": _iso(instrument.emission_date),
        "fecha_vencimiento": _iso(instrument.maturity_date),
        "payment_frequency": instrument.payment_frequency,
        "cupon": cupon,
        "is_tamar_family": is_tamar_family,
        # CER puro (no DUAL_CER): habilita el cajón "Proyección CER" del popup.
        "is_cer_proj": is_cer,
    }
    # CER fields: bonos CER + DUAL_CER_TAMAR (que usa cer_base como rail CER).
    if is_cer or is_dual_cer:
        meta["cer_base"] = _safe(instrument.cer_base)
        meta["cer_lag"] = instrument.cer_lag
    if is_dual_cer:
        meta["cer_spread"] = _safe(instrument.cer_spread)
    # TAMAR spread aplica a PURO/DUAL/DUAL_CER_TAMAR.
    if is_tamar_family:
        meta["spread_rate"] = _safe(instrument.spread_rate)
    # Floor mensual: DUAL con piso fijo, y también el leg TF.
    if is_dual or leg == "TF":
        meta["floor_rate_monthly"] = _safe(instrument.floor_rate_monthly)
    return meta


def _cashflows_all(instrument: Instrument, ref_date: date,
                   indices=None, tamar_forecast: Optional[float] = None) -> List[Dict[str, Any]]:
    """Lista completa de cashflows (pasados + futuros), sorted ascending.

    Cada row trae:
      - vr_cartera: residual nominal DESPUÉS de la amortización del row
        (inicio = sum de TODAS las amortizaciones presentes en la lista —
        soberanos mid-amort sólo cargan futuros en Excel, en cuyo caso el
        VR arranca en el outstanding actual, no en 100).
      - is_past: True si la fecha ya pasó.
      - is_next: True si es el próximo cupón con interés (= cupón corriente,
        el que se marca en negrita en el modelo IAMC).

    Para bonos TAMAR-family (PURO/DUAL/DUAL_CER_TAMAR) sin cashflows en Excel
    (el payback es dinámico, depende de TAMAR futura), sintetiza 2 filas:
    anchor en emisión (VR=100, sin pago) + maturity (VR=0, amort=payoff
    proyectado). Permite que el popup muestre algo equivalente al modelo
    IAMC para estos bonos.
    """
    out: List[Dict[str, Any]] = []
    cfs = sorted(instrument.cashflows or [], key=lambda c: c.date)

    # TAMAR-family bullets sin Excel cashflows: sintetizar 2 filas a partir
    # del payback proyectado a vencimiento.
    if not cfs:
        itype = (instrument.instrument_type or "").upper().strip()
        if (itype in _TAMAR_TYPES and indices is not None
                and instrument.emission_date and instrument.maturity_date):
            payoff = FinancialEngine.projected_payoff(
                instrument, indices, tamar_forecast=tamar_forecast, ref_date=ref_date,
            )
            if payoff is not None and payoff > 0:
                mat_past = instrument.maturity_date < ref_date
                return [
                    {
                        "date": instrument.emission_date.isoformat(),
                        "vr_cartera": 100.0,
                        "amortization": 0.0,
                        "interest": 0.0,
                        "total": 0.0,
                        "label": "Renta",  # anchor de inicio de accrual
                        "is_past": True,
                        "is_next": False,
                        "is_synthetic": True,
                    },
                    {
                        "date": instrument.maturity_date.isoformat(),
                        "vr_cartera": 0.0,
                        "amortization": _safe(payoff),
                        "interest": 0.0,  # bullet capitalizable: todo en amort
                        "total": _safe(payoff),
                        "label": "Renta + Amortización",
                        "is_past": mat_past,
                        "is_next": not mat_past,
                        "is_synthetic": True,
                    },
                ]
        return out

    # Inicio del VR = total amortizado en TODA la lista. Para AO27 con schedule
    # completo: 100. Para AL29D con sólo futuros: 70 (residual actual).
    total_amort = sum(c.amortization for c in cfs)
    vr_running = total_amort if total_amort > 0 else 100.0
    # Próximo cupón con interés > 0 (el que está accruing).
    next_with_interest = next(
        (c for c in cfs if c.date > ref_date and c.interest > 0), None,  # ex-cupón: > settle
    )
    next_date = next_with_interest.date if next_with_interest else None

    for cf in cfs:
        vr_after = max(vr_running - cf.amortization, 0.0)
        # Label "Obs. Prox. Pago" — qué tipo de evento es este row.
        if cf.amortization > 0 and cf.interest > 0:
            label = "Renta + Amortización"
        elif cf.amortization > 0:
            label = "Amortización"
        elif cf.interest > 0:
            label = "Renta"
        else:
            label = "—"
        out.append({
            "date": cf.date.isoformat(),
            "vr_cartera": _safe(vr_after),
            "amortization": _safe(cf.amortization),
            "interest": _safe(cf.interest),
            "total": _safe(cf.amortization + cf.interest),
            "label": label,
            "is_past": cf.date <= ref_date,   # ex-cupón: flujo en la liquidación = ya pagado
            "is_next": (next_date is not None and cf.date == next_date),
        })
        vr_running = vr_after
    return out


def _resolve_ref(settlement_lag: int) -> date:
    """T+0 (lag=0) = today, T+1 (lag=1) = next business day BYMA. Cualquier
    otro lag positivo cae al siguiente hábil correspondiente."""
    if settlement_lag <= 0:
        return _domain_today()
    return settlement_byma(_domain_today().strftime("%Y-%m-%d"), lag=settlement_lag).date()


def _live_metrics(
    snapshot: MarketSnapshot, indices, fx, ref_date: date,
    *, tamar_forecast: Optional[float] = None,
) -> Dict[str, Any]:
    """Bundle completo de métricas (TIR/MD/V.Téc/...) para un snapshot.
    Si snapshot.price viene como None, sólo se devuelven las que no dependen
    del precio (accrued, residual, etc.).

    `ref_date` se usa como settle date (T+0 o T+1) para TODOS los cálculos —
    accrued, residual, TIR, MD, etc. — para mantener consistencia interna
    (sin esto, TIR podía estar en T+1 y V.Téc en T+0).

    `tamar_forecast` (decimal, ej 0.20 = 20%): override de la TAMAR proyectada
    para el resto del plazo. Sólo aplica a TAMAR PURO/DUAL/DUAL_CER_TAMAR.
    Default None → usa la última TAMAR publicada por BCRA.
    """
    inst = snapshot.instrument
    itype = (inst.instrument_type or "").upper().strip()
    is_tamar_family = itype in _TAMAR_TYPES

    tir = FinancialEngine.calculate_tir(
        snapshot, indices_provider=indices, fx_provider=fx, settle_date=ref_date,
        tamar_forecast=tamar_forecast,
    )
    vtec = FinancialEngine.calculate_technical_value(
        # settle_lag=0: `ref_date` YA es el settle (T+0/T+1) resuelto arriba, igual que
        # en calculate_tir; sin esto, calculate_technical_value re-aplica settlement_byma
        # (settle_lag=1 por default) → doble lag en la V.Téc/paridad del popup (+0,26% en CI).
        snapshot, indices_provider=indices, fx_provider=fx, ref_date=ref_date, settle_lag=0,
    )
    md = (FinancialEngine.calculate_duration(snapshot, tir, settle_date=ref_date)
          if tir is not None else None)
    parity = (snapshot.price / vtec) if (vtec and snapshot.price) else None

    accrued = FinancialEngine.accrued_interest(inst, ref_date)
    residual = FinancialEngine.residual_nominal(inst, ref_date)
    days_accrued = FinancialEngine.days_since_last_coupon(inst, ref_date)
    cy = FinancialEngine.current_yield(inst, snapshot.price, ref_date) if snapshot.price else None
    dv01 = FinancialEngine.dv01(inst, tir, ref_date) if tir is not None else None
    conv = FinancialEngine.convexity(inst, tir, ref_date) if tir is not None else None

    term = None
    if inst.maturity_date and inst.maturity_date > ref_date:
        term = (inst.maturity_date - ref_date).days / 365.25

    tea = tir
    tna = FinancialEngine.tea_to_tna(tea) if tea is not None else None
    tna_mensual = FinancialEngine.tea_to_tna_monthly(tea) if tea is not None else None
    tem = FinancialEngine.tea_to_tem(tea) if tea is not None else None
    tem_360 = FinancialEngine.tea_to_tem_m12(tea) if tea is not None else None

    # Fechas del cupón corriente. Para zero-coupon (LECAP/LECER/BONCER ZC) y
    # TAMAR bullets el bond no tiene cupón con interés explícito > 0, así que
    # _period_bounds devuelve None. Fallback: el "período corriente" arranca en
    # emission y termina en maturity (matchea la convención del modelo de referencia
    # para bullets — "Último cupón = emisión, Próximo = vto").
    bounds = FinancialEngine._period_bounds(inst, ref_date)
    if bounds:
        last_coupon = _iso(bounds[0])
        next_coupon = _iso(bounds[1].date)
    else:
        last_coupon = _iso(inst.emission_date)
        next_coupon = _iso(inst.maturity_date)

    # Spread de mercado (sólo TAMAR family): TIR_decimal − TAMAR proyectado.
    # Equivale a "qué tan por encima/debajo de TAMAR está la TIR implícita".
    spread_mercado = None
    tamar_used = None
    if is_tamar_family and indices is not None:
        if tamar_forecast is not None:
            tamar_used = float(tamar_forecast)
        else:
            t = indices.get_tamar()  # TNA % publicada por BCRA
            tamar_used = (t / 100.0) if t is not None else None
        if tea is not None and tamar_used is not None:
            spread_mercado = tea - tamar_used

    # Clean / Dirty: el precio cotizado se asume DIRTY (con intereses corridos).
    # Para CER/DL/TAMAR la convención de "clean" no aplica de la misma forma,
    # pero el accrued lineal sigue siendo útil como referencia.
    price_dirty = snapshot.price
    price_clean = (price_dirty - accrued) if (price_dirty is not None) else None
    paridad_clean = (price_clean / residual) if (price_clean is not None and residual) else None

    return {
        "tir": _safe(tea),
        "tna": _safe(tna),
        "tna_nominal": _safe(_nominal_tna(inst, tea)),
        "tna_mensual": _safe(tna_mensual),
        "tem": _safe(tem),
        "tem_360": _safe(tem_360),
        "duration": _safe(md),
        "technical_value": _safe(vtec),
        "parity": _safe(parity),
        "parity_clean": _safe(paridad_clean),
        "accrued_interest": _safe(accrued),
        "days_accrued": days_accrued,
        "residual_nominal": _safe(residual),
        "current_yield": _safe(cy),
        "dv01": _safe(dv01),
        "convexity": _safe(conv),
        "term_to_maturity": _safe(term),
        "price_dirty": _safe(price_dirty),
        "price_clean": _safe(price_clean),
        "spread_mercado": _safe(spread_mercado),
        "tamar_forecast_used": _safe(tamar_used),
        "last_coupon_date": last_coupon,
        "next_coupon_date": next_coupon,
    }


def get_bond_detail(
    ticker: str, repo, provider, indices, fx,
    *, historical_supported: Optional[set] = None,
    settlement_lag: int = 1,
    tamar_forecast: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Detalle completo de un ticker para popular el popup en su apertura.

    `historical_supported` es la frozenset HISTORICAL_SUPPORTED_TICKERS del
    server — la pasamos para que el frontend sepa si renderizar la tab Chart.

    `settlement_lag` controla la fecha de referencia para todas las métricas:
    1 (default) = T+1 (próximo hábil BYMA) — convención de mercado para AR
    bond pricing. 0 = T+0 (hoy) — útil para análisis teórico.
    """
    resolved = _resolve_instrument_and_leg(ticker, repo, indices)
    if resolved is None:
        return None
    base_ticker, instrument, indices_eff, leg, ticker_u = resolved

    ref_date = _resolve_ref(settlement_lag)
    snapshots = provider.fetch_snapshots([base_ticker])
    snapshot = snapshots.get(base_ticker)
    if snapshot is None:
        snapshot = MarketSnapshot(
            instrument=instrument, price=None, last_update=ref_date,
        )
    else:
        snapshot.instrument = instrument

    fx_rate = None
    if fx is not None:
        try:
            fx_rate = fx.get_mayorista_venta()
        except Exception:  # noqa: BLE001 — FX externo, degradar a None
            fx_rate = None

    metrics = _live_metrics(snapshot, indices_eff, fx, ref_date, tamar_forecast=tamar_forecast)
    market = {
        "price": _safe(snapshot.price),
        "bid": _safe(snapshot.bid),
        "ask": _safe(snapshot.ask),
        "volume": _safe(snapshot.volume),
        "change_pct": _safe(snapshot.change_pct),
        "fx_mayorista_venta": _safe(fx_rate),
    }

    chart_supported = (
        historical_supported is not None and base_ticker in historical_supported
    )

    meta = _bond_metadata(instrument, leg=leg)
    meta["ticker"] = ticker_u  # mostrar el ticker con sufijo (ej. TTJ26_TF)

    return {
        "ticker": ticker_u,
        "meta": meta,
        "cashflows": _cashflows_all(instrument, ref_date, indices=indices_eff,
                                    tamar_forecast=tamar_forecast),
        "market": market,
        "metrics": metrics,
        "chart_supported": chart_supported,
        "settlement_lag": settlement_lag,
        "settle_date": ref_date.isoformat(),
    }


def calculate(
    ticker: str, repo, provider, indices, fx,
    *, mode: str, price: Optional[float] = None,
    price_mode: str = "dirty", tir: Optional[float] = None,
    settlement_lag: int = 1,
    tamar_forecast: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Recalcula todas las métricas dado un precio (clean/dirty) o un TIR.

    mode:
      - "from_price": usa `price` (interpretado según `price_mode`).
      - "from_tir":   usa `tir` (decimal: 0.30 = 30%).

    `settlement_lag` controla la fecha de referencia (T+0 vs T+1).

    Devuelve el bundle de métricas + el precio implícito (clean+dirty) y el TIR.
    None si el ticker no existe.
    """
    resolved = _resolve_instrument_and_leg(ticker, repo, indices)
    if resolved is None:
        return None
    base_ticker, instrument, indices_eff, leg, ticker_u = resolved

    ref_date = _resolve_ref(settlement_lag)

    # Snapshot mínimo (no precisamos quotes live — el usuario ya provee el precio).
    snapshots = provider.fetch_snapshots([base_ticker])
    snapshot = snapshots.get(base_ticker)
    if snapshot is None:
        snapshot = MarketSnapshot(
            instrument=instrument, price=None, last_update=ref_date,
        )
    else:
        snapshot.instrument = instrument

    accrued = FinancialEngine.accrued_interest(instrument, ref_date)
    residual = FinancialEngine.residual_nominal(instrument, ref_date)

    # Resolver (price_dirty, tir_decimal) según el modo.
    if mode == "from_price":
        if price is None or price <= 0:
            return None
        if price_mode == "clean":
            price_dirty = price + accrued
            price_clean = price
        else:
            price_dirty = price
            price_clean = price - accrued
        tir_calc = FinancialEngine.tir_from_price(
            snapshot, price_dirty, indices_provider=indices_eff, fx_provider=fx,
            settle_date=ref_date, tamar_forecast=tamar_forecast,
        )
    elif mode == "from_tir":
        if tir is None:
            return None
        price_dirty = FinancialEngine.price_from_tir(
            snapshot, tir, indices_provider=indices_eff, fx_provider=fx,
            settle_date=ref_date, tamar_forecast=tamar_forecast,
        )
        price_clean = (price_dirty - accrued) if price_dirty is not None else None
        tir_calc = tir
    else:
        return None

    # Override del snapshot con el precio resuelto para las métricas downstream.
    snap_calc = snapshot.model_copy(update={"price": price_dirty})
    out = _live_metrics(snap_calc, indices_eff, fx, ref_date, tamar_forecast=tamar_forecast)
    out["tir"] = _safe(tir_calc)
    if tir_calc is not None:
        out["tna"] = _safe(FinancialEngine.tea_to_tna(tir_calc))
        out["tna_nominal"] = _safe(_nominal_tna(instrument, tir_calc))
        out["tna_mensual"] = _safe(FinancialEngine.tea_to_tna_monthly(tir_calc))
        out["tem"] = _safe(FinancialEngine.tea_to_tem(tir_calc))
        out["tem_360"] = _safe(FinancialEngine.tea_to_tem_m12(tir_calc))
        out["duration"] = _safe(FinancialEngine.calculate_duration(snap_calc, tir_calc,
                                                                    settle_date=ref_date))
        out["dv01"] = _safe(FinancialEngine.dv01(instrument, tir_calc, ref_date))
        out["convexity"] = _safe(FinancialEngine.convexity(instrument, tir_calc, ref_date))
    out["price_dirty"] = _safe(price_dirty)
    out["price_clean"] = _safe(price_clean)
    # Paridad clean = clean / residual (% del nominal vivo).
    out["parity_clean"] = _safe(
        (price_clean / residual) if (price_clean is not None and residual) else None
    )
    out["accrued_interest"] = _safe(accrued)
    out["residual_nominal"] = _safe(residual)
    out["settlement_lag"] = settlement_lag
    out["settle_date"] = ref_date.isoformat()
    return out


def get_horizon_matrix(
    ticker: str, repo, provider, indices, fx,
    *, settlement_lag: int = 1,
    tamar_forecast: Optional[float] = None
) -> Optional[Dict[str, Any]]:
    """Calcula la matriz de retornos esperados (Horizon Analysis).
    Evalúa 5 horizontes temporales (meses) x 6 shifts de TIR (bps).
    Usa aproximación estándar (Taylor expansion) de Carry + Price Effect
    para velocidad, sin requerir simulaciones completas de índices futuros.
    """
    resolved = _resolve_instrument_and_leg(ticker, repo, indices)
    if resolved is None:
        return None
    base_ticker, instrument, indices_eff, leg, ticker_u = resolved

    ref_date = _resolve_ref(settlement_lag)
    snapshots = provider.fetch_snapshots([base_ticker])
    snapshot = snapshots.get(base_ticker)
    if snapshot is None or snapshot.price is None:
        return None

    snapshot.instrument = instrument

    # Base TIR and Risk Metrics
    base_tir = FinancialEngine.calculate_tir(
        snapshot, indices_provider=indices_eff, fx_provider=fx,
        settle_date=ref_date, tamar_forecast=tamar_forecast
    )
    if base_tir is None:
        return None

    duration = FinancialEngine.calculate_duration(snapshot, base_tir, settle_date=ref_date) or 0.0
    convexity = FinancialEngine.convexity(instrument, base_tir, ref_date) or 0.0

    months = [1, 3, 6, 9, 12]
    shifts_bps = [-200, -100, 0, 100, 200, 300]

    matrix = []

    for shift in shifts_bps:
        row = {"shift": shift, "cells": []}
        shift_pct = shift / 10000.0

        # Efecto precio aproximado: -MD * dY + 0.5 * Convexity * dY^2
        price_effect = (-duration * shift_pct) + (0.5 * convexity * (shift_pct ** 2))

        for m in months:
            t = m / 12.0
            carry = base_tir * t

            # Retorno total = Carry asumiendo TIR constante + Efecto de cambio de TIR
            # Si el bono vence antes del horizonte, el retorno de precio al vto es siempre 0 (pulveriza la MD).
            # Para simplificar en esta vista institucional rápida, asumimos la aproximación lineal:
            total_return = (carry + price_effect) * 100.0

            # Color HSL (Red a Green): Rango esperado ~ -15% a +15%
            # hue = 0 (Rojo) a 120 (Verde)
            hue = min(max((total_return + 10) * 4.8, 0), 120)
            lightness = 25 + min(abs(total_return), 20)
            text_color = "white" if hue < 30 or hue > 90 else "#1e293b"

            row["cells"].append({
                "month": m,
                "value": total_return,
                "style": f"background-color: hsl({hue:.0f}, 80%, {lightness:.0f}%); color: {text_color};"
            })
        matrix.append(row)

    return {
        "ticker": ticker_u,
        "base_tir": base_tir,
        "duration": duration,
        "months": months,
        "matrix": matrix
    }
