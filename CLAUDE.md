# CLAUDE.md — Guía del codebase (web personal + terminal de bonos)

**Web personal de David Berisso** (`/` dashboard-resume con radar/grafo de skills en ECharts,
`/projects`) **+ terminal de renta fija argentina** en `/bonos` (10 paneles SSR: bonares, cer,
tasa_fija, tamar, dolar_linked, bopreales, panel_lider, futuros, bei_tenor, bei_sendero; modal
por bono con tabs Trading / Gráfico (Lightweight Charts) / Quant (horizon matrix)) + ABM de
instrumentos en `/abm` + manager de usuarios en `/users`.

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
`history/`, `jwt_secret`, `dashboard_layout.json`, `monitores_global.log` (WARNING+, 5 MB × 5).
**Nadie crea el admin** (ni el lifespan ni `deploy.sh`): con `db_dir` virgen `/login` responde
"Usuario o contraseña incorrectos" para siempre — `scripts/init_admin.py` (idempotente) ANTES.

## Arquitectura

```text
apps/web/
  app.py               FastAPI + lifespan: 2 loops supervisados (`refresh` 5s, `bei` 300s) + `_startup_reconcile` (1×). `_ALL_TYPES` = qué precia el motor. OpenAPI apagada (MONITOR_ENABLE_DOCS=1 sólo dev).
  state.py             AppState: snapshot vivo + revision/wait_for_change (SSE) + errores/loop_crashes/degraded_loops + salud del catálogo + tablas BEI.
  supervisor.py        `supervise()`: reinicia con backoff 1s→60s el loop que termine por lo que sea (ver Robustez).
  deps.py deps_auth.py get_repo (singleton CatalogRepository) + get_state/hub/provider/indices/fx/rofex/bondterminal · get_current_user (401) / _html (302) / admin / RequireTabPermission (403).
  templates.py json_script.py   AuthJinja2Templates inyecta `current_user` + `has_tab()` · json_for_script (JSON seguro en <script>).
  routers/  auth (login/logout + rate-limit) · users_abm (admin) · personal (`/`, `/projects`) · panels (`/bonos`, /panels/{id}/rows|chart|share, layout) · panels_schema (PANELS/PANEL_ORDER/filtros: registro declarativo) · bonds (modal: detail/horizon-matrix/price-history + metrics/cer sin UI) · abm · header (/header/cards, /health/badge) · stream (/stream SSE)
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
scripts/init_admin.py    el único script. deploy.sh + deploy/{monitores.service,nginx-monitores.conf,setup-https.sh}.
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

`_ALL_TYPES` = SOBERANOS + BOPREALES + TASA_FIJA + CER + DOLAR_LINKED + TAMAR + DUAL_TAMAR +
PROVINCIALES — **sin `OBLIGACIONES_NEGOCIABLES`** (ver Pendientes).

Cada panel es `<tbody hx-get="/panels/{id}/rows">` disparado por `sse:refresh` (`/stream`:
`refresh` por ciclo, `ping` cada 15s, `send_timeout=10`); `every 60s` es sólo fallback y todos
los triggers van gateados por `[mrRefreshOK(this)]` (pestaña oculta / panel cerrado) más
`tabvisible from:body`. Los 15s de `base.html` son el badge; `/header/cards` va cada 60s.
Bonares y CER tienen selector CI/24hs → `_ci_metrics` (motor sobre el snapshot CI, memoizado
por `(revision, panel)`). El layout del Gridstack es UN archivo global
(`db_dir/dashboard_layout.json`; POST/DELETE `/panels/layout`, login + tope 64 KB). Modal:
`GET /bond/{t}/detail` (Tailwind play-CDN + Alpine) + `/horizon-matrix` + `/price-history`
(JSON para Lightweight Charts: Data912 → `chart_history` BYMA → CSV piso; red caída = 503 `[]`).
**Capa personal**: `routers/personal.py` sirve `personal/*.html` standalone (Inter + Font
Awesome + ECharts 5.5.0 por CDN, `style.css`, `main.js`); no pasan por `base.html` ni por auth.

## Autenticación y permisos

JWT HS256 en cookie httponly `access_token` (SameSite=Lax, 24h; también `Authorization: Bearer`).
Secreto: env `MONITOR_JWT_SECRET_KEY` > `db_dir/jwt_secret` (0600) > generado y persistido.
`UserORM.allowed_tabs` (`"*"` = todas, `is_admin` bypasea) + `RequireTabPermission("abm")` como
`dependencies=` del router `abm`; `users_abm` exige admin. `_TAB_LANDING` = `bonos→/bonos`,
`abm→/abm`; admin aterriza en `/bonos`; sin pestañas → 403 en el login. Falta de **permiso** ≠
falta de **login**: `TabForbiddenException` → **403** con links a lo que sí puede ver; sólo
`RequiresLoginException` → 302 `/login` (`HX-Redirect` si es HTMX).

**Exige sesión HOY**: `/abm/*` (tab), `/users/*` (admin), `POST/DELETE /panels/layout`,
`/api/metrics`, `/api/riesgo-pais` (401). **Público HOY**: `/`, `/projects`, `/bonos`,
`/panels/*`, `/bond/*`, `/header/cards`, `/stream`, `/api/health` (recortado, sin `last_error`)
y `/health/badge` — `app.py` asume que el badge está detrás de login y **no lo está**; su tooltip
lleva `last_error` crudo. `html_deps`/`api_deps` existen en `app.py` sin aplicar: gatear el
terminal es decisión pendiente del usuario.

**Rate-limit del login**: 5 intentos / 5 min por (IP, usuario), bcrypt dummy contra timing. La IP
es el peer TCP; `X-Forwarded-For` sólo se cree si el peer está en `settings.trusted_proxy_ips`
(default `127.0.0.1,::1`), ÚLTIMA entrada (nginx). Un CDN delante rompe el supuesto.

## Despliegue

**Oracle Cloud** (host `paginapersonal`, ssh `web-personal`), clon en `/home/ubuntu/projects-hub`
con `origin` = projects-hub. systemd `monitores.service` (`User=ubuntu`, `venv/bin/python
run.py`, `Restart=always` 5s); nginx `:80 → :8000` (`deploy/nginx-monitores.conf`:
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
  history/, jwt_secret, layout y log. Una base adentro del working tree la denuncia
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

- **Supervisión**: los 2 loops van en `supervise()` (backoff 1s→60s, reset tras 60s sanos, tope
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

- **Gatear `/bonos` y sus fragmentos detrás de login** (`html_deps`/`api_deps` listos, sin
  aplicar); mientras tanto el badge y `/stream` también son públicos.
- **Vendorear lo que sigue en CDN sin pin**: `lightweight-charts` (unpkg, en `base.html` → TODAS
  las páginas del terminal), Tailwind play-CDN + `alpinejs@3.x.x` (`fragments/bond_detail.html`),
  ECharts 5.5.0 + Font Awesome + Google Fonts (`personal/*`). El resto ya es `static/vendor/`.
- **ONs**: `data/obligaciones_negociables.csv` es semilla sin ingesta (se conserva a propósito);
  `_ALL_TYPES` no las precia; `PANELS` aún define `obligaciones_negociables`/`provinciales`/
  `valor_relativo`/`bei_pares` fuera de `PANEL_ORDER`; el ABM abre en esa hoja. ¿Vuelven o se limpian?
- **Sin UI**: `fragments/cer_drawer_body.html` + `GET/POST /bond/{t}/cer`, `POST
  /bond/{t}/metrics` (`calc_result.html` sí lo usa `/abm/calc`) y `static/js/quant_engine.js`.
- **`Profile.pdf`** en la raíz: trackeado, nadie lo sirve ni lo linkea (el mount estático es
  `apps/web/static`). O va a `static/` con un link "CV" en `personal/index.html`, o sale del repo.

## Flujo Superpowers (método de trabajo)

Plugin **Superpowers**: `brainstorming → spec → writing-plans → plan → subagent-driven →
code-review → finishing-branch`; artefactos en `docs/superpowers/` (on-demand). Las skills se
auto-disparan al arrancar Claude Code. **Este CLAUDE.md gana sobre cualquier skill** (financieras
de `docs/convenciones-financieras.md`, SQLite = verdad, Excel = semilla). **TDD no aplica mientras no haya suite**: la
verificación es `py -3.12 -m ruff check .` + smoke con `MONITOR_DISABLE_LOOPS=1` (import limpio,
rutas responden, templates compilan) + comparar números a mano en el modal. Worktrees **nunca**
dentro del proyecto (OneDrive; `.worktrees/` gitignored): `EnterWorktree` del harness o
`~/.config/superpowers/worktrees/`. Comandos en planes: `py -3.12`, no `python`/`pytest`.
