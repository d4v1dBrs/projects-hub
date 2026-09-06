"""Financial backend for the five-tab bond workbench.

The module deliberately has no history or HTTP concerns.  It consumes the
repository and already-selected live provider supplied by the route, delegates
bond pricing to :class:`FinancialEngine`, and only adds position/fee/scenario
arithmetic around that domain result.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any, Optional

from apps.web.bond_detail import (
    _live_metrics,
    _resolve_instrument_and_leg,
    _resolve_ref,
    get_bond_detail,
)
from core.domain.conventions import cer_reference_date
from core.domain.currency import position_currency
from core.domain.models import Instrument, MarketSnapshot
from core.domain.services import FinancialEngine
from core.domain.xirr import xirr

_SOVEREIGN_TYPES = frozenset({"BONAR", "GLOBAL", "BOPREAL"})
_TAMAR_TYPES = frozenset({"PURO", "DUAL", "DUAL_CER_TAMAR"})
_JULIAN_YEAR = 365.25

_DEFAULTS = {
    "price": None,
    "nominal": 10_000.0,
    "cost_price": None,
    "yield_pct": None,
    "shock_bps": 100.0,
    "capital": 100_000.0,
    "entry_fee_pct": 0.5,
    "exit_fee_pct": 0.5,
    "annual_fee_pct": 0.0,
    "horizon_days": 365,
    "income_target": 0.0,
    "inflation_pct": 20.0,
}


def _num(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _finite(value: Any) -> Any:
    """Recursively make the result strict-JSON compatible."""
    if isinstance(value, dict):
        return {key: _finite(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite(item) for item in value]
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _fmt_es(value: Optional[float], digits: int = 2) -> str:
    if value is None or not math.isfinite(value):
        return "no disponible"
    rendered = f"{value:,.{digits}f}"
    return rendered.replace(",", "_").replace(".", ",").replace("_", ".")


def _call_number(obj: Any, method: str) -> Optional[float]:
    fn = getattr(obj, method, None) if obj is not None else None
    if not callable(fn):
        return None
    try:
        return _num(fn())
    except Exception:  # noqa: BLE001 - external provider degrades explicitly
        return None


def _quote_offer(fx: Any, method: str, casa: str) -> Optional[float]:
    value = _call_number(fx, method)
    if value is not None and value > 0:
        return value
    get_quote = getattr(fx, "get_quote", None) if fx is not None else None
    if not callable(get_quote):
        return None
    try:
        quote = get_quote(casa)
    except Exception:  # noqa: BLE001 - external provider degrades explicitly
        return None
    value = _num((quote or {}).get("venta"))
    return value if value is not None and value > 0 else None


def _market_setup(instrument: Instrument, fx: Any) -> dict[str, Any]:
    """Describe quote units, engine units, and future cashflow conversion."""
    ticker = (instrument.ticker or "").upper()
    itype = instrument.norm_type
    quote_currency = position_currency(itype, ticker)
    setup: dict[str, Any] = {
        "quote_currency": quote_currency,
        "pricing_currency": quote_currency,
        "pricing_divisor": 1.0,
        "cashflow_multiplier": 1.0,
        "conversion_basis": None,
        "cashflow_basis": "nominal contractual",
    }

    if itype in _SOVEREIGN_TYPES:
        setup["pricing_currency"] = "USD"
        setup["cashflow_basis"] = "USD contractual"
        if quote_currency == "ARS":
            if itype == "GLOBAL":
                rate = _quote_offer(fx, "get_ccl_venta", "contadoconliqui")
                basis = "CCL vendedor"
            else:
                rate = _quote_offer(fx, "get_mep_venta", "bolsa")
                basis = "MEP vendedor"
            setup["pricing_divisor"] = rate
            setup["cashflow_multiplier"] = rate
            setup["conversion_basis"] = basis
        return setup

    if instrument.is_dolar_linked:
        setup["cashflow_basis"] = "USD contractual"
        if quote_currency == "ARS":
            rate = _quote_offer(fx, "get_mayorista_venta", "mayorista")
            setup["cashflow_multiplier"] = rate
            setup["conversion_basis"] = "tipo de cambio oficial vendedor"
        return setup

    if instrument.is_hard_dollar:
        setup["cashflow_basis"] = "USD contractual"
        if quote_currency == "ARS":
            if instrument.is_ley_argentina:
                rate = _quote_offer(fx, "get_mep_venta", "bolsa")
                basis = "MEP vendedor"
            else:
                rate = _quote_offer(fx, "get_ccl_venta", "contadoconliqui")
                basis = "CCL vendedor"
            setup["cashflow_multiplier"] = rate
            setup["conversion_basis"] = basis
        return setup

    if instrument.is_cer:
        setup["cashflow_basis"] = "unidades contractuales base CER"
    elif itype in _TAMAR_TYPES:
        setup["cashflow_basis"] = "escenario proyectado indexado"
    return setup


def _pricing_price(price: Optional[float], setup: dict[str, Any]) -> Optional[float]:
    if price is None or price <= 0:
        return None
    divisor = _num(setup.get("pricing_divisor"))
    if divisor is None or divisor <= 0:
        return None
    return price / divisor


def _quote_price(price: Optional[float], setup: dict[str, Any]) -> Optional[float]:
    """Convert an engine price back to the traded quote currency."""
    if price is None:
        return None
    divisor = _num(setup.get("pricing_divisor"))
    if divisor is None or divisor <= 0:
        return None
    return price * divisor


def _snapshot(instrument: Instrument, price: Optional[float], settle: date) -> MarketSnapshot:
    return MarketSnapshot(instrument=instrument, price=price, last_update=settle)


def _tir(
    instrument: Instrument,
    quote_price: Optional[float],
    setup: dict[str, Any],
    indices: Any,
    fx: Any,
    settle: date,
) -> Optional[float]:
    engine_price = _pricing_price(quote_price, setup)
    if engine_price is None:
        return None
    result = FinancialEngine.tir_from_price(
        _snapshot(instrument, engine_price, settle),
        engine_price,
        indices_provider=indices,
        fx_provider=fx,
        settle_date=settle,
    )
    return _num(result)


def _price_at_yield(
    instrument: Instrument,
    yield_dec: Optional[float],
    setup: dict[str, Any],
    indices: Any,
    fx: Any,
    settle: date,
) -> Optional[float]:
    if yield_dec is None or yield_dec <= -1.0:
        return None
    price = FinancialEngine.price_from_tir(
        _snapshot(instrument, None, settle),
        yield_dec,
        indices_provider=indices,
        fx_provider=fx,
        settle_date=settle,
    )
    return _quote_price(_num(price), setup)


def _cer_level(indices: Any, target: date) -> Optional[float]:
    fn = getattr(indices, "get_cer", None) if indices is not None else None
    if not callable(fn):
        return None
    try:
        value = _num(fn(target))
    except Exception:  # noqa: BLE001 - external provider degrades explicitly
        return None
    return value if value is not None and value > 0 else None


def _project_cashflows(
    instrument: Instrument,
    indices: Any,
    setup: dict[str, Any],
    settle: date,
    inflation: float,
) -> tuple[list[dict[str, Any]], list[str], Optional[str], bool]:
    """Project future per-100 cashflows into the traded quote currency.

    Fixed schedules remain contractual.  CER, FX and TAMAR-family amounts are
    explicit scenarios because their future nominal amount is not known today.
    """
    assumptions: list[str] = []
    scenario = False
    cashflows = [cf for cf in instrument.cashflows if cf.date > settle]

    if not cashflows and instrument.norm_type in _TAMAR_TYPES:
        payoff = FinancialEngine.projected_payoff(instrument, indices, ref_date=settle)
        payoff = _num(payoff)
        if payoff is None or payoff <= 0 or instrument.maturity_date is None:
            return [], assumptions, "No hay un pago TAMAR/máximo de rieles proyectable.", True
        tamar = None
        fn = getattr(indices, "get_tamar", None) if indices is not None else None
        if callable(fn):
            try:
                tamar = _num(fn())
            except Exception:  # noqa: BLE001 - external provider degrades explicitly
                tamar = None
        rate_text = f" ({_fmt_es(tamar, 3)}% TNA)" if tamar is not None else ""
        assumptions.append(
            "Escenario: el motor promedia la TAMAR histórica observada y mantiene "
            f"la última TAMAR constante para el tramo futuro{rate_text}; aplica "
            "el spread, la capitalización mensual y el piso o máximo contractual. "
            "El supuesto de inflación ingresado no se aplica a esta familia."
        )
        if instrument.is_dual_cer_tamar:
            assumptions.append(
                "Riel CER del dual: el motor extrapola desde la fecha actual el "
                "crecimiento observado de los últimos 30 días, en forma compuesta: "
                "CER actual × (CER actual / CER hace 30 días)^(días futuros / 30). "
                f"El pago usa el CER de {instrument.cer_lag} días hábiles antes "
                "del vencimiento, aplica el spread CER contractual devengado "
                "desde la emisión en ACT/365,25 y toma el máximo frente al riel TAMAR."
            )
            assumptions.append(
                "Si falta el CER de hace 30 días, el motor conserva el CER actual; "
                "si no dispone de CER o CER base válido, solo calcula el riel TAMAR. "
                "Es una proyección del motor, no un cobro nominal garantizado."
            )
        return [
            {
                "date": instrument.maturity_date,
                "interest": 0.0,
                "amortization": payoff,
            }
        ], assumptions, None, True

    if not cashflows:
        return [], assumptions, "El catálogo no tiene flujos contractuales futuros.", False

    if instrument.is_cer:
        if instrument.cer_base is None or instrument.cer_base <= 0:
            return [], assumptions, "Falta un CER base válido.", True
        if inflation <= -1.0:
            return [], assumptions, "El escenario de inflación debe ser mayor que -100%.", True
        current_ref = cer_reference_date(settle, instrument.cer_lag)
        current_cer = _cer_level(indices, current_ref)
        if current_cer is None:
            return [], assumptions, "No hay CER actual para construir el escenario.", True
        scenario = True
        assumptions.append(
            f"Escenario: el CER crece a una tasa anual constante de "
            f"{_fmt_es(inflation * 100, 3)}%; cada pago usa su rezago contractual de "
            f"{instrument.cer_lag} días hábiles."
        )

        def multiplier(payment_date: date) -> float:
            payment_ref = cer_reference_date(payment_date, instrument.cer_lag)
            years = max((payment_ref - current_ref).days / _JULIAN_YEAR, 0.0)
            projected_cer = current_cer * (1.0 + inflation) ** years
            return projected_cer / instrument.cer_base

    else:
        raw_multiplier = setup.get("cashflow_multiplier")
        fixed_multiplier = _num(raw_multiplier)
        if fixed_multiplier is None or fixed_multiplier <= 0:
            basis = setup.get("conversion_basis") or "tipo de cambio requerido"
            return [], assumptions, f"No está disponible {basis} para convertir los flujos.", True

        def multiplier(payment_date: date) -> float:
            del payment_date
            return fixed_multiplier

        if setup.get("conversion_basis"):
            scenario = True
            assumptions.append(
                f"Escenario: los flujos futuros en USD usan {setup['conversion_basis']} "
                f"constante de {_fmt_es(fixed_multiplier, 4)} "
                f"{setup['quote_currency']}/USD."
            )

    projected = []
    for cf in cashflows:
        factor = multiplier(cf.date)
        interest = _num(cf.interest * factor)
        amortization = _num(cf.amortization * factor)
        if interest is None or amortization is None:
            return [], assumptions, "Un flujo proyectado no es finito.", scenario
        projected.append(
            {"date": cf.date, "interest": interest, "amortization": amortization}
        )
    return projected, assumptions, None, scenario


def _pv(
    cashflows: list[dict[str, Any]],
    reference: date,
    yield_dec: float,
    instrument: Instrument,
    *,
    include_reference: bool = False,
) -> Optional[float]:
    if yield_dec <= -1.0:
        return None
    total = 0.0
    try:
        for flow in cashflows:
            if flow["date"] < reference:
                continue
            if flow["date"] == reference and not include_reference:
                continue
            years = instrument.year_fraction_to(flow["date"], reference)
            amount = flow["interest"] + flow["amortization"]
            total += amount / (1.0 + yield_dec) ** years
    except (OverflowError, ValueError, ZeroDivisionError):
        return None
    return _num(total)


def _scenario_yield(
    instrument: Instrument, engine_yield: Optional[float], inflation: float
) -> Optional[float]:
    if engine_yield is None:
        return None
    if instrument.is_cer:
        return (1.0 + engine_yield) * (1.0 + inflation) - 1.0
    return engine_yield


def _horizon_rows(
    instrument: Instrument,
    projected: list[dict[str, Any]],
    projection_reason: Optional[str],
    base_price: Optional[float],
    base_yield: Optional[float],
    settle: date,
    entry_fee_pct: float,
    exit_fee_pct: float,
) -> tuple[list[dict[str, Any]], Optional[str]]:
    if projection_reason:
        return [], projection_reason
    if not projected:
        return [], "No hay flujos futuros para los horizontes."
    if base_price is None or base_price <= 0:
        return [], "No hay un precio base positivo para los horizontes."
    if base_yield is None or base_yield <= -1.0:
        return [], "No se puede resolver la TIR base de los horizontes."

    maturity = instrument.maturity_date or projected[-1]["date"]
    if maturity <= settle:
        return [], "El instrumento ya venció."
    initial_net = base_price * (1.0 + entry_fee_pct / 100.0)
    rows = []
    seen_horizons: set[date] = set()
    for requested_days in (30, 90, 180, 365):
        horizon = min(settle + timedelta(days=requested_days), maturity)
        if horizon in seen_horizons:
            continue
        seen_horizons.add(horizon)
        coupons = sum(
            flow["interest"] for flow in projected if flow["date"] <= horizon
        )
        amortization = sum(
            flow["amortization"] for flow in projected if flow["date"] <= horizon
        )
        at_maturity = horizon >= maturity
        for shift_bps in (-100, 0, 100):
            shifted_yield = base_yield + shift_bps / 10_000.0
            exit_price = (
                0.0
                if at_maturity
                else _pv(projected, horizon, shifted_yield, instrument)
            )
            if exit_price is None:
                return [], "No se pudo valuar la venta en uno de los horizontes."
            gross_proceeds = coupons + amortization + exit_price
            exit_fee = 0.0 if at_maturity else exit_price * exit_fee_pct / 100.0
            net_proceeds = gross_proceeds - exit_fee
            rows.append(
                {
                    "days": (horizon - settle).days,
                    "requested_days": requested_days,
                    "date": horizon.isoformat(),
                    "yield_shift_bps": shift_bps,
                    "exit_price": exit_price,
                    "coupons": coupons,
                    "amortization": amortization,
                    "return_pct": (gross_proceeds / base_price - 1.0) * 100.0,
                    "net_return_pct": (net_proceeds / initial_net - 1.0) * 100.0,
                }
            )
    return rows, None


def _numerical_risk(
    instrument: Instrument,
    base_yield: Optional[float],
    base_price: Optional[float],
    setup: dict[str, Any],
    indices: Any,
    fx: Any,
    settle: date,
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    if base_yield is None or base_price is None or base_price <= 0:
        return None, None, None
    bump = 0.0001
    price_minus = _price_at_yield(
        instrument, base_yield - bump, setup, indices, fx, settle
    )
    price_plus = _price_at_yield(
        instrument, base_yield + bump, setup, indices, fx, settle
    )
    if price_minus is None or price_plus is None:
        return None, None, None
    dv01 = (price_minus - price_plus) / 2.0
    duration = dv01 / base_price / bump
    convexity = (price_minus + price_plus - 2.0 * base_price) / (
        base_price * bump * bump
    )
    return _num(dv01), _num(duration), _num(convexity)


def _trading(
    instrument: Instrument,
    market: dict[str, Any],
    setup: dict[str, Any],
    indices: Any,
    fx: Any,
    settle: date,
    params: dict[str, Any],
    projected: list[dict[str, Any]],
    projection_reason: Optional[str],
    inflation: float,
) -> dict[str, Any]:
    price = _num(params["price"])
    if price is None:
        price = _num(market.get("price"))
    bid = _num(market.get("bid"))
    ask = _num(market.get("ask"))
    nominal = _num(params["nominal"]) or 0.0
    cost_price = _num(params["cost_price"])
    market_yield = _tir(instrument, price, setup, indices, fx, settle)
    bid_yield = _tir(instrument, bid, setup, indices, fx, settle)
    ask_yield = _tir(instrument, ask, setup, indices, fx, settle)

    midpoint = (bid + ask) / 2.0 if bid is not None and ask is not None else None
    spread = ask - bid if bid is not None and ask is not None else None
    spread_bps = (
        spread / midpoint * 10_000.0
        if spread is not None and midpoint is not None and midpoint > 0
        else None
    )
    market_value = price * nominal / 100.0 if price is not None else None
    unrealized = (
        (price - cost_price) * nominal / 100.0
        if price is not None and cost_price is not None
        else None
    )

    shock = _num(params["shock_bps"]) or 0.0
    requested_yield = _num(params["yield_pct"])
    base_yield = (
        requested_yield / 100.0 if requested_yield is not None else market_yield
    )
    base_price = (
        _price_at_yield(instrument, base_yield, setup, indices, fx, settle)
        if requested_yield is not None
        else price
    )
    stressed_yield = base_yield + shock / 10_000.0 if base_yield is not None else None
    stressed_price = _price_at_yield(
        instrument, stressed_yield, setup, indices, fx, settle
    )
    dv01_per100, modified_duration, convexity = _numerical_risk(
        instrument, base_yield, base_price, setup, indices, fx, settle
    )
    dv01_position = (
        dv01_per100 * nominal / 100.0 if dv01_per100 is not None else None
    )

    stress = []
    if base_yield is not None:
        for multiple in (-2, -1, 0, 1, 2):
            shift = multiple * shock
            row_yield = base_yield + shift / 10_000.0
            row_price = _price_at_yield(
                instrument, row_yield, setup, indices, fx, settle
            )
            pnl = (
                (row_price - base_price) * nominal / 100.0
                if row_price is not None and base_price is not None
                else None
            )
            return_pct = (
                (row_price / base_price - 1.0) * 100.0
                if row_price is not None and base_price is not None and base_price > 0
                else None
            )
            stress.append(
                {
                    "shock_bps": shift,
                    "yield": row_yield,
                    "price": row_price,
                    "pnl": pnl,
                    "return_pct": return_pct,
                }
            )

    horizon_yield = _scenario_yield(instrument, base_yield, inflation)
    horizon_price = (
        _pv(projected, settle, horizon_yield, instrument)
        if requested_yield is not None and horizon_yield is not None and not projection_reason
        else base_price
    )
    horizons, horizons_reason = _horizon_rows(
        instrument,
        projected,
        projection_reason,
        horizon_price,
        horizon_yield,
        settle,
        _num(params["entry_fee_pct"]) or 0.0,
        _num(params["exit_fee_pct"]) or 0.0,
    )

    horizon_assumptions = [
        "Importes por 100 VN: renta y amortización contractual hasta el "
        "horizonte más valor de venta de los flujos restantes.",
        "La fecha se limita al vencimiento si el horizonte solicitado lo supera.",
        "La TIR desplazada valúa la venta; el retorno neto incluye comisiones "
        "de entrada y salida, pero no honorario anual ni impuestos.",
        "Al vencimiento no hay valor de venta ni comisión de salida.",
    ]
    if instrument.is_cer:
        horizon_assumptions.append(
            "En CER, la venta usa una TIR nominal de escenario combinada por Fisher; "
            "la TIR base informada en Trading sigue siendo real."
        )
    return {
        "currency": setup["quote_currency"],
        "pricing_currency": setup["pricing_currency"],
        "yield_basis": _yield_basis(instrument, setup),
        "base_price": base_price,
        "base_yield": base_yield,
        "stressed_price": stressed_price,
        "stressed_yield": stressed_yield,
        "bid_yield": bid_yield,
        "ask_yield": ask_yield,
        "spread": spread,
        "spread_bps": spread_bps,
        "midpoint": midpoint,
        "nominal": nominal,
        "market_value": market_value,
        "unrealized_pnl": unrealized,
        "dv01_per100": dv01_per100,
        "dv01_position": dv01_position,
        "modified_duration": modified_duration,
        "convexity": convexity,
        "simulated_price": base_price,
        "simulated_yield": base_yield,
        "stress": stress,
        "horizons": horizons,
        "horizons_reason": horizons_reason,
        "horizons_assumptions": horizon_assumptions,
    }


def _yield_basis(instrument: Instrument, setup: dict[str, Any]) -> str:
    if instrument.is_cer:
        return "TIR real CER"
    if instrument.norm_type in _TAMAR_TYPES:
        return "TIR nominal sobre pago indexado proyectado"
    if (
        instrument.norm_type in _SOVEREIGN_TYPES
        or instrument.is_dolar_linked
        or instrument.is_hard_dollar
    ):
        return "TIR sobre flujos USD"
    return f"TIR nominal en {setup['pricing_currency']}"


def _xirr(
    instrument: Instrument, flows: list[float], dates: list[date]
) -> Optional[float]:
    if len(flows) < 2 or len(flows) != len(dates):
        return None
    if not any(value > 0 for value in flows) or not any(value < 0 for value in flows):
        return None
    result = xirr(flows, dates, day_count=instrument.day_count_enum)
    return _num(result)


def _wealth_case(
    instrument: Instrument,
    projected: list[dict[str, Any]],
    quote_price: float,
    valuation_yield: float,
    settle: date,
    horizon: date,
    capital: float,
    entry_pct: float,
    exit_pct: float,
    annual_pct: float,
    maturity: date,
) -> dict[str, Any]:
    entry_rate = entry_pct / 100.0
    unit_cost = quote_price / 100.0 * (1.0 + entry_rate)
    nominal = capital / unit_cost
    gross_outlay = quote_price * nominal / 100.0
    entry_fee = gross_outlay * entry_rate
    initial_outlay = gross_outlay + entry_fee

    by_date: dict[date, dict[str, float]] = {}
    for flow in projected:
        if flow["date"] <= horizon:
            row = by_date.setdefault(
                flow["date"], {"interest": 0.0, "amortization": 0.0, "sale": 0.0}
            )
            row["interest"] += flow["interest"] * nominal / 100.0
            row["amortization"] += flow["amortization"] * nominal / 100.0

    sold_before_maturity = horizon < maturity
    if sold_before_maturity:
        sale_per_100 = _pv(projected, horizon, valuation_yield, instrument) or 0.0
        row = by_date.setdefault(
            horizon, {"interest": 0.0, "amortization": 0.0, "sale": 0.0}
        )
        row["sale"] += sale_per_100 * nominal / 100.0

    rows = []
    previous_date = settle
    opening_market_value = gross_outlay
    annual_rate = annual_pct / 100.0
    total_period_fees = 0.0
    for flow_date in sorted(by_date):
        amounts = by_date[flow_date]
        days = max((flow_date - previous_date).days, 0)
        annual_fee = opening_market_value * annual_rate * days / _JULIAN_YEAR
        exit_fee = amounts["sale"] * exit_pct / 100.0
        interest = amounts["interest"]
        amortization = amounts["amortization"]
        sale = amounts["sale"]
        gross = interest + amortization + sale
        fee = annual_fee + exit_fee
        rows.append(
            {
                "date": flow_date.isoformat(),
                "interest": interest,
                "amortization": amortization,
                "sale": sale,
                "gross": gross,
                "fee": fee,
                "net": gross - fee,
            }
        )
        total_period_fees += fee
        remaining_per_100 = _pv(projected, flow_date, valuation_yield, instrument) or 0.0
        opening_market_value = remaining_per_100 * nominal / 100.0
        previous_date = flow_date

    dates = [settle] + [date.fromisoformat(row["date"]) for row in rows]
    gross_flows = [-gross_outlay] + [row["gross"] for row in rows]
    net_flows = [-initial_outlay] + [row["net"] for row in rows]
    return {
        "nominal": nominal,
        "gross_outlay": gross_outlay,
        "entry_fee": entry_fee,
        "initial_outlay": initial_outlay,
        "gross_yield": _xirr(instrument, gross_flows, dates),
        "net_yield": _xirr(instrument, net_flows, dates),
        "fees_total": entry_fee + total_period_fees,
        "income_in_horizon": sum(row["interest"] for row in rows),
        "principal_in_horizon": sum(row["amortization"] for row in rows),
        "sale_value": sum(row["sale"] for row in rows),
        "cashflows": rows,
        "sold_before_maturity": sold_before_maturity,
    }


def _unsupported_wealth(
    currency: str,
    capital: float,
    reason: str,
    assumptions: list[str],
    horizon: Optional[date],
) -> dict[str, Any]:
    return {
        "currency": currency,
        "capital": capital,
        "nominal": None,
        "gross_outlay": None,
        "entry_fee": None,
        "initial_outlay": None,
        "gross_yield": None,
        "net_yield": None,
        "fees_total": None,
        "income_in_horizon": None,
        "principal_in_horizon": None,
        "sale_value": None,
        "horizon_date": horizon.isoformat() if horizon else None,
        "capital_for_target": None,
        "assumptions": assumptions,
        "cashflows": [],
        "fee_comparison": [],
        "supported": False,
        "reason": reason,
    }


def _wealth(
    instrument: Instrument,
    projected: list[dict[str, Any]],
    reason: Optional[str],
    assumptions: list[str],
    quote_price: Optional[float],
    engine_yield: Optional[float],
    setup: dict[str, Any],
    settle: date,
    params: dict[str, Any],
) -> dict[str, Any]:
    currency = setup["quote_currency"]
    capital = _num(params["capital"]) or 0.0
    known_maturity = instrument.maturity_date
    if known_maturity is None and projected:
        known_maturity = projected[-1]["date"]
    requested_horizon = settle + timedelta(days=int(params["horizon_days"]))
    horizon = min(requested_horizon, known_maturity) if known_maturity else requested_horizon
    if reason:
        return _unsupported_wealth(currency, capital, reason, assumptions, horizon)
    if quote_price is None or quote_price <= 0:
        return _unsupported_wealth(
            currency, capital, "Se requiere un precio de cotización positivo.", assumptions,
            horizon,
        )
    if engine_yield is None or engine_yield <= -1.0:
        return _unsupported_wealth(
            currency, capital, "No se puede resolver la TIR actual.", assumptions, horizon
        )
    if not projected:
        return _unsupported_wealth(
            currency, capital, "No hay flujos futuros disponibles.", assumptions, horizon
        )
    if capital <= 0:
        return _unsupported_wealth(
            currency, capital, "El capital debe ser positivo.", assumptions, horizon
        )

    valuation_yield = engine_yield
    if instrument.is_cer:
        inflation = (_num(params["inflation_pct"]) or 0.0) / 100.0
        valuation_yield = (1.0 + engine_yield) * (1.0 + inflation) - 1.0
        assumptions.append(
            "La venta del escenario CER combina por Fisher la TIR real del motor "
            "con el supuesto de inflación indicado."
        )

    maturity = known_maturity or projected[-1]["date"]
    if horizon <= settle:
        return _unsupported_wealth(
            currency,
            capital,
            "El instrumento no tiene un horizonte de inversión positivo.",
            assumptions,
            horizon,
        )

    entry_pct = _num(params["entry_fee_pct"]) or 0.0
    exit_pct = _num(params["exit_fee_pct"]) or 0.0
    annual_pct = _num(params["annual_fee_pct"]) or 0.0
    case = _wealth_case(
        instrument,
        projected,
        quote_price,
        valuation_yield,
        settle,
        horizon,
        capital,
        entry_pct,
        exit_pct,
        annual_pct,
        maturity,
    )

    assumptions.extend(
        [
            "El capital es el presupuesto total: los VN comprados incluyen la "
            "comisión de entrada.",
            "La TIR bruta y neta se resuelven con las fechas de los flujos y la "
            f"convención {instrument.day_count_enum.value} del instrumento.",
            "El honorario anual se devenga proporcionalmente sobre el capital de "
            "mercado al inicio de cada intervalo entre flujos, con TIR constante "
            "y prorrateo ACT/365,25.",
        ]
    )
    if case["sold_before_maturity"]:
        assumptions.append(
            "La venta al horizonte se valúa con TIR constante y paga la comisión "
            "de salida indicada."
        )
    else:
        assumptions.append("El rescate al vencimiento se cobra sin comisión de salida.")

    comparison_rates = sorted({0.0, 0.5, 1.0, 2.0, entry_pct})
    fee_comparison = []
    for comparison_pct in comparison_rates:
        comparison = _wealth_case(
            instrument,
            projected,
            quote_price,
            valuation_yield,
            settle,
            horizon,
            capital,
            comparison_pct,
            exit_pct,
            annual_pct,
            maturity,
        )
        fee_comparison.append(
            {"entry_fee_pct": comparison_pct, "net_yield": comparison["net_yield"]}
        )

    target = _num(params["income_target"]) or 0.0
    income = case["income_in_horizon"]
    capital_for_target = capital * target / income if target > 0 and income > 0 else None
    return {
        "currency": currency,
        "capital": capital,
        "nominal": case["nominal"],
        "gross_outlay": case["gross_outlay"],
        "entry_fee": case["entry_fee"],
        "initial_outlay": case["initial_outlay"],
        "gross_yield": case["gross_yield"],
        "net_yield": case["net_yield"],
        "yield_day_count": instrument.day_count_enum.value,
        "fees_total": case["fees_total"],
        "income_in_horizon": income,
        "principal_in_horizon": case["principal_in_horizon"],
        "sale_value": case["sale_value"],
        "horizon_date": horizon.isoformat(),
        "capital_for_target": capital_for_target,
        "assumptions": assumptions,
        "cashflows": case["cashflows"],
        "fee_comparison": fee_comparison,
        "supported": True,
        "reason": None,
    }


def _timeline_dates(settle: date, projected: list[dict[str, Any]]) -> list[date]:
    candidates = {settle}
    for flow in projected[:3]:
        event = flow["date"]
        if event <= settle:
            continue
        gap = (event - settle).days
        if gap > 2:
            candidates.add(settle + timedelta(days=gap // 2))
            candidates.add(event - timedelta(days=1))
        candidates.add(event)
    return sorted(candidates)


def _projected_accrued(
    instrument: Instrument,
    reference: date,
    setup: dict[str, Any],
    indices: Any,
    inflation: float,
    settle: date,
) -> Optional[float]:
    accrued = _num(FinancialEngine.accrued_interest(instrument, reference))
    if accrued is None or accrued == 0:
        return 0.0
    if instrument.is_cer:
        if instrument.cer_base is None or instrument.cer_base <= 0:
            return None
        current_ref = cer_reference_date(settle, instrument.cer_lag)
        current_cer = _cer_level(indices, current_ref)
        if current_cer is None or inflation <= -1.0:
            return None
        target = cer_reference_date(reference, instrument.cer_lag)
        years = max((target - current_ref).days / _JULIAN_YEAR, 0.0)
        return accrued * current_cer * (1.0 + inflation) ** years / instrument.cer_base
    factor = _num(setup.get("cashflow_multiplier"))
    return accrued * factor if factor is not None else None


def _unsupported_teaching(reason: str, assumptions: list[str]) -> dict[str, Any]:
    return {
        "supported": False,
        "reason": reason,
        "next_event": None,
        "timeline": [],
        "price_yield": [],
        "stress": [],
        "exercises": [],
        "assumptions": assumptions,
    }


def _teaching(
    instrument: Instrument,
    projected: list[dict[str, Any]],
    reason: Optional[str],
    assumptions: list[str],
    setup: dict[str, Any],
    indices: Any,
    engine_yield: Optional[float],
    settle: date,
    params: dict[str, Any],
) -> dict[str, Any]:
    if reason:
        return _unsupported_teaching(reason, assumptions)
    if not projected:
        return _unsupported_teaching("No hay flujos futuros disponibles.", assumptions)
    if engine_yield is None or engine_yield <= -1.0:
        return _unsupported_teaching("No se puede resolver la TIR actual.", assumptions)

    teaching_start = max(settle, instrument.emission_date or settle)
    projected = [flow for flow in projected if flow["date"] >= teaching_start]
    if not projected:
        return _unsupported_teaching(
            "No hay flujos en o después de la fecha de emisión.", assumptions
        )

    valuation_yield = engine_yield
    if instrument.is_cer:
        inflation = (_num(params["inflation_pct"]) or 0.0) / 100.0
        valuation_yield = (1.0 + engine_yield) * (1.0 + inflation) - 1.0
    else:
        inflation = 0.0

    event_date = projected[0]["date"]
    event_flows = [flow for flow in projected if flow["date"] == event_date]
    event_interest = sum(flow["interest"] for flow in event_flows)
    event_amortization = sum(flow["amortization"] for flow in event_flows)
    before = _pv(
        projected, event_date, valuation_yield, instrument, include_reference=True
    )
    after = _pv(projected, event_date, valuation_yield, instrument)
    if before is None or after is None:
        return _unsupported_teaching(
            "No está disponible la valuación del evento de pago.", assumptions
        )
    event_total = event_interest + event_amortization
    next_event = {
        "date": event_date.isoformat(),
        "interest": event_interest,
        "amortization": event_amortization,
        "before_dirty": before,
        "after_dirty": after,
        "drop": before - after,
        "total_wealth_before": before,
        "total_wealth_after": after + event_total,
    }

    timeline = []
    for timeline_date in _timeline_dates(teaching_start, projected):
        dirty = _pv(projected, timeline_date, valuation_yield, instrument)
        accrued = _projected_accrued(
            instrument, timeline_date, setup, indices, inflation, settle
        )
        clean = dirty - accrued if dirty is not None and accrued is not None else None
        timeline.append(
            {
                "date": timeline_date.isoformat(),
                "dirty": dirty,
                "clean": clean,
                "accrued": accrued,
            }
        )

    price_yield = []
    for offset in (-500, -250, -100, 0, 100, 250, 500):
        curve_yield = valuation_yield + offset / 10_000.0
        curve_price = (
            _pv(projected, teaching_start, curve_yield, instrument)
            if curve_yield > -1.0
            else None
        )
        price_yield.append({"yield": curve_yield, "price": curve_price})

    shock = _num(params["shock_bps"]) or 0.0
    shocked_yield = valuation_yield + shock / 10_000.0
    base_price = _pv(projected, teaching_start, valuation_yield, instrument)
    shocked_price = _pv(projected, teaching_start, shocked_yield, instrument)
    shock_return = (
        (shocked_price / base_price - 1.0) * 100.0
        if shocked_price is not None and base_price is not None and base_price > 0
        else None
    )
    currency = setup["quote_currency"]
    drop = before - after
    wealth_change = after + event_total - before
    nominal = _num(params["nominal"]) or 0.0
    position_payment = event_total * nominal / 100.0
    teaching_stress = []
    for multiple in (-2, -1, 0, 1, 2):
        shift = multiple * shock
        row_yield = valuation_yield + shift / 10_000.0
        row_price = (
            _pv(projected, teaching_start, row_yield, instrument)
            if row_yield > -1.0
            else None
        )
        row_return = (
            (row_price / base_price - 1.0) * 100.0
            if row_price is not None and base_price is not None and base_price > 0
            else None
        )
        teaching_stress.append(
            {
                "shock_bps": shift,
                "yield": row_yield,
                "price": row_price,
                "pnl": (
                    (row_price - base_price) * nominal / 100.0
                    if row_price is not None and base_price is not None
                    else None
                ),
                "return_pct": row_return,
            }
        )
    exercises = [
        {
            "question": f"¿Cuánto cae el precio sucio el {event_date.isoformat()}?",
            "answer": f"{_fmt_es(drop)} {currency} por 100 VN",
            "working": f"{_fmt_es(before)} - {_fmt_es(after)} = {_fmt_es(drop)} "
            f"{currency} por 100 VN, con la misma fecha base.",
        },
        {
            "question": f"¿Se conserva el patrimonio al cobrar el evento de {instrument.ticker}?",
            "answer": f"{_fmt_es(wealth_change)} {currency} por 100 VN",
            "working": f"{_fmt_es(after)} + {_fmt_es(event_interest)} de renta + "
            f"{_fmt_es(event_amortization)} de amortización - {_fmt_es(before)} = "
            f"{_fmt_es(wealth_change)} {currency} por 100 VN.",
        },
        {
            "question": f"¿Cuánto cobra una posición de {_fmt_es(nominal)} VN en ese evento?",
            "answer": f"{_fmt_es(position_payment)} {currency} para {_fmt_es(nominal)} VN",
            "working": f"{_fmt_es(event_total)} {currency} por 100 VN × "
            f"{_fmt_es(nominal)} / 100 = {_fmt_es(position_payment)} {currency}.",
        },
        {
            "question": f"¿Qué ocurre si la TIR se mueve {_fmt_es(shock, 0)} puntos básicos?",
            "answer": (
                f"{_fmt_es(shock_return)}% de variación de precio"
                if shock_return is not None
                else "Variación no disponible"
            ),
            "working": f"Se descuentan todos los flujos proyectados de {instrument.ticker} "
            f"a {_fmt_es(shocked_yield * 100, 4)}% y se compara el precio "
            f"{_fmt_es(shocked_price)} con {_fmt_es(base_price)} {currency} por 100 VN.",
        },
    ]
    teaching_assumptions = list(assumptions)
    if instrument.is_cer:
        teaching_assumptions.append(
            "La curva precio/TIR de Docencia usa valores nominales de escenario "
            "combinados por Fisher; la TIR de Detalle y Trading sigue siendo real."
        )
    teaching_assumptions.append(
        "Los valores inmediatamente anterior y posterior usan exactamente la fecha "
        "del evento como base; la caída sucia equivale a renta más amortización."
    )
    return {
        "supported": True,
        "reason": None,
        "next_event": next_event,
        "timeline": timeline,
        "price_yield": price_yield,
        "stress": teaching_stress,
        "exercises": exercises,
        "assumptions": teaching_assumptions,
    }


def _annotate_detail(
    detail: dict[str, Any],
    instrument: Instrument,
    setup: dict[str, Any],
    indices: Any,
    fx: Any,
    settle: date,
) -> None:
    market = detail["market"]
    engine_price = _pricing_price(_num(market.get("price")), setup)
    engine_bid = _pricing_price(_num(market.get("bid")), setup)
    engine_ask = _pricing_price(_num(market.get("ask")), setup)
    pricing_snapshot = _snapshot(instrument, engine_price, settle)
    detail["metrics"] = _live_metrics(pricing_snapshot, indices, fx, settle)
    detail["pricing"] = {
        "price": engine_price,
        "bid": engine_bid,
        "ask": engine_ask,
        "currency": setup["pricing_currency"],
        "quote_currency": setup["quote_currency"],
        "conversion_rate": setup.get("pricing_divisor"),
        "conversion_basis": setup.get("conversion_basis"),
    }
    raw_currency = "USD" if "USD" in setup["cashflow_basis"] else setup["quote_currency"]
    raw_unit = raw_currency
    if instrument.is_cer:
        raw_currency = None
        raw_unit = "CER_BASE"
    detail["cashflow_basis"] = {
        "kind": setup["cashflow_basis"],
        "currency": raw_currency,
        "unit": raw_unit,
        "note": "Los flujos de Detalle conservan importes contractuales/base; "
        "los importes de escenario se informan en wealth.cashflows.",
    }
    detail["meta"]["quote_currency"] = setup["quote_currency"]
    detail["meta"]["pricing_currency"] = setup["pricing_currency"]
    detail["meta"]["cashflow_basis"] = setup["cashflow_basis"]


def build_workbench(
    ticker: str,
    repo: Any,
    provider: Any,
    indices: Any,
    fx: Any,
    *,
    settlement_lag: int = 1,
    params: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    """Build finite financial analytics for the local bond workbench.

    ``provider`` must already represent the same CI/24-hour settlement selected
    by ``settlement_lag``.  This function never fetches historical data.
    """
    resolved = _resolve_instrument_and_leg(ticker, repo, indices)
    if resolved is None:
        return None
    base_ticker, instrument, indices_eff, _leg, _ticker_u = resolved
    values = dict(_DEFAULTS)
    values.update(params or {})
    settle = _resolve_ref(settlement_lag)

    detail = get_bond_detail(
        ticker,
        repo,
        provider,
        indices_eff,
        fx,
        settlement_lag=settlement_lag,
    )
    if detail is None:
        return None

    try:
        live_snapshot = provider.fetch_snapshots([base_ticker]).get(base_ticker)
    except Exception:  # noqa: BLE001 - live provider degrades explicitly
        live_snapshot = None
    detail["market"]["operations"] = (
        live_snapshot.operations if live_snapshot is not None else None
    )

    setup = _market_setup(instrument, fx)
    _annotate_detail(detail, instrument, setup, indices_eff, fx, settle)
    market = detail["market"]
    quote_price = _num(values["price"])
    if quote_price is None:
        quote_price = _num(market.get("price"))

    warnings: list[str] = []
    if values["price"] is not None:
        warnings.append(
            "Los análisis de Trading y Wealth Management usan el precio ingresado."
        )
    if setup.get("pricing_divisor") is None:
        warnings.append(
            f"No está disponible {setup.get('conversion_basis') or 'el tipo de cambio requerido'}; "
            "se deshabilitan los cálculos que dependen de esa conversión."
        )

    engine_yield = _tir(instrument, quote_price, setup, indices_eff, fx, settle)
    inflation = (_num(values["inflation_pct"]) or 0.0) / 100.0
    projected, projection_assumptions, projection_reason, scenario = _project_cashflows(
        instrument, indices_eff, setup, settle, inflation
    )
    if scenario:
        warnings.append(
            "Los flujos futuros no fijos son valores de escenario, no importes "
            "nominales garantizados."
        )

    trading = _trading(
        instrument,
        market,
        setup,
        indices_eff,
        fx,
        settle,
        values,
        projected,
        projection_reason,
        inflation,
    )
    wealth = _wealth(
        instrument,
        projected,
        projection_reason,
        list(projection_assumptions),
        quote_price,
        engine_yield,
        setup,
        settle,
        values,
    )
    teaching = _teaching(
        instrument,
        projected,
        projection_reason,
        list(projection_assumptions),
        setup,
        indices_eff,
        (
            (_num(values["yield_pct"]) or 0.0) / 100.0
            if values["yield_pct"] is not None
            else engine_yield
        ),
        settle,
        values,
    )

    result = {
        "detail": detail,
        "trading": trading,
        "wealth": wealth,
        "teaching": teaching,
        "warnings": warnings,
    }
    return _finite(result)
