from typing import Final

GRID_COLUMNS: Final = 200
GRID_CELL_HEIGHT: Final = 5
GRID_MARGIN: Final = 5

_PANEL_IDS: Final = (
    "bonares", "cer", "tasa_fija", "tamar", "dolar_linked",
    "bopreales", "panel_lider", "futuros", "bei_tenor", "bei_sendero",
)

DEFAULT_DASHBOARD_STATE: Final[dict[str, object]] = {
    "version": 1,
    "layout": [
        {"id": "bopreales", "x": 0, "y": 0, "w": 55, "h": 45},
        {"id": "tasa_fija", "x": 55, "y": 0, "w": 66, "h": 83},
        {"id": "cer", "x": 121, "y": 0, "w": 76, "h": 167},
        {"id": "bonares", "x": 0, "y": 45, "w": 55, "h": 101},
        {"id": "panel_lider", "x": 55, "y": 83, "w": 66, "h": 128},
        {"id": "tamar", "x": 0, "y": 146, "w": 55, "h": 86},
        {"id": "dolar_linked", "x": 121, "y": 167, "w": 76, "h": 33},
        {"id": "futuros", "x": 0, "y": 232, "w": 200, "h": 74},
        {"id": "bei_tenor", "x": 0, "y": 306, "w": 200, "h": 74},
        {"id": "bei_sendero", "x": 0, "y": 380, "w": 200, "h": 74},
    ],
    "hidden": ["futuros", "bei_tenor", "bei_sendero"],
    "cols": {panel_id: [] for panel_id in _PANEL_IDS},
}
