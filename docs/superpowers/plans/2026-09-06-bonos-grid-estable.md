# Bonos Grid Estable Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convertir `/bonos` en una grilla bloqueada por defecto, sin autoajustes ni auto-scroll, con edición transaccional y colisiones que nunca muevan paneles vecinos.

**Architecture:** Un default inmutable y versionado se entrega desde FastAPI. Un controlador JavaScript dedicado valida estado, deriva el motor de GridStack, administra el borrador de edición y persiste sólo al aplicar; el template conserva HTMX y delega exclusivamente la geometría.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, JavaScript sin framework, GridStack 11.5.1, HTMX/SSE, CSS, Playwright para verificación manual instrumentada.

**Spec:** `docs/superpowers/specs/2026-09-06-bonos-grid-estable-design.md`

## Global Constraints

- Ejecutar Python únicamente con `py -3.12`.
- No crear una suite `tests/`; este repositorio valida con Ruff, smoke y navegador.
- No modificar pricing, providers, catálogo ni ciclos HTMX/SSE.
- Mantener GridStack 11.5.1 local; no agregar dependencias ni CDNs.
- Embeber JSON mediante `json_for_script`, nunca con `json.dumps` directo en `<script>`.
- Preservar todos los cambios ajenos ya presentes en el working tree.
- No hacer commit, push, pull ni deploy hasta pedido explícito del usuario.
- Después de cada cambio funcional, actualizar el servidor local y revisar `/bonos` en navegador.

---

## File Map

- `apps/web/dashboard_layout.py`: única fuente del default oficial y constantes de grilla.
- `apps/web/static/js/dashboard_grid.js`: validación, almacenamiento, motor estable y transacción de edición.
- `apps/web/routers/panels.py`: entrega del default; elimina escritura/lectura del archivo runtime.
- `apps/web/templates/pages/index.html`: markup y wiring del controlador con paneles/CONFIG existentes.
- `apps/web/static/css/app.css`: estados bloqueado/editando, grips, barra y feedback de colisión.
- `AGENTS.md`: documentación operativa del nuevo almacenamiento.
- `CLAUDE.md`: copia de arquitectura que también referencia el layout runtime anterior.

---

### Task 1: Default versionado y retiro de rutas

**Files:**
- Create: `apps/web/dashboard_layout.py`
- Modify: `apps/web/routers/panels.py:18-170`

**Interfaces:**
- Produces: `GRID_COLUMNS: int`, `GRID_CELL_HEIGHT: int`, `GRID_MARGIN: int`.
- Produces: `DEFAULT_DASHBOARD_STATE: dict[str, object]` con claves `version`, `layout`, `hidden`, `cols`.
- Consumes: `json_for_script(DEFAULT_DASHBOARD_STATE)` desde el handler de `/bonos`.

- [ ] **Step 1: Crear el default completo del proyecto**

Crear `apps/web/dashboard_layout.py` con constantes de sólo lectura por convención y las diez geometrías:

```python
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
```

- [ ] **Step 2: Entregar constantes y JSON seguro desde `/bonos`**

Importar el nuevo módulo en `apps/web/routers/panels.py` y reemplazar el contexto del template:

```python
from apps.web.dashboard_layout import (
    DEFAULT_DASHBOARD_STATE,
    GRID_CELL_HEIGHT,
    GRID_COLUMNS,
    GRID_MARGIN,
)

return _TEMPLATES.TemplateResponse(
    request,
    "pages/index.html",
    {
        "panels": panels,
        "last_refresh": state.last_refresh,
        "default_layout": json_for_script(DEFAULT_DASHBOARD_STATE),
        "grid_columns": GRID_COLUMNS,
        "grid_cell_height": GRID_CELL_HEIGHT,
        "grid_margin": GRID_MARGIN,
    },
)
```

- [ ] **Step 3: Eliminar el almacenamiento global del servidor**

Eliminar de `apps/web/routers/panels.py`:

- `_LAYOUT_FILE`, `_LAYOUT_MAX_BYTES` y `_read_default_layout()`.
- `save_default_layout()` y `clear_default_layout()`.
- Imports `asyncio`, `json`, `os`, `Path`, `get_current_user_html` y `settings` si quedan sin consumidores.

No agregar reemplazo de escritura: el backend sólo sirve el default versionado.

- [ ] **Step 4: Validar módulo y tabla de rutas**

Run:

```powershell
py -3.12 -m ruff check apps/web/dashboard_layout.py apps/web/routers/panels.py
$env:MONITOR_DISABLE_LOOPS='1'
py -3.12 -c "from apps.web.app import app; routes={(r.path,method) for r in app.routes for method in getattr(r,'methods',set())}; assert ('/bonos','GET') in routes; assert ('/panels/layout','POST') not in routes; assert ('/panels/layout','DELETE') not in routes"
```

Expected: Ruff limpio y proceso con código `0`.

---

### Task 2: Controlador GridStack estable

**Files:**
- Create: `apps/web/static/js/dashboard_grid.js`

**Interfaces:**
- Consumes: `window.GridStack`, elemento `.grid-stack`, default JSON y constantes de grilla.
- Produces: `window.BonosDashboardGrid.create(options) -> DashboardController`.
- Produces methods: `beginEdit()`, `applyEdit()`, `cancelEdit()`, `previewDefault()`, `setPanelVisible(id, visible)`, `isPanelHidden(id)`, `isEditing()`, `getState()`.
- Produces properties: `grid` y `lastError`.
- Emits: `dashboard:modechange`, `dashboard:statechange`, `dashboard:collision`, `dashboard:applyerror` sobre el elemento de grilla.

- [ ] **Step 1: Definir utilidades puras y validación**

Crear un IIFE sin módulos externos:

```javascript
(function (global) {
  "use strict";

  var STORAGE_KEY = "bonos-dashboard-state-v1";
  var LEGACY_KEYS = ["grid-layout-v3", "panels-hidden-v1", "panel-cols-v2", "panel-cols-v1"];

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function positionsOverlap(left, right) {
    return !(left.y + left.h <= right.y || right.y + right.h <= left.y ||
             left.x + left.w <= right.x || right.x + right.w <= left.x);
  }

  function validateState(candidate, panelIds, columns) {
    if (!candidate || typeof candidate !== "object" || candidate.version !== 1 ||
        !Array.isArray(candidate.layout) || !Array.isArray(candidate.hidden) ||
        candidate.layout.length !== panelIds.length) return null;
    var known = new Set(panelIds);
    var seen = new Set();
    var layout = [];
    for (var index = 0; index < candidate.layout.length; index += 1) {
      var raw = candidate.layout[index];
      if (!raw || typeof raw !== "object" || !known.has(raw.id) || seen.has(raw.id)) return null;
      var numbers = [raw.x, raw.y, raw.w, raw.h];
      if (!numbers.every(Number.isInteger) || raw.x < 0 || raw.y < 0 ||
          raw.w < 1 || raw.h < 1 || raw.x + raw.w > columns) return null;
      seen.add(raw.id);
      layout.push({id: raw.id, x: raw.x, y: raw.y, w: raw.w, h: raw.h});
    }
    if (seen.size !== panelIds.length) return null;
    var hidden = new Set(candidate.hidden);
    if (hidden.size !== candidate.hidden.length) return null;
    for (var hiddenId of hidden) if (!seen.has(hiddenId)) return null;
    var visible = layout.filter(function (item) { return !hidden.has(item.id); });
    for (var left = 0; left < visible.length; left += 1) {
      for (var right = left + 1; right < visible.length; right += 1) {
        if (positionsOverlap(visible[left], visible[right])) return null;
      }
    }
    var byId = new Map(layout.map(function (item) { return [item.id, item]; }));
    return {
      version: 1,
      layout: panelIds.map(function (id) { return byId.get(id); }),
      hidden: panelIds.filter(function (id) { return hidden.has(id); }),
    };
  }

  global.BonosDashboardGrid = { create: createDashboardGrid, validateState: validateState };
})(window);
```

La normalización de cada fila conserva sólo `{id, x, y, w, h}` y rechaza propiedades o
tipos inesperados en vez de pasarlos a GridStack.

- [ ] **Step 2: Implementar límites duros**

Definir dentro del mismo IIFE:

```javascript
class StableGridEngine extends GridStack.Engine {
  moveNode(node, options) {
    var proposed = Object.assign({}, node);
    GridStack.Utils.copyPos(proposed, options);
    this.nodeBoundFix(proposed, proposed.w !== node.w || proposed.h !== node.h);
    if (!options.nested && !options.skip && this.collide(node, proposed)) {
      var target = node._event && node._event.target ? node._event.target : node.el;
      if (target) target.dispatchEvent(new CustomEvent("dashboard:collision", {bubbles: true}));
      return false;
    }
    return super.moveNode(node, options);
  }
}
```

No sobreescribir `_fixCollisions`; bloquear antes de entrar en la rama que reubica vecinos.

- [ ] **Step 3: Implementar carga estable y paneles ocultos**

`createDashboardGrid(options)` debe:

1. Enumerar IDs desde `[gs-id]` y validar el default.
2. Limpiar claves legacy de forma idempotente.
3. Leer/validar `bonos-dashboard-state-v1`; usar default si falla.
4. Inicializar GridStack con:

```javascript
var grid = GridStack.init({
  column: options.columns,
  cellHeight: options.cellHeight,
  margin: options.margin,
  float: true,
  animate: false,
  handle: ".layout-drag-handle",
  draggable: {scroll: false},
  resizable: {handles: "e, se"},
  engineClass: StableGridEngine,
}, options.element);
```

5. Cargar geometría en batch, retirar visualmente los IDs de `hidden`, conservar sus
   posiciones en un mapa interno y ejecutar `grid.disable()`.
6. Agregar `dashboard-ready` sólo después de terminar para evitar un flash de auto-layout.

Para mostrar un panel oculto, consultar
`grid.engine.isAreaEmpty(position.x, position.y, position.w, position.h)`. Si devuelve
`false`, pasar `Object.assign({}, position, {autoPosition: true})` a
`grid.makeWidget(item, widgetOptions)` para encontrar un hueco sin mover nodos existentes.

- [ ] **Step 4: Implementar transacción de edición**

Mantener `appliedState`, `draftState`, `editSnapshot` e `editing` dentro del closure:

```javascript
function beginEdit() {
  if (editing) return;
  editSnapshot = captureState();
  draftState = clone(editSnapshot);
  editing = true;
  grid.enable();
  element.classList.add("layout-editing");
  emit("dashboard:modechange");
}

function cancelEdit() {
  if (!editing) return;
  replaceState(editSnapshot);
  finishEdit();
}

function applyEdit() {
  var next = validateState(captureState(), panelIds, columns);
  if (!next || !writeAppliedState(next)) {
    lastError = "No se pudo aplicar";
    emit("dashboard:applyerror");
    return false;
  }
  appliedState = clone(next);
  finishEdit();
  return true;
}
```

`grid.on("change")` actualiza sólo el mapa/borrador. No debe llamar a `localStorage`.
`setPanelVisible` rechaza cambios fuera de edición.

- [ ] **Step 5: Neutralizar auto-scroll y persistir una sola vez**

Al crear el primer controlador de esta página, reemplazar la utilidad usada
incondicionalmente por GridStack durante resize:

```javascript
if (!GridStack.Utils.__bonosResizeScrollDisabled) {
  GridStack.Utils.__bonosResizeScrollDisabled = true;
  GridStack.Utils.updateScrollResize = function () {};
}
```

`writeAppliedState` ejecuta exactamente una mutación sobre la clave espacial:

```javascript
function writeAppliedState(next) {
  try {
    if (JSON.stringify(next) === JSON.stringify(defaultState)) {
      localStorage.removeItem(STORAGE_KEY);
    } else {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    }
    return true;
  } catch (error) {
    return false;
  }
}
```

Si falla, conservar edición y borrador.

- [ ] **Step 6: Verificar sintaxis del controlador**

Run:

```powershell
node --check apps/web/static/js/dashboard_grid.js
```

Expected: sin salida y código `0`.

---

### Task 3: Integración de template y experiencia de edición

**Files:**
- Modify: `apps/web/templates/pages/index.html:1-530`
- Modify: `apps/web/static/css/app.css:95-177`
- Modify: `apps/web/static/css/app.css:373-386`

**Interfaces:**
- Consumes: `BonosDashboardGrid.create(options)` de Task 2.
- Consumes: `default_layout`, `grid_columns`, `grid_cell_height`, `grid_margin` de Task 1.
- Produces: controles DOM `#layout-edit-bar`, `#layout-apply`, `#layout-cancel`, `#layout-default`, `#layout-edit-status`.
- Preserves: filtros, chart, share, modal, SSE y segundo listener HTMX de animación de celdas.

- [ ] **Step 1: Conectar constantes y default seguro**

Reemplazar los `set` hardcodeados por los valores del contexto y cargar el controlador:

```html
<script src="/static/vendor/gridstack/gridstack-all.js"></script>
<script src="/static/js/dashboard_grid.js"></script>
<script id="dashboard-default-state" type="application/json">{{ default_layout|safe }}</script>
```

Usar `grid_columns`, `grid_cell_height` y `grid_margin` en los atributos `data-*`.

- [ ] **Step 2: Agregar grips y barra transaccional**

Dentro de cada `.panel-head`, antes del título:

```html
<button type="button" class="layout-drag-handle"
        aria-label="Mover {{ p.title }}" title="Mover panel">⠿</button>
```

Antes de `.grid-stack`:

```html
<div id="layout-edit-bar" class="layout-edit-bar" hidden>
  <strong>Editando layout</strong>
  <span id="layout-edit-status" role="status" aria-live="polite"></span>
  <button type="button" id="layout-cancel">Cancelar</button>
  <button type="button" id="layout-default">Default</button>
  <button type="button" id="layout-apply">Aplicar</button>
</div>
```

- [ ] **Step 3: Reemplazar inicialización, auto-fit y guardado continuo**

Conservar la generación CSS de 200 columnas y sustituir la llamada a `GridStack.init`, `KEY`,
`fitPanel`, `fitAll`, listeners de resize manual y el `htmx:afterSwap` geométrico por:

```javascript
var defaultState = JSON.parse(document.getElementById("dashboard-default-state").textContent);
var dashboard = BonosDashboardGrid.create({
  element: el,
  defaultState: defaultState,
  columns: COL,
  cellHeight: CELL,
  margin: MARGIN,
});
var grid = dashboard.grid;
```

Quitar también los `delete item.dataset.manual` y las invocaciones de `fitPanel` dentro de `requestAnimationFrame`
de filtros, settlement y apertura de paneles. No tocar el listener HTMX separado que
aplica animaciones `blip-up`/`blip-down` a celdas.

- [ ] **Step 4: Integrar CONFIG con modo edición**

`renderConfigMenu()` debe renderizar:

- Lista de paneles con estado visible/oculto.
- `Alternar Tema Claro/Oscuro`.
- `Editar layout` cuando está bloqueado.
- `Restaurar default` que llama `beginEdit()` y luego `previewDefault()`.
- Sin `Guardar layout como default` y sin `fetch("/panels/layout")`.

Los toggles de paneles llaman `dashboard.setPanelVisible(id, visible)` y quedan
deshabilitados fuera de edición. Los botones X sólo actúan durante edición.

Cablear la barra:

```javascript
editButton.addEventListener("click", function () { dashboard.beginEdit(); });
applyButton.addEventListener("click", function () { dashboard.applyEdit(); });
cancelButton.addEventListener("click", function () { dashboard.cancelEdit(); });
defaultButton.addEventListener("click", function () { dashboard.previewDefault(); });
```

Escuchar eventos `dashboard:*` para actualizar menú, barra, `hidden` y mensajes. En el
handler existente de `Escape`, cancelar edición antes de cerrar menús cuando no hay modal.

- [ ] **Step 5: Agregar estados visuales sin tapar contenido**

Agregar este CSS, ajustando únicamente nombres de variables ya existentes si fuera necesario:

```css
.grid-stack:not(.dashboard-ready) { visibility: hidden; }
.layout-drag-handle { display: none; }
.grid-stack.layout-editing .layout-drag-handle { display: inline-flex; cursor: grab; }
.grid-stack:not(.layout-editing) > .grid-stack-item .ui-resizable-handle { display: none !important; }
.layout-edit-bar { position: sticky; top: var(--header-height, 0); z-index: 25; }
.grid-stack.layout-editing {
  background-image:
    linear-gradient(rgba(35, 102, 255, .10) 1px, transparent 1px),
    linear-gradient(90deg, rgba(35, 102, 255, .10) 1px, transparent 1px);
  background-size: 20px 20px;
}
.grid-stack.layout-editing .grid-stack-item-content { outline: 1px solid var(--accent); }
.grid-stack-item.layout-collision .grid-stack-item-content { outline-color: var(--down); }
```

Usar variables existentes del tema y ampliar `.ui-resizable-e/.ui-resizable-se` sólo en
modo edición. `.ph-x` permanece oculta fuera de edición.

- [ ] **Step 6: Reiniciar y ejecutar smoke visual inicial**

Detener únicamente el proceso que escucha `127.0.0.1:8001`, reiniciar con `py -3.12 run.py`
y abrir `http://127.0.0.1:8001/bonos`.

Expected:

- Se ven siete paneles en la geometría oficial.
- El tablero está bloqueado y sin grips.
- No aparece `Guardar layout como default`.
- `CONFIG → Editar layout` muestra barra, guías y handles.

---

### Task 4: Documentación y verificación de aceptación

**Files:**
- Modify: `AGENTS.md:35-135`
- Modify: `CLAUDE.md:35-120`
- Verify: `apps/web/dashboard_layout.py`
- Verify: `apps/web/static/js/dashboard_grid.js`
- Verify: `apps/web/routers/panels.py`
- Verify: `apps/web/templates/pages/index.html`
- Verify: `apps/web/static/css/app.css`

**Interfaces:**
- Consumes: feature completa de Tasks 1-3.
- Produces: documentación sin referencias al archivo/rutas retiradas y evidencia de cada criterio.

- [ ] **Step 1: Actualizar documentación operativa**

En `AGENTS.md` y `CLAUDE.md`:

- Quitar `dashboard_layout.json` de los artefactos derivados de `db_dir`.
- Reemplazar la descripción `POST/DELETE /panels/layout` por default versionado y
  preferencia local aplicada explícitamente.
- Quitar esas rutas de la lista de endpoints autenticados.
- Documentar que los refrescos HTMX nunca cambian geometría.

- [ ] **Step 2: Verificar carga estable durante refrescos**

En Playwright, instalar instrumentación antes de navegar que envuelva
`Storage.prototype.setItem`, registre la clave `bonos-dashboard-state-v1` y tome snapshots
de `{id,x,y,w,h}`. Navegar a `/bonos`, esperar carga inicial y dos refrescos SSE.

Expected:

```text
loading_panels = 0
layout_writes = 0
geometry_changes_after_ready = 0
console_errors = 0
```

- [ ] **Step 3: Verificar bloqueo, colisiones y viewport**

Automatizar estas maniobras:

1. Intentar drag y resize bloqueado: geometría idéntica.
2. Entrar en edición y agrandar Tasa Fija contra Panel Líder.
3. Mover Bonares contra Tasa Fija.
4. Redimensionar Panel Líder sosteniendo el puntero junto al borde inferior.

Expected:

```text
non_active_node_changes = 0
scroll_delta_px = 0
collision_feedback_visible = true
```

- [ ] **Step 4: Verificar transacción y migración**

Probar en un contexto limpio y otro con claves legacy:

1. Editar y cancelar: snapshot exacto, cero escrituras.
2. Editar y aplicar: una mutación de `bonos-dashboard-state-v1` y persistencia tras reload.
3. Pulsar Default y cancelar: vuelve al estado aplicado anterior.
4. Pulsar Default y aplicar: clave local eliminada, columnas visibles y geometría oficial.
5. Inyectar JSON inválido: fallback al default sin excepción.
6. Verificar que claves legacy ya no existan.

- [ ] **Step 5: Ejecutar gates del repositorio**

Run:

```powershell
py -3.12 -m ruff check .
$env:MONITOR_DISABLE_LOOPS='1'
py -3.12 run.py
```

Con el smoke activo, verificar:

```text
GET    /bonos          -> 200
POST   /panels/layout  -> 404
DELETE /panels/layout  -> 404
```

Expected: imports limpios, templates compilados, rutas correctas y sin traceback.

- [ ] **Step 6: Revisar visualmente dos viewports**

Abrir `/bonos` en `1910 × 900` y `1366 × 768`. Comparar el viewport grande con la captura
del usuario y revisar modo bloqueado, CONFIG, modo edición, scroll interno y feedback rojo.

Dejar el servidor normal activo en `http://127.0.0.1:8001/bonos` para revisión del usuario.

---

## Completion Evidence

La implementación se considera terminada sólo si se conservan juntos:

- Salida limpia de Ruff.
- Smoke de rutas con `200/404/404`.
- Auditoría de dos refrescos con cero cambios y cero escrituras.
- Auditoría de colisiones con cero vecinos modificados.
- Auditoría de resize con delta de scroll igual a cero.
- Persistencia/cancelación/default demostrados tras recarga.
- Capturas visuales de ambos viewports.
- Servidor local activo para revisión.
