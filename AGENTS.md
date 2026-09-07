# AGENTS.md — Guía del codebase (web personal + terminal de bonos)

## MANDATO PRIORITARIO PARA TODA IA — LEER COMPLETO ANTES DE ACTUAR

Este archivo es la guía operativa canónica del repositorio. Toda IA debe leerlo completo —y
cualquier `AGENTS.md` más profundo que aplique— antes de analizar, proponer, editar, ejecutar o
validar trabajo del proyecto. Estas reglas tienen prioridad sobre skills, prompts auxiliares y
convenciones genéricas, pero **nunca** pueden desplazar instrucciones de sistema, desarrollador o
usuario de mayor jerarquía. Si existe un conflicto, declararlo y seguir la instrucción superior.

### Estándar de ingeniería

- Prioridad: **correctitud financiera/funcional → seguridad → integridad de datos → mantenibilidad
  → rendimiento medido → velocidad**. Nunca invertir ese orden por conveniencia.
- Resolver la causa raíz con el menor cambio coherente; preservar contratos/firmas y evitar
  refactors, renombres, dependencias o abstracciones ajenos a la tarea.
- No inventar comportamiento, datos ni convenciones: verificar código, configuración, fuente
  primaria, historial o runtime según corresponda.
- Mantener código simple y explícito. Optimizar sólo cuellos identificados; evitar N+1, I/O repetido,
  caches sin cota, bloqueo del event loop y concurrencia que altere el pricing determinista.
- Validar bordes y usar errores/observabilidad específicos; no ocultar fallas con `except Exception`,
  defaults silenciosos, datos sintéticos o degradaciones no reportadas.

### Flujo obligatorio por tarea

1. **Estado**: `git status --short --branch`; detectar alcance y cambios ajenos. Nunca sobrescribir,
   revertir ni limpiar trabajo del usuario.
2. **Contexto**: localizar con `rg --files`/`rg -n`; leer sólo archivos, callers, contratos, config y
   docs relevantes. Usar `git log`/`git blame` sólo ante ambigüedad real.
3. **Riesgo**: clasificar documentación, UI, comportamiento, transversal, finanzas, auth/seguridad,
   esquema/DB, proveedor u operaciones.
4. **Resultado**: antes de editar, fijar aceptación, invariantes y checks. Diseño breve si es acotado;
   plan por fases sólo con dependencias, ambigüedad o riesgo.
5. **Cambio**: una tarea coherente, diff mínimo y estilo existente; registrar problemas laterales sin
   ampliar alcance.
6. **Evidencia**: check específico primero, luego amplio; revisar diff/estado. No afirmar éxito sin
   salida fresca verificable.
7. **Entrega**: informar archivos, comandos/resultados, riesgos y partes no validadas; ausencia de
   errores no prueba exactitud.

### Uso eficiente de contexto y herramientas

- Mapear primero; usar búsquedas y rangos pequeños. No volcar repo, archivos completos, dependencias,
  generados ni logs extensos.
- Reutilizar contexto confirmado, agrupar comandos y no releer tras `apply_patch` salvo check puntual.
- Paralelizar sólo 2+ investigaciones independientes y read-heavy: máximo dos agentes por defecto,
  sin estado/archivos compartidos y con integración única. Nunca editar el mismo archivo en paralelo.
- Superpowers completo sólo para cambios complejos, creativos, transversales o riesgosos; en cambios
  acotados, diseño breve + validación dirigida + revisión del diff.
- Preferir Codex, Superpowers, GitHub y browser/automatización existentes. **No sumar orquestador,
  memoria/context manager, navegador, MCP, plugin o dependencia** que duplique capacidad.
- Evitar investigación especulativa, documentación duplicada, ceremonia y optimización sin métrica.

### Definición de terminado

- **Python**: check dirigido + `py -3.12 -m ruff check .`; nunca `python`/`pip`/`pytest` pelados.
- **Arranque/rutas/templates**: smoke con `MONITOR_DISABLE_LOOPS=1` y `MONITOR_DB_DIR` temporal si
  puede tocar estado; probar import, rutas relevantes y templates.
- **UI**: servidor local + vista afectada; revisar consola, red, interacción, responsive y temas.
- **Sólo docs**: validar estructura, referencias, obsolescencia, whitespace y tamaño; sin servidor si
  no cambió vista/runtime.
- **Finanzas**: contrastar caso determinista con fuente/cálculo independiente; reportar inputs,
  valuación, settlement y tolerancia.
- **Fallas ajenas**: no corregirlas; separar checks aprobados, fallas preexistentes y no ejecutados.

### Protocolo obligatorio para cambios financieros

- Leer `docs/convenciones-financieras.md` y docstrings/estrategias involucrados.
- Confirmar valuación, settlement CI/24h/T+N, calendario, day-count, unidades/escala, moneda/sufijo,
  tasa nominal/efectiva, capitalización, flujos, lag índice/FX, redondeo y calidad/fuente activa+floor.
- Mantener dominio puro/determinista; cubrir nominal y bordes de fechas, flujos, tasas y faltantes.
  Nunca ajustar “hasta que dé” ni inventar velas, índices o cobros.
- Para `DUAL_CER_TAMAR`, preservar estrictamente: **settlement T+N → lag CER de 10 hábiles → spread
  → máximo de rieles**, en ese orden. Cotejar TTJ26 con IAMC (V.Téc 146.39) si se toca ese camino.
- Preservar las firmas de `FinancialEngine` y sus consumidores. Un cambio de contrato requiere mapa
  completo de callers y migración explícita, no compatibilidad accidental.

### Seguridad, datos y permisos

- Mínimo privilegio. Sin autorización explícita: no instalar dependencias/skills/plugins/MCP; tocar
  secretos, `.env`, DB persistente, servicios/host; crear branch/worktree; ni commit/push/pull/merge/deploy.
- Nunca push a `monitor-upstream`; sólo `origin`. No destruir/descartar cambios ni exponer secretos,
  payloads sensibles o excepciones internas en endpoints públicos, logs o respuestas.
- No debilitar TLS, timeouts, autenticación, rate-limit, validaciones, checks o supervisión para
  “hacer pasar” una tarea. En httpx, `None` significa sin timeout y está prohibido como sustituto de
  `httpx.USE_CLIENT_DEFAULT`; las excepciones TLS sólo pasan por la allowlist configurada.
- SQLite es verdad; Excel/CSV, semillas. Sin reseed destructivo: esquema forward-only, stores fuera
  del árbol, smoke aislado y migración explícita, compatible e idempotente cuando aplique.

### Fuentes de verdad y disciplina documental

- Fuentes: runtime verificado = comportamiento; `AGENTS.md` = operación;
  `docs/convenciones-financieras.md` = pricing; SQLite = catálogo. Ante divergencia, verificar intención
  y actualizar código+docs en el mismo cambio autorizado.
- `CLAUDE.md` duplicaba 187/219 líneas no vacías de esta guía: consolidar en tarea separada; mientras,
  no editar ambas copias por reflejo ni dejar que diverjan silenciosamente.
- Decisiones duraderas junto a su fuente; eliminar obsolescencia y fechar/evidenciar hallazgos temporales.

### Alertas verificadas del estado actual (auditoría 2026-09-06)

- **Sin red crítica**: no hay `tests/` ni `.github/workflows`; Ruff solo no prueba finanzas, auth,
  rutas, persistencia ni loops.
- **Divergencia de montaje**: el worktree actual de `apps/web/app.py` importa/monta sólo `personal`,
  `panels`, `bonds`, `header` y `stream`; los módulos `auth`, `users_abm` y `abm` siguen presentes
  pero no están montados. `HEAD` sí los montaba y definía `html_deps`/`api_deps`. A la vez,
  `/api/metrics` y `/api/riesgo-pais` aún dependen de `get_current_user` y el handler HTML fue
  reemplazado por un 401 JSON. **Antes de tocar rutas o auth, confirmar si esta divergencia es una
  decisión activa del usuario; nunca restaurarla ni eliminarla automáticamente.**
- El árbol puede estar sucio y este archivo sin trackear: `git status` es obligatorio; ninguna
  diferencia preexistente autoriza a tocarla.

### Mejoras priorizadas pendientes — no implementarlas incidentalmente

- **P0 — red mínima de regresión**: restaurar selectivamente desde la historia común `95380b` y
  adaptar al diseño actual `test_json_script.py`, `test_loop_supervisor.py`,
  `test_settlement_consonance.py`, `test_fin_Z1_financiero_vtec_settlement.py` y
  `test_rem_R1_financiero_cer_lag.py`. No revivir toda la suite legacy ni su arquitectura obsoleta.
- **P1 — invariantes**: tras la red determinista, Hypothesis para settlement/calendario, day-count,
  paridad/V.Téc y orden de rieles, con oráculos claros y ejemplos independientes.
- **P1 — CI**: GitHub Actions con Python 3.12, instalación de `requirements.lock` más
  `requirements-dev.txt`, Ruff y pytest; DB temporal, loops off y sin secretos/prod/proveedores externos.
- **Automatización futura útil**: considerar dos skills locales pequeñas, sólo en tarea explícita:
  `verify-financial-change` (convenciones → tests dirigidos → benchmark → Ruff) y
  `verify-web-change` (smoke aislado → servidor → browser → consola/red → Ruff). No crear un sistema
  de agentes adicional ni duplicar lo que ya cubren Codex/Superpowers.

**Web personal de David Berisso** (`/` dashboard-resume con radar/grafo de skills en ECharts,
`/projects`) **+ terminal de renta fija argentina** en `/bonos` (10 paneles SSR: bonares, cer,
tasa_fija, tamar, dolar_linked, bopreales, panel_lider, futuros, bei_tenor, bei_sendero; modal
por bono con tabs Trading / Grafico / Quant / WM / Docencia). El código también contiene ABM de
instrumentos en `/abm` y manager de usuarios en `/users`; su montaje actual está bajo la alerta de
auditoría anterior y no debe asumirse sólo por la presencia de los módulos.

**Origen**: FORK RECORTADO de `MonitorMercadoArgy` (base común `95380b2`; `497feb7` sacó
ON/provinciales/valor relativo/bei_pares, `730861b` borró tests y legacy). El remote
`monitor-upstream` es SOLO referencia: **nunca pushear ahí**. El de trabajo es `origin` =
`git@github.com-personal:d4v1dBrs/projects-hub.git`.

**Precios: BYMA open** (`settings.market_source`; alternativas `byma_realtime` —`BYMADATA_USER/
PASS` en `.env`— y `data912`, por `MONITOR_MARKET_SOURCE` + restart: el selector de la UI y
`/source/*` se quitaron acá) **con floor Data912 mergeado DEBAJO** (`provider_hub._apply_floor`:
rellena lo que la activa no lista y pisa un 0 con un cierre real). La quote de una fila puede
venir de `byma/field_map` **o** del floor, por símbolo y por ciclo: si un precio sale raro, mirar
las dos. Índices **BCRA**, futuros **Matba/Rofex WS**, FX **dolarapi**, riesgo país
**BondTerminal**, REM de la API comunitaria (ArgentinaDatos como fallback de los dos últimos).

> **Convenciones financieras** (CER NT8/2024, TAMAR, BEI, day-counts, MD BYMA, ONs, LECAP):
> `docs/convenciones-financieras.md` — extraídas del `agents.md` del monitor original (que ya no
> está en este repo). El código de pricing las cita por sección; leerlas ANTES de tocar
> `core/domain/pricing/`.

## Cómo correr

```powershell
py -3.12 -m pip install -r requirements.lock -r requirements-dev.txt   # runtime + ruff
$env:MONITOR_ADMIN_PASSWORD='...'; py -3.12 scripts/init_admin.py     # SOLO la 1ª vez
py -3.12 run.py                     # uvicorn → http://localhost:8000
py -3.12 -m ruff check .            # ÚNICO gate: acá NO hay tests/ ni check.ps1
$env:MONITOR_DISABLE_LOOPS='1'; py -3.12 run.py   # smoke sin loops (import + rutas)
```

`run.py` exige **3.12.x** y no reinicia nada (eso es systemd). Nunca `python`/`pytest` pelados.
`settings._load_dotenv` carga un `.env` en la raíz (gitignored). Bases y log viven en
`settings.db_dir` (`%LOCALAPPDATA%\monitor` en Windows, `$XDG_DATA_HOME/monitor` o
`~/.local/share/monitor` en Linux; `MONITOR_DB_DIR` reubica TODO): `catalog.db`, `backups/`,
`history/`, `jwt_secret`, `monitores_global.log` (WARNING+, 5 MB × 5).
**Nadie crea el admin** (ni el lifespan ni `deploy.sh`): con `db_dir` virgen `/login` responde
"Usuario o contraseña incorrectos" para siempre — `scripts/init_admin.py` (idempotente) ANTES.

## Arquitectura

```text
apps/web/
  app.py               FastAPI + lifespan: loops supervisados (`refresh` 5s, `bei` 300s; `history` 300s solo si hay columnas historicas) + `_startup_reconcile` (1×). `_ALL_TYPES` = qué precia el motor. OpenAPI apagada (MONITOR_ENABLE_DOCS=1 sólo dev).
  state.py             AppState: snapshot vivo + revision/wait_for_change (SSE) + errores/loop_crashes/degraded_loops + salud del catálogo + tablas BEI.
  supervisor.py        `supervise()`: reinicia con backoff 1s→60s el loop que termine por lo que sea (ver Robustez).
  deps.py deps_auth.py get_repo (singleton CatalogRepository) + get_state/hub/provider/indices/fx/rofex/bondterminal · get_current_user (401) / _html (302) / admin / RequireTabPermission (403).
  templates.py json_script.py   AuthJinja2Templates inyecta `current_user` + `has_tab()` · json_for_script (JSON seguro en <script>).
  routers/  auth (login/logout + rate-limit) · users_abm (admin) · personal (`/`, `/projects`) · panels (`/bonos`, /panels/{id}/rows|chart|share) · panels_schema (PANELS/PANEL_ORDER/filtros: registro declarativo) · bonds (modal: detail/horizon-matrix/price-history + metrics/cer sin UI) · abm · header (/header/cards, /health/badge) · stream (/stream SSE)
  bond_detail.py panels_rows.py instruments_abm.py   backend del modal (get_bond_detail/calculate/cer_projection/get_horizon_matrix) · builders de filas/chart/share · CRUD SQLite del ABM + backfills + register_stocks.
  templates/ base.html (nav + header strip + badge) · pages/{index=dashboard Gridstack, abm, login, users} · fragments/* · personal/{index,projects}.html (HTML standalone, no heredan base)
  static/   css/app.css (terminal, light/dark) · css/style.css (personal) · js/main.js (ECharts del resume) · js/uni_filters.js (ABM) · js/quant_engine.js (SIN consumidor) · vendor/ (htmx, htmx-sse, gridstack, chart.umd, html2canvas — locales)
core/domain/
  models.py services.py   Pydantic v2 (Cashflow/Instrument frozen, MarketSnapshot) · FinancialEngine = FACHADA delgada sobre pricing/.
  pricing/  base.py (VanillaStrategy) · strategies.py (Cer/DolarLinked/Tamar/DualCerTamar/HardDollar) · registry.py (predicado→strategy) · tamar.py (payoff BONTE TAMAR + V.Téc dual: CONTRATO en el docstring) · metrics.py · stubs.py · context.py protocols.py
  conventions.py daycount.py xirr.py clock.py currency.py   puras: settlement/tasas/CER ref · day-count declarado · XIRR Brent · `today()` (MONITOR_AS_OF sólo tests) · moneda por sufijo D/C.
  instrument_groups.py   universo de `instrument_type` VÁLIDOS por grupo + is_known_type() + PANEL_LIDER (ver invariante "tipos").
  cashflow_synth.py yield_curve.py inflation_path.py on_classification.py interfaces.py   síntesis de cashflows · NS/NSS + Fisher (BEI) · sendero mensual · sector de ON por emisor · ABCs de repo/provider.
core/holiday_engine.py   calendario BYMA + feriados AR (5 fuentes + data/feriados_ar.xlsx). TODO el settlement cuelga de acá.
core/infrastructure/
  provider_hub.py async_http.py circuit_breaker.py _tls.py   ProviderHub (fuente activa + floor, `HubMarketDataProvider`) · ResilientClient (httpx + breaker + semáforo por host) · verificación TLS siempre.
  byma/  sources.py (MarketSource byma_open|byma_realtime|data912 + make_source) · field_map.py (fila BYMA → Data912Row) · credentials.py (BYMADATA_USER/PASS ↔ .env) · universe.py (titulos_final.csv → tabla byma_catalog, buscador del ABM) · catalog_enrich.py (ISIN/emisor/ficha) · chart_history.py (cierres diarios BYMA `chart`)
  data912_provider.py indices_provider.py fx_provider.py futures_provider.py rem_provider.py bondterminal_provider.py argentinadatos_provider.py schemas.py repositories.py history_paths.py
  db/  engine.py (SQLite+WAL) · models.py (UserORM, InstrumentORM, CashflowORM, BymaCatalogORM) · catalog_repository.py (CatalogRepository, auto-seed, type_health, init_db forward-only) · backup.py
apps/cli/bei.py          compute_bei_tables (bootstrap + NSS + Fisher + sendero); lo llama `_bei_loop`. `_common.py` = fallback CLI sobre el Excel (la app le inyecta el use_case).
config/settings.py       pydantic-settings (`MONITOR_*`), db_dir y derivados en model_post_init, JWT secret, TZ del proceso, logging.
scripts/init_admin.py    el único script. deploy.sh + deploy/{monitores.service,nginx-projects-hub.conf,setup-https.sh}.
data/  instruments_master.xlsx (SEMILLA del catálogo) · byma/titulos_final.csv (universo BYMA, se reingesta en cada arranque) · feriados_ar.xlsx · history/{cer,tamar,a3500,reservas,bei}_diario.csv (semillas read-only; el estado va a db_dir/history) · history/precio_historico.csv (piso offline del histórico) · obligaciones_negociables.csv (semilla SIN ingesta, ver Pendientes)
```

## Flujo web (HTMX SSR + SSE)

El **lifespan**: `ResilientClient` → `ProviderHub(make_source(market_source))` (fallback
`byma_open` → `Data912Source`) → `AppState` → `warn_if_frozen()` → `backup_db` (1×/día) →
`get_repo()` (auto-siembra del Excel si la DB está vacía; una siembra fallida NO tumba el
arranque: se publica en `/api/health` y el badge) → providers del modal → tasks:

- `_startup_reconcile` (1×, NO supervisado): patas MEP/CABLE de soberanos + alta de acciones
  (`PANEL_LIDER`) → ISIN desde `titulos_final.csv` y ficha BYMA → `ingest_byma_catalog`
  (delete+insert de `byma_catalog`, cada arranque) → patas por ISIN → `reload()` → salud.
- `refresh` (5s, **crítico**): `hub.refresh_all()` + `prefetch` BCRA/dolarapi →
  `GenerateMonitorReport.execute(_ALL_TYPES)` en `to_thread` (pricing SERIAL a propósito, GIL)
  → `AppState.update` → push SSE. Ciclo > `refresh_sec` se grita a WARNING.
- `bei` (1× al arranque + 300s): `compute_bei_tables` → `AppState.set_bei`.
- `history` (tras el primer snapshot + 300s): precarga bases Sem/1M/3M/YTD/1A
  solo para `HISTORY_TYPES`, derivado de las columnas de paneles activos. Si el set
  esta vacio, no se inicia esta tarea ni se descargan historicos automaticamente.
  El refresh arranca sin espera inicial, y tanto refresh como CI leen estas bases
  solo de cache: nunca descargan historicos. BEI no calcula variaciones historicas.
  Solo `refresh` ingiere precios/indices/FX: BEI y reconcile esperan el primer
  snapshot y reutilizan los proveedores. Una base historica vacia se reintenta.

`_ALL_TYPES` = SOBERANOS + BOPREALES + TASA_FIJA + CER + DOLAR_LINKED + TAMAR + DUAL_TAMAR +
PROVINCIALES — **sin `OBLIGACIONES_NEGOCIABLES`** (ver Pendientes).

Cada panel es `<tbody hx-get="/panels/{id}/rows">` disparado por `sse:refresh` (`/stream`:
`refresh` por ciclo, `ping` cada 15s, `send_timeout=10`); `every 60s` es sólo fallback y todos
los triggers van gateados por `[mrRefreshOK(this)]` (pestaña oculta / panel cerrado) más
`tabvisible from:body`. Los 15s de `base.html` son el badge; `/header/cards` va cada 60s.
Bonares y CER tienen selector CI/24hs → `_ci_metrics` (motor sobre el snapshot CI, memoizado
por `(revision, panel)`). Los swaps HTMX reemplazan sólo filas y nunca cambian la geometría.
El layout de GridStack parte del default versionado de `apps/web/dashboard_layout.py`; una
preferencia personal se guarda en `localStorage` (`bonos-dashboard-state-v1`) únicamente al
pulsar Aplicar. Cancelar no escribe y Default + Aplicar elimina la preferencia local. Modal:
`GET /bond/{t}/detail` usa `bond_workbench.py` y un snapshot del Hub en el mismo plazo
CI/24hs. `POST /bond/{t}/workbench` recalcula escenarios, posiciones y comisiones;
`bond-workbench.js/css` reemplazan Tailwind/Alpine y liberan charts/requests al cerrar.
`/history-analysis` y `/api-fields` son lazy, con cache acotado y limite de cuatro
consultas externas simultaneas por proceso. `bond_history.py` combina cierres CSV,
Data912 y OHLCV BYMA sin inventar velas; solicita tres anos e informa cobertura real.
Lightweight Charts 5.2.1 local se carga al abrir Grafico. Quant usa retornos de precio
entre ruedas BYMA consecutivas, no retorno total. WM separa cupon/amortizacion/venta
y comisiones; Docencia muestra corte teorico a TIR constante, glosario y ejercicios.
Los flujos indexados/FX son escenarios explicitos, no cobros garantizados. Se conservan
las rutas legacy `/horizon-matrix` y `/price-history`.
**Capa personal**: `routers/personal.py` sirve `personal/*.html` standalone (Inter + Font
Awesome + ECharts 6.1.0 por CDN, `style.css`, `main.js`); no pasan por `base.html` ni por auth.

## Autenticación y permisos

JWT HS256 en cookie httponly `access_token` (SameSite=Lax, 24h; también `Authorization: Bearer`).
Secreto: env `MONITOR_JWT_SECRET_KEY` > `db_dir/jwt_secret` (0600) > generado y persistido.
`UserORM.allowed_tabs` (`"*"` = todas, `is_admin` bypasea) + `RequireTabPermission("abm")` como
`dependencies=` del router `abm`; `users_abm` exige admin. `_TAB_LANDING` = `bonos→/bonos`,
`abm→/abm`; admin aterriza en `/bonos`; sin pestañas → 403 en el login. Falta de **permiso** ≠
falta de **login**: `TabForbiddenException` → **403** con links a lo que sí puede ver; sólo
`RequiresLoginException` → 302 `/login` (`HX-Redirect` si es HTMX).

> **Alerta de montaje actual**: las reglas siguientes describen el contrato de acceso diseñado,
> pero `auth`, `users_abm` y `abm` no están incluidos hoy en `app.py`; por eso `/login`, `/abm/*`
> y `/users/*` no están disponibles en el worktree auditado. Verificar intención antes de cambiarlo.

**Exige sesión según el contrato diseñado**: `/abm/*` (tab), `/users/*` (admin), `/api/metrics`,
`/api/riesgo-pais` (401). **Permanece público en el montaje actual**: `/`, `/projects`, `/bonos`,
`/panels/*`, `/bond/*`, `/header/cards`, `/stream`, `/api/health` (recortado, sin `last_error`)
y `/health/badge` — `app.py` asume que el badge está detrás de login y **no lo está**; su tooltip
lleva `last_error` crudo. Gatear el terminal es decisión pendiente: `html_deps`/`api_deps` estaban
en `HEAD`, pero ya no existen en el worktree auditado; no confundir intención con montaje actual.

**Rate-limit del login**: 5 intentos / 5 min por (IP, usuario), bcrypt dummy contra timing. La IP
es el peer TCP; `X-Forwarded-For` sólo se cree si el peer está en `settings.trusted_proxy_ips`
(default `127.0.0.1,::1`), ÚLTIMA entrada (nginx). Un CDN delante rompe el supuesto.

## Despliegue

**Oracle Cloud** (host `paginapersonal`, ssh `web-personal`), clon en `/home/ubuntu/projects-hub`
con `origin` = projects-hub. systemd `monitores.service` (`User=ubuntu`, `venv/bin/python
run.py`, `Restart=always` 5s); nginx `:80 → :8000` (`deploy/nginx-projects-hub.conf`:
`proxy_buffering off` + `proxy_read_timeout 24h` para el SSE).

```bash
git push origin main                                  # local
ssh web-personal 'cd projects-hub && bash deploy.sh'  # git pull --ff-only + venv 3.12 (validado, se crea si falta) + pip install -r requirements.txt + restart + healthcheck /api/health (6×5s)
```

`deploy.sh` es `set -euo pipefail` (si algo falla antes del restart, el servicio viejo sigue
arriba) e instala `requirements.txt`, NO el `.lock`. El unit **no tiene `EnvironmentFile`** (sólo
`Environment=PATH`): las `MONITOR_*` salen del `.env` en la raíz del clon (gitignored) o de
`Environment=` en el unit; el `/etc/monitores/env` de `setup-https.sh` no existe todavía. Variables:

- `MONITOR_DB_DIR` fuera del árbol (p. ej. `/var/lib/monitor`): reubica catalog.db, backups/,
  history/, jwt_secret y log. Una base adentro del working tree la denuncia
  `Settings._check_db_paths` por ERROR (`MONITOR_DB_IN_TREE_FATAL=1` = aborta).
- `MONITOR_JWT_SECRET_KEY` (si no, se persiste en `db_dir/jwt_secret`).
- `MONITOR_COOKIE_SECURE`: `false` **a propósito** mientras se sirva por HTTP (con `true` el
  browser descarta la cookie → login en loop). Con dominio: `bash deploy/setup-https.sh
  <dominio> <email>` (root, en el server) y recién ahí `true` + uvicorn `--proxy-headers
  --forwarded-allow-ips=127.0.0.1`.
- `MONITOR_MARKET_SOURCE` (+ `BYMADATA_USER/PASS`), `MONITOR_TRUSTED_PROXY_IPS`,
  `MONITOR_TLS_NO_VERIFY_HOSTS` (CSV; default vacío = se verifica todo), `MONITOR_ADMIN_PASSWORD`
  /`MONITOR_ADMIN_USER` (sólo `init_admin.py`), `MONITOR_DISABLE_LOOPS` (smoke), `MONITOR_AS_OF`
  (congela el "hoy" del dominio: **jamás en prod**; `warn_if_frozen` lo grita al boot).

## Invariantes (no romper)

- **SQLite (`catalog.db`) = fuente de verdad; Excel/CSV = semillas**. `CatalogRepository`
  auto-siembra desde `instruments_master.xlsx` SOLO con la DB vacía; `reload()` refresca el cache
  y NUNCA re-siembra. Las altas de la ABM viven SOLO en SQLite y se ven en caliente (save →
  `reload()` → el ciclo siguiente las precia). Acá **no existe `ingest_master.py`**:
  `ingest_from_excel` es destructivo y sin guards: para cambiar datos, ABM o migración, no re-seed.
- **Schema forward-only**: `init_db` agrega columnas (`ALTER ADD COLUMN`), nunca dropea
  (`CURRENT_SCHEMA_VERSION` + `schema_meta` para transformar datos).
- **Un `instrument_type` fuera de `instrument_groups.py` deja el bono INVISIBLE** (el read-path
  filtra por igualdad exacta). Agregar un tipo = editarlo ahí PRIMERO; el borde de escritura
  valida (`repositories._resolve_instrument_type` avisa por WARNING, `save_instrument` rechaza con
  `is_known_type()`) y `/api/health` publica `catalog.orphans/defaulted`. Nunca inventar el tipo
  del nombre de la hoja. Corolario acá: además tiene que estar en `app._ALL_TYPES` y `PANEL_ORDER`.
- **V.Téc / payoff de los DUAL_CER_TAMAR**: settlement T+N → lag CER de 10 hábiles → spread →
  max de rieles, EN ESE ORDEN (ya se rompió dos veces). Leer el docstring de
  `core/domain/pricing/tamar.py` y `docs/convenciones-financieras.md` ANTES de tocar `tamar_dual_payoff_at` /
  `calculate_technical_value`. Sin suite no hay red: cotejar a mano con IAMC (TTJ26 → V.Téc 146.39).
- **`FinancialEngine` preserva firmas** (consumidores: `bond_detail`, `generate_report`, `bei`).
- **Nada de `.db` ni logs dentro del árbol**: todo cuelga de `db_dir` (`_DB_DERIVED`; un store
  nuevo se agrega ahí). `data/history/` es semilla read-only: escribir vía
  `history_paths.state_path`, leer vía `resolve_read`. Única escritura tolerada en el árbol:
  `data/feriados_ar_cache.json` del holiday_engine (gitignored).
- **Timeouts de httpx**: el centinela es `httpx.USE_CLIENT_DEFAULT`, **NO `None`** (= sin
  timeout: un request colgado no vuelve nunca). Cualquier wrapper nuevo copia `ResilientClient`.
- **TLS se verifica siempre** (`_tls.py`, allowlist vacía); excepción sólo por
  `MONITOR_TLS_NO_VERIFY_HOSTS`, nunca `verify=False` en un cliente.
- **Zona horaria**: `apply_timezone()` fija la TZ del proceso al importar `settings` (el server
  corre en UTC y el dominio usa `date.today()` naive). No-op en Windows a propósito.
- **JSON embebido en `<script>`** va por `json_for_script`, nunca `json.dumps` pelado.

## Robustez / Operaciones

- **Supervisión**: todos los loops activos van en `supervise()` (backoff 1s→60s, reset tras 60s sanos, tope
  de 5 cancelaciones espurias); `stopping` se setea ANTES de cancelar (shutdown ≠ caída).
  `refresh` caído = crítico (badge rojo "sin datos", `status: degraded`, retención 300s); `bei`
  caído = parcial (ámbar "loop caído", `degraded_loops`). El 2026-09-01 el refresh murió mudo 22hs.
- **Backup**: snapshot online de `catalog.db` al arrancar (1×/día, rota a `backup_keep=7`) en
  `db_dir/backups`. Sin script de restore acá: parar el servicio y copiar el archivo a mano.
- **Salud**: `/api/health` (`status`, `is_stale`, `age_seconds`, `degraded_loops`, `catalog`) +
  badge + `journalctl -u monitores.service -f` + `db_dir/monitores_global.log`.
- **Árbol sucio en el server**: `deploy.sh` es `--ff-only`; si aborta, alguien editó allá:
  `ssh web-personal 'cd projects-hub && git status'`, `git stash`/`git checkout -- .`, nunca
  commitear ahí. El runtime ya no escribe en `data/` (salvo el cache de feriados).

## Pendientes / decisiones abiertas

- **Gatear `/bonos` y sus fragmentos detrás de login**: `html_deps`/`api_deps` estaban listos en
  `HEAD`, pero faltan en el worktree auditado; mientras tanto badge y `/stream` son públicos.
- **CDNs pendientes en la web personal**: ECharts 6.1.0 + Font Awesome + Google Fonts
  (`personal/*`). El modal ya usa Lightweight Charts y Lucide locales con version fija;
  no carga Tailwind ni Alpine.
- **ONs**: `data/obligaciones_negociables.csv` es semilla sin ingesta (se conserva a propósito);
  `_ALL_TYPES` no las precia. Los paneles `obligaciones_negociables`, `provinciales`,
  `valor_relativo` y `bei_pares` fueron retirados de `PANELS` y `PANEL_ORDER`; quedan semillas y
  plomería parcial. Su restauración o limpieza sigue siendo una decisión explícita pendiente.
- **Sin UI**: `fragments/cer_drawer_body.html` + `GET/POST /bond/{t}/cer`, `POST
  /bond/{t}/metrics` (`calc_result.html` sí lo usa `/abm/calc`) y `static/js/quant_engine.js`.

## Flujo Superpowers (método de trabajo)

### Revision local solicitada por el usuario

- Despues de cada cambio, iniciar o actualizar el servidor local y abrir el navegador
  en la vista modificada para que el usuario pueda revisarla. Dejar el servidor activo
  y compartir la URL local. Reutilizar la pestana de revision cuando ya este abierta.
- Acumular cambios en local. No hacer commit, push, pull ni despliegue hasta que el
  usuario lo pida explicitamente.

Plugin **Superpowers**: para trabajo complejo, `brainstorming → spec → writing-plans → plan →
subagent-driven → code-review → finishing-branch`; artefactos en `docs/superpowers/` (on-demand).
Para cambios acotados aplicar el flujo liviano definido al inicio. Las skills se auto-disparan al
arrancar Codex. **Este AGENTS.md gana sobre cualquier skill dentro de las instrucciones del repo,
siempre debajo de sistema/desarrollador/usuario** (financieras de
`docs/convenciones-financieras.md`, SQLite = verdad, Excel = semilla). Mientras no haya suite, TDD
integral no aplica y debe declararse esa limitación: el gate actual es `py -3.12 -m ruff check .` +
smoke aislado con `MONITOR_DISABLE_LOOPS=1` (import limpio, rutas relevantes, templates) + contraste
manual financiero cuando corresponda. La restauración de tests se rige por la prioridad P0 anterior.
Worktrees **nunca** dentro del proyecto (OneDrive; `.worktrees/` gitignored): `EnterWorktree` del
harness o `~/.config/superpowers/worktrees/`, sólo con autorización. Comandos en planes:
`py -3.12`, no `python`/`pytest` pelados.
