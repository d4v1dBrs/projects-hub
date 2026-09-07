# Diseño: grilla estable y edición controlada en Bonos Argy

**Fecha:** 2026-09-06
**Estado:** aprobado en conversación, pendiente de revisión del archivo
**Vista afectada:** `/bonos`

## 1. Contexto

La grilla actual usa GridStack 11.5.1 con 200 columnas, celdas verticales de 5 px,
`float: false`, drag desde todo el encabezado y resize por los bordes este y sudeste.
Además, `fitPanel()` recalcula la altura después de cargas y refrescos HTMX, y el evento
`change` persiste cada geometría producida por GridStack.

La instrumentación del comportamiento actual confirmó:

- 21 escrituras/reacomodos del layout durante 6,2 segundos sin interacción.
- Al crecer Tasa Fija 20 unidades, Panel Líder también se desplazó 20 unidades.
- Mantener un resize cerca del borde inferior desplazó el viewport 36 px.
- El layout guardado por el usuario cambió sólo por cargar filas y recibir refrescos.
- Anular `GridStack.Utils.updateScrollResize` mantuvo el viewport exactamente en el
  mismo `scrollY` durante la misma maniobra de resize.
- Un motor derivado de `GridStack.Engine` pudo rechazar movimientos y tamaños con
  colisión sin alterar el panel vecino.

## 2. Objetivos

1. Ningún dato, filtro, refresco HTMX o carga inicial debe cambiar la geometría.
2. Ningún panel debe moverse accidentalmente durante el uso normal.
3. Mover o redimensionar un panel no debe empujar a otro.
4. El viewport no debe desplazarse automáticamente durante drag o resize.
5. Las modificaciones deben ser transaccionales: aplicar o cancelar todo el borrador.
6. El layout actual del usuario debe quedar como default versionado del proyecto.
7. Debe desaparecer la capacidad de escribir un default global en el servidor.

## 3. No objetivos

- Reemplazar GridStack por otro motor.
- Rediseñar el contenido, tablas, filtros o cálculos financieros de los paneles.
- Crear sincronización de layouts entre navegadores o usuarios.
- Agregar autenticación para guardar preferencias.
- Rediseñar la experiencia móvil; se conservará el comportamiento responsivo vigente.
- Modificar los ciclos SSE/HTMX o la frecuencia de actualización de datos.

## 4. Decisiones aprobadas

### 4.1 Modelo de interacción

- Se conserva GridStack, estabilizado mediante configuración y un motor de colisiones
  local.
- La grilla comienza siempre bloqueada con drag y resize deshabilitados.
- El modo edición se inicia desde `CONFIG → Editar layout`.
- Al editar aparece una barra temporal y persistente con `Cancelar`, `Default` y
  `Aplicar`.
- Sólo un grip dedicado mueve el panel. El encabezado completo deja de ser handle.
- Los handles de resize son más grandes y sólo se muestran durante la edición.
- Los botones, filtros, tablas y barras de scroll nunca inician drag.

### 4.2 Altura

- La altura queda fija en unidades de GridStack.
- El contenido excedente usa el scroll interno existente de `.panel-body`.
- Se eliminan `fitPanel`, `fitAll`, `MINROWS`, `FIT_PAD` y todas sus invocaciones.
- `htmx:afterSwap`, filtros de moneda/ley y cambios de settlement no modifican tamaños.

### 4.3 Colisiones

- Las colisiones se comportan como límites duros.
- El panel activo se queda en la última posición o tamaño válido.
- Los demás nodos conservan exactamente sus coordenadas y dimensiones.
- El panel activo muestra un borde rojo breve cuando la posición propuesta está
  ocupada.

### 4.4 Persistencia

- `Aplicar` guarda una preferencia local en ese navegador.
- `Cancelar` y `Escape` restauran la instantánea tomada al entrar en edición.
- Ningún evento `change` escribe directamente en `localStorage`.
- El default oficial sólo se modifica en el código del proyecto.

## 5. Default oficial

El default se declara en `apps/web/dashboard_layout.py` como
`DEFAULT_DASHBOARD_STATE`. El módulo no realiza I/O y expone un objeto serializable
con `version`, `layout`, `hidden` y `cols`. `layout` contiene los diez paneles aunque
algunos estén ocultos, para recordar dónde reaparecen. `cols` contiene arrays vacíos,
por lo que todas las columnas son visibles por default.

La grilla conserva estas constantes:

- Columnas: `200`.
- Alto de celda: `5 px`.
- Margen: `5 px`.
- Mínimo por panel: `28 × 8` unidades.

### 5.1 Geometría

| Panel | x | y | w | h | Estado inicial |
|---|---:|---:|---:|---:|---|
| `bopreales` | 0 | 0 | 55 | 45 | visible |
| `tasa_fija` | 55 | 0 | 66 | 83 | visible |
| `cer` | 121 | 0 | 76 | 167 | visible |
| `bonares` | 0 | 45 | 55 | 101 | visible |
| `panel_lider` | 55 | 83 | 66 | 128 | visible |
| `tamar` | 0 | 146 | 55 | 86 | visible |
| `dolar_linked` | 121 | 167 | 76 | 33 | visible |
| `futuros` | 0 | 232 | 200 | 74 | oculto |
| `bei_tenor` | 0 | 306 | 200 | 74 | oculto |
| `bei_sendero` | 0 | 380 | 200 | 74 | oculto |

Los paneles inicialmente ocultos son `futuros`, `bei_tenor` y `bei_sendero`. Todas las
columnas de todos los paneles quedan visibles por default.

## 6. Arquitectura

### 6.1 Default del servidor

`apps/web/dashboard_layout.py` tendrá una sola responsabilidad: definir y devolver el
estado oficial. `apps/web/routers/panels.py` lo serializa mediante `json_for_script` y
lo entrega al template de `/bonos`.

Se elimina el flujo basado en el archivo externo `dashboard_layout.json`:

- Se elimina `_LAYOUT_FILE`.
- Se elimina `_read_default_layout()`.
- Se eliminan `POST /panels/layout` y `DELETE /panels/layout`.
- Se limpian imports y dependencias usados exclusivamente por esas rutas.
- Un archivo viejo que permanezca en `db_dir` queda inerte y nunca vuelve a leerse.

### 6.2 Controlador del navegador

`apps/web/static/js/dashboard_grid.js` encapsula:

- `StableGridEngine`: política de colisiones duras.
- Validación y normalización del estado persistido.
- Carga del default o preferencia local.
- Bloqueo/desbloqueo de GridStack.
- Instantánea, borrador, aplicar, cancelar y restaurar default.
- Estado visual del modo edición.
- Persistencia de la geometría y paneles visibles.
- Neutralización del auto-scroll de drag y resize.

El template conserva la lógica SSR/HTMX y las acciones funcionales de los paneles, pero
delega el ciclo de vida espacial al controlador.

### 6.3 Template y estilos

`apps/web/templates/pages/index.html`:

- Incluye `dashboard_grid.js` después de GridStack.
- Inserta el default en JSON seguro.
- Agrega el grip dedicado y la barra temporal de edición.
- Reemplaza la acción `Guardar layout como default` por `Editar layout`.
- Mantiene `Restaurar default` sin llamadas al servidor.
- Quita el auto-fit y la persistencia desde `grid.on("change")`.

`apps/web/static/css/app.css`:

- Oculta grips y handles en modo bloqueado.
- Dibuja guías y bordes azules durante edición.
- Amplía el área alcanzable de los handles sin cubrir el scroll en modo normal.
- Muestra la colisión rechazada en rojo.
- Distingue claramente el estado `layout-editing`.

## 7. Motor estable

`StableGridEngine` deriva de `GridStack.Engine` y sobreescribe `moveNode`.

Antes de delegar al motor original:

1. Construye la geometría propuesta usando la posición actual y las opciones recibidas.
2. Aplica los límites normales de la grilla.
3. Comprueba intersecciones con los otros nodos.
4. Si la operación primaria colisiona, devuelve `false` sin llamar a la lógica que
   reubica vecinos.
5. Si no colisiona, delega a `super.moveNode()`.

La validación se aplica tanto a drag como a resize. La carga inicial sólo acepta estados
sin solapamientos, por lo que no necesita resolver colisiones.

La instancia de GridStack usa:

- `float: true`, para conservar huecos y evitar compactación automática.
- `animate: false`, para que no parezca que otros paneles se desplazan.
- `draggable.scroll: false`, para evitar scroll durante drag.
- Drag y resize deshabilitados inmediatamente después de cargar el estado.

GridStack 11.5.1 ejecuta el auto-scroll de resize de forma incondicional. El controlador
neutraliza `GridStack.Utils.updateScrollResize` para esta página. `/bonos` contiene una
sola grilla, por lo que no afecta otro componente.

## 8. Estado local

La clave nueva es `bonos-dashboard-state-v1`:

```json
{
  "version": 1,
  "layout": [
    {"id": "bopreales", "x": 0, "y": 0, "w": 55, "h": 45}
  ],
  "hidden": ["futuros", "bei_tenor", "bei_sendero"]
}
```

El estado persistido conserva geometría para paneles visibles y ocultos. Si se muestra
un panel cuyo lugar ya está ocupado, se ubica en el primer espacio libre debajo del
tablero sin mover otros nodos.

La validación exige:

- Objeto con `version === 1`.
- `layout` y `hidden` como arrays.
- Exactamente una entrada de geometría por cada panel activo.
- Coordenadas y tamaños enteros, finitos, positivos y dentro de las 200 columnas.
- Ningún solapamiento entre paneles visibles.
- `hidden` contiene sólo IDs conocidos presentes en `layout`, sin duplicados.

Un panel es visible cuando está en `layout` y no está en `hidden`; conservar una entrada
de geometría para un panel oculto no lo vuelve visible.

Un estado inválido se elimina y se sustituye por el default oficial.

Las claves anteriores se eliminan una sola vez al cargar el nuevo controlador:

- `grid-layout-v3`
- `panels-hidden-v1`
- `panel-cols-v2`
- `panel-cols-v1`

`panel-cols-v3` continúa almacenando las columnas ocultas porque esa preferencia no
forma parte de la geometría. Aplicar el default también elimina `panel-cols-v3` para
volver a mostrar todas las columnas.

## 9. Ciclo de interacción

### 9.1 Carga

1. Parsear y validar el default embebido.
2. Parsear y validar la preferencia local.
3. Elegir preferencia válida o default.
4. Cargar GridStack una sola vez y aplicar paneles ocultos en modo batch.
5. Bloquear drag y resize.
6. Activar HTMX normalmente.

No se persiste nada durante esta secuencia.

### 9.2 Entrar en edición

1. El usuario elige `CONFIG → Editar layout`.
2. Se toma una copia profunda de geometría y paneles ocultos.
3. Se habilitan drag y resize.
4. Se agrega `layout-editing` al documento y se muestra la barra temporal.
5. Los toggles de visibilidad pasan a modificar el borrador.
6. Los botones de cerrar panel aparecen únicamente durante edición.

### 9.3 Aplicar

1. Validar el borrador completo.
2. Escribir una vez `bonos-dashboard-state-v1`.
3. Si el borrador representa el default, eliminar esa clave en vez de duplicarlo.
4. Si se aplicó `Default`, eliminar también `panel-cols-v3`.
5. Bloquear GridStack y cerrar el modo edición.

### 9.4 Cancelar

1. Ejecutar una actualización batch.
2. Restaurar exactamente geometría y visibilidad de la instantánea.
3. No escribir en almacenamiento.
4. Bloquear GridStack y cerrar el modo edición.

`Escape` ejecuta la misma ruta. Una recarga del navegador durante edición descarta el
borrador porque nunca fue persistido.

### 9.5 Default

`Default` carga el estado oficial como borrador para previsualizarlo. Todavía puede
cancelarse. Sólo `Aplicar` elimina la personalización local.

## 10. Actualizaciones de datos

Los swaps HTMX continúan reemplazando únicamente el contenido del `<tbody>`. No existe
ningún listener posterior que llame a `grid.update`, cambie `gs-h` o persista el layout.

Los filtros de moneda, ley y settlement conservan su comportamiento funcional, pero ya
no borran flags manuales ni solicitan ajustes de altura. La tabla se desplaza dentro del
alto asignado al panel.

## 11. Manejo de errores

- **Preferencia inválida:** eliminar clave, registrar advertencia en consola y cargar
  default.
- **Default inválido:** no inicializar personalización; conservar el fallback SSR
  apilado y registrar error visible en consola.
- **`localStorage` no disponible o sin cuota:** mantener edición abierta, mostrar
  `No se pudo aplicar` y conservar el borrador para reintentar o cancelar.
- **Colisión:** rechazar sólo la propuesta, marcar brevemente el panel activo y mantener
  todo el estado previo.
- **GridStack ausente:** no ejecutar el controlador; los paneles quedan como bloques SSR.
- **Panel oculto sin posición libre:** ubicarlo al final del tablero, nunca reacomodar
  nodos existentes.

## 12. Accesibilidad y seguridad de interacción

- `Editar layout`, `Aplicar`, `Cancelar` y `Default` son botones reales.
- El estado de edición se expone con `aria-pressed` y texto visible.
- El grip dedicado tiene nombre accesible `Mover <título del panel>`.
- `Escape` cancela sin persistir.
- Los controles internos detienen `pointerdown` para no iniciar drag.
- El modo bloqueado mantiene completa interacción con tablas, scrolls, filtros y modales.

## 13. Criterios de aceptación

1. Dos refrescos HTMX completos producen cero cambios de `x`, `y`, `w` o `h`.
2. Dos refrescos HTMX completos producen cero escrituras de la clave de layout.
3. En modo bloqueado no puede iniciarse drag ni resize.
4. Un resize junto al borde del viewport cambia `scrollY` en 0 px.
5. Una colisión de drag deja todos los paneles distintos del activo sin cambios.
6. Una colisión de resize deja todos los paneles distintos del activo sin cambios.
7. `Cancelar` restaura exactamente el snapshot inicial y no escribe en almacenamiento.
8. `Aplicar` realiza una sola mutación de la clave de estado y sobrevive a una recarga.
9. `Default` reproduce la tabla de geometría de la sección 5.1.
10. Futuros, BEI Tenor y BEI Sendero arrancan ocultos; los demás, visibles.
11. Todas las columnas arrancan visibles después de aplicar el default.
12. `POST /panels/layout` y `DELETE /panels/layout` responden `404`.
13. `GET /bonos` responde `200`, carga filas y no registra errores JavaScript.

## 14. Verificación

No se agrega una suite nueva porque el repositorio no tiene tests. La validación será:

1. `py -3.12 -m ruff check .`
2. Smoke con `MONITOR_DISABLE_LOOPS=1` verificando import, rutas y compilación de templates.
3. Instrumentación Playwright de geometría, escrituras y `scrollY`.
4. Pruebas de carga, editar, colisionar, cancelar, aplicar, recargar y restaurar default.
5. Revisión visual en `1910 × 900` y `1366 × 768`.
6. Consola del navegador sin errores.
7. Servidor local activo en `http://127.0.0.1:8001/bonos` para revisión del usuario.

## 15. Archivos previstos

- Nuevo: `apps/web/dashboard_layout.py`
- Nuevo: `apps/web/static/js/dashboard_grid.js`
- Modificado: `apps/web/routers/panels.py`
- Modificado: `apps/web/templates/pages/index.html`
- Modificado: `apps/web/static/css/app.css`
- Modificado: `AGENTS.md`, sólo si su descripción del layout necesita actualizarse

No se modifican cálculos financieros, proveedores, modelos, repositorios ni datos del
catálogo.
