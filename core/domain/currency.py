"""Currency helpers — ticker suffix → moneda canónica.

Convención: sufijo D=MEP, C=CABLE, resto=ARS.  Aplica a soberanos,
BOPREALES y ONs multi-pata. Un único punto de verdad para que repositorios,
infraestructura y capa web no re-implementen la misma regla.
"""
from __future__ import annotations


def ccy_from_suffix(ticker: str) -> str:
    """Moneda de una especie por su sufijo: D=MEP, C=CABLE, resto=ARS."""
    t = (ticker or "").upper()
    if t.endswith("D"):
        return "MEP"
    if t.endswith("C"):
        return "CABLE"
    return "ARS"


_USD_TYPES = ("BONAR", "GLOBAL", "BOPREAL")
_USD_TOKENS = ("HARD DOLLAR", "DOLAR LINKED", "DOLLAR LINKED",
               "DOLAR_LINKED", "DOLLAR_LINKED")

def _pays_usd(instrument_type: str) -> bool:
    t = (instrument_type or "").upper().strip()
    return t in _USD_TYPES or any(tok in t for tok in _USD_TOKENS)

def position_currency(instrument_type: str, ticker: str) -> str:
    """USD para patas MEP/CABLE de tipos que cotizan en USD; ARS para el resto."""
    if _pays_usd(instrument_type) and ccy_from_suffix(ticker) in ("MEP", "CABLE"):
        return "USD"
    return "ARS"
