"""Schema declarativo de los paneles de bonos: columnas por panel + registro
`PANELS` (id -> titulo/tipos/columnas) + sets de comportamiento (filtros de moneda,
plazo CI, resalte de columna). Es data pura, separada de los builders/rutas de
`panels.py` para que agregar o editar un panel sea un solo lugar declarativo.
"""

# --- Column schemas (espejo de server._get_columns para los paneles de bonos) --- #
_BONARES_COLS = [
    {"key": "ticker", "label": "Ticker", "kind": "text"},
    {"key": "vto", "label": "Vto", "kind": "date"},
    {"key": "days_next_coupon", "label": "Próx Cup", "kind": "number", "decimals": 0},
    {"key": "price", "label": "Precio", "kind": "number", "decimals": 2},
    {"key": "technical_value", "label": "V.Téc", "kind": "number", "decimals": 2},
    {"key": "parity", "label": "Paridad", "kind": "percent", "decimals": 2},
    {"key": "tir", "label": "TIR", "kind": "percent", "decimals": 2},
    {"key": "duration", "label": "MD", "kind": "number", "decimals": 2},
    {"key": "change_pct", "label": "%Día", "kind": "percent_signed", "decimals": 2},
    {"key": "volume", "label": "Vol $", "kind": "volume"},
]
_BOPREALES_COLS = [
    c for c in _BONARES_COLS if c["key"] not in {"days_next_coupon", "technical_value"}
]
_CER_COLS = [
    {"key": "ticker", "label": "Ticker", "kind": "text"},
    {"key": "category", "label": "Categoría", "kind": "text"},
    {"key": "vto", "label": "Vto", "kind": "date"},
    {"key": "price", "label": "Precio", "kind": "number", "decimals": 2},
    {"key": "parity", "label": "Paridad", "kind": "percent", "decimals": 2},
    {"key": "tir", "label": "TIR", "kind": "percent", "decimals": 2},
    {"key": "duration", "label": "DM", "kind": "number", "decimals": 2},
    {"key": "change_pct", "label": "Var%", "kind": "percent_signed", "decimals": 2},
    {"key": "volume", "label": "Vol $", "kind": "volume"},
]
_TASA_FIJA_COLS = [
    {"key": "ticker", "label": "Ticker", "kind": "text"},
    {"key": "dias", "label": "Días", "kind": "number", "decimals": 0},
    {"key": "price", "label": "Precio", "kind": "number", "decimals": 2},
    {"key": "technical_value", "label": "V.Téc", "kind": "number", "decimals": 2},
    {"key": "parity", "label": "Paridad", "kind": "percent", "decimals": 2},
    {"key": "tir", "label": "TIR/TEA", "kind": "percent", "decimals": 2},
    {"key": "tna", "label": "TNA(365)", "kind": "percent", "decimals": 2},
    {"key": "tem", "label": "TEM(365)", "kind": "percent", "decimals": 2},
    {"key": "duration", "label": "DM", "kind": "number", "decimals": 2},
    {"key": "change_pct", "label": "Var %", "kind": "percent_signed", "decimals": 2},
    {"key": "volume", "label": "Vol $", "kind": "volume"},
]
_TAMAR_COLS = [
    {"key": "ticker", "label": "Ticker", "kind": "text"},
    {"key": "vto", "label": "Vto", "kind": "date"},
    {"key": "dias", "label": "Días", "kind": "number", "decimals": 0},
    {"key": "price", "label": "Precio", "kind": "number", "decimals": 2},
    {"key": "tir", "label": "TIR (TEA)", "kind": "percent", "decimals": 2},
    {"key": "duration", "label": "MD", "kind": "number", "decimals": 2},
    {"key": "change_pct", "label": "%Día", "kind": "percent_signed", "decimals": 2},
    {"key": "volume", "label": "Vol $", "kind": "volume"},
]

_PANEL_LIDER_COLS = [
    {"key": "ticker", "label": "Ticker", "kind": "text"},
    {"key": "bid", "label": "Compra", "kind": "number", "decimals": 2},
    {"key": "ask", "label": "Venta", "kind": "number", "decimals": 2},
    {"key": "mid", "label": "Mid", "kind": "number", "decimals": 2},
    {"key": "change_pct", "label": "Día %", "kind": "percent_signed", "decimals": 2},
    {"key": "volume", "label": "Vol $", "kind": "volume"},
    {"key": "operations", "label": "Ops", "kind": "number", "decimals": 0},
]
_FUTUROS_COLS = [
    {"key": "ticker", "label": "Contrato", "kind": "text"},
    {"key": "vto", "label": "Vto", "kind": "date"},
    {"key": "bid", "label": "Compra", "kind": "number", "decimals": 2},
    {"key": "ask", "label": "Venta", "kind": "number", "decimals": 2},
    {"key": "last", "label": "Último", "kind": "number", "decimals": 2},
    {"key": "settle", "label": "Ajuste", "kind": "number", "decimals": 2},
    {"key": "tna", "label": "TNA", "kind": "percent", "decimals": 2},
    {"key": "open_interest", "label": "OP.INT", "kind": "volume"},
    {"key": "volume", "label": "Vol", "kind": "volume"},
]
_BEI_TENOR_COLS = [
    {"key": "plazo", "label": "Plazo", "kind": "text"},
    {"key": "dias", "label": "Días", "kind": "number", "decimals": 0},
    {"key": "tea_nominal", "label": "TEA Nom", "kind": "percent", "decimals": 2},
    {"key": "tea_real", "label": "TEA Real", "kind": "percent", "decimals": 2},
    {"key": "tamar_fwd", "label": "TAMAR fwd", "kind": "percent", "decimals": 2},
    {"key": "bei_spot", "label": "BEI spot", "kind": "percent", "decimals": 2},
    {"key": "bei_fwd", "label": "BEI fwd", "kind": "percent", "decimals": 2},
    {"key": "bei_g_adj", "label": "BEI γ-adj", "kind": "percent", "decimals": 2},
    {"key": "bei_tamar", "label": "BEI TAMAR", "kind": "percent", "decimals": 2},
    {"key": "dev_implicita", "label": "Deval DLR", "kind": "percent", "decimals": 2},
    {"key": "tc_real", "label": "TC real", "kind": "percent_signed", "decimals": 2},
]
_BEI_SENDERO_COLS = [
    {"key": "mes", "label": "Mes", "kind": "text"},
    {"key": "dias_mes", "label": "Días", "kind": "number", "decimals": 0},
    {"key": "bei_mensual", "label": "BEI mensual", "kind": "percent", "decimals": 2},
    {"key": "rem_mensual", "label": "REM mensual", "kind": "percent", "decimals": 2},
    {"key": "diff", "label": "BEI − REM", "kind": "percent_signed", "decimals": 2},
]
_BEI_TABLE_KEY = {"bei_tenor": "tenor", "bei_sendero": "sendero"}

# id -> (título, {instrument_types}, columnas). TODO panel de acá está en PANEL_ORDER:
# los del monitor que quedaron sin UI (ON, provinciales, valor relativo, BEI pares) se
# retiraron del registro en vez de dejarlos alcanzables sólo por URL.
PANELS = {
    "bonares": ("BONARES Y GLOBALES", {"BONAR", "GLOBAL"},
                [c for c in _BONARES_COLS if c["key"] != "technical_value"]),
    "bopreales": ("BOPREALES", {"BOPREAL"}, _BOPREALES_COLS),
    "cer": ("BONOS CER", {"CER", "LECER", "BONCER", "BONCER ZC", "CON CUPON", "STEP-UP"}, _CER_COLS),
    "tasa_fija": ("TASA FIJA", {"LECAP", "BONCAP", "BONOFIJA"}, _TASA_FIJA_COLS),
    "dolar_linked": ("DOLAR LINKED", {"DOLAR_LINKED"}, _BONARES_COLS),
    "tamar": ("TAMAR / DUAL", {"PURO", "DUAL", "DUAL_CER_TAMAR"}, _TAMAR_COLS),
    "panel_lider": ("PANEL LÍDER · acciones", set(), _PANEL_LIDER_COLS),
    "futuros": ("FUTUROS DLR (Matba/Rofex)", set(), _FUTUROS_COLS),
    "bei_tenor": ("BEI POR TENOR (NSS + Fisher)", set(), _BEI_TENOR_COLS),
    "bei_sendero": ("SENDERO MENSUAL · BEI vs REM-BCRA", set(), _BEI_SENDERO_COLS),
}
PANEL_ORDER = ["bonares", "cer", "tasa_fija", "tamar", "dolar_linked", "bopreales",
               "panel_lider", "futuros",
               "bei_tenor", "bei_sendero"]

# Fetch historical returns only for instrument types with an active consumer.
HISTORY_TYPES = frozenset(
    kind for pid in PANEL_ORDER
    if any(c["key"] in {"var_7d", "var_30d", "var_90d", "var_ytd", "var_1y"}
           for c in PANELS[pid][2])
    for kind in PANELS[pid][1]
)

# Paneles cuyas especies cotizan en 3 monedas (mismo bono): se les agrega el filtro
# ARS/MEP/CABLE en el header (default MEP). La moneda se deriva del sufijo del ticker
# (D=MEP, C=CABLE, resto=ARS). BOPREALes incluidos: cotizan en pesos (base BPO*),
# MEP (…D) y cable (…C) — la pata pesos se linkea por ISIN (ver backfill_legs_from_universe).
CCY_FILTER_PANELS = {"bonares", "bopreales"}

# Paneles que solo muestran especies CON precio de mercado (una pata sin cotización no
# genera fila). Hoy ninguno: era el panel de ONs; en soberanos/CER el backstop de
# cierre previo ya cubre, y un faltante se nota más.
PRICE_REQUIRED_PANELS: set = set()

# Paneles con filtro de ley aplicable (AR / EXT) en el header. Hoy ninguno (era ON y
# provinciales); la plomería (`data-ley` en la fila, `_ley_of`) queda para reactivarlo.
LEY_FILTER_PANELS: set = set()

# Paneles con selector de plazo de liquidación CI (T+0) / 24hs (T+1). El precio y
# todo lo que deriva de él (TIR/paridad/MD/V.Téc) se recalcula on-demand para el
# plazo elegido desde el snapshot CI del hub (BYMA trae ambos plazos en una llamada).
# BONARES (soberanos USD, 3 monedas) y CER (peso ajustado: el plazo además mueve el
# ref de indexación CER de la V.Téc, no solo el descuento — ver _ci_metrics/settle_lag).
SETTLE_FILTER_PANELS = {"bonares", "cer"}

# Paneles donde se resalta la columna TIR (fondo accent, mismo efecto que la
# `sortcol` del FCI) para distinguirla rápido: TODOS los paneles de bonos que
# tienen columna TIR — soberanos (CER / Tasa Fija / TAMAR / Dólar Linked / Bonares
# / Bopreales). Se aplica en el panel del
# dashboard y en el popup de compartir (la foto).
_TIR_HL_PANELS = {pid for pid, (_t, _types, _cols) in PANELS.items()
                  if any(c.get("key") == "tir" for c in _cols)}
# Columna a resaltar (fondo accent) por panel — en el dashboard Y en la foto. Por defecto
# la TIR (soberanos/CER/ON/DL/TAMAR/VR…), pero TASA FIJA resalta la TNA: son instrumentos
# a tasa fija (en general <1 año) que se comparan por tasa devengada nominal (TNA), no por
# TIR. Panel sin entrada → sin resalte.
_HL_COL_KEY = {pid: "tir" for pid in _TIR_HL_PANELS}
_HL_COL_KEY["tasa_fija"] = "tna"
