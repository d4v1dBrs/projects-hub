# projects-hub — web personal + terminal de renta fija

Web personal de David Berisso y, colgando de la misma app, un terminal de renta fija
argentina. Es un fork recortado del monitor "MonitorMercadoArgy": quedó el motor de
pricing y el dashboard de bonos, nada más.

- **`/` y `/projects`** — home (dashboard-resume con grafo de skills en ECharts) y
  proyectos. Públicas, sin login.
- **`/bonos`** — terminal de bonos: dashboard Gridstack SSR (HTMX + SSE) con paneles
  Bonares/Globales, CER, Tasa fija, TAMAR/Dual, Dólar linked, Bopreales, Panel líder,
  Futuros DLR, BEI por tenor y sendero BEI vs REM; modal por bono con tabs Trading /
  Gráfico (Lightweight Charts) / Quant (matriz de horizonte). Precios de
  **BYMA open** (~20 min de demora) con **piso Data912** mergeado debajo por símbolo;
  índices CER/TAMAR/A3500/reservas de la **API del BCRA**; FX de **dolarapi**; futuros
  DLR por el **WebSocket público de Matba/Rofex**; riesgo país de **bondterminal**;
  REM del BCRA con fallback **ArgentinaDatos**. Hoy se sirve sin login.
- **`/abm`** (permiso por pestaña) y **`/users`** (admin) — ABM de instrumentos y de
  usuarios. Sesión por JWT en cookie httponly. Escribir el layout de los paneles,
  `/api/metrics` y `/api/riesgo-pais` también exigen sesión.

## Stack

FastAPI + Jinja2 SSR + HTMX (fragmentos) + SSE (`/stream` pushea `refresh` por ciclo).
SQLite (SQLAlchemy 2) como fuente de verdad del catálogo y los usuarios;
`data/instruments_master.xlsx` es sólo la semilla si la base está vacía. Pricing puro y
testeable en `core/domain` (XIRR, day-counts, CER/TAMAR/dual por Strategy + registry).
Ingesta async con httpx + circuit breaker en `core/infrastructure`. Python **3.12**
pineado (`run.py` aborta con otra minor). Este repo no tiene suite de tests: el único
gate es `ruff`.

## Quick start (local, Windows)

```powershell
py -3.12 -m pip install -r requirements.lock -r requirements-dev.txt
$env:MONITOR_ADMIN_PASSWORD='...'; py -3.12 scripts/init_admin.py   # SOLO la 1ª vez
py -3.12 run.py                     # uvicorn → http://localhost:8000
py -3.12 -m ruff check .            # lint (config en ruff.toml)
```

`init_admin.py` crea el primer admin (`admin`, o `MONITOR_ADMIN_USER`) en una
`catalog.db` virgen y es idempotente. Sin ese paso `/login` responde "Usuario o
contraseña incorrectos" para siempre: nadie crea usuarios por vos. En el primer arranque
la app siembra el catálogo desde el Excel, ingesta `data/byma/titulos_final.csv` y
empieza a acumular el estado de los índices en `db_dir/history`.

## Deploy (Oracle Cloud)

```bash
git push origin main                                   # origin = d4v1dBrs/projects-hub
ssh web-personal 'cd projects-hub && bash deploy.sh'   # pull --ff-only + venv 3.12 + pip + restart + healthcheck
```

En el servidor, systemd `monitores.service` corre `venv/bin/python run.py`
(`deploy/monitores.service`, `Restart=always`) y nginx proxya `:80 → :8000`
(`deploy/nginx-projects-hub.conf`, con buffering off y read-timeout largo para el SSE).
`deploy.sh` instala `requirements.txt` (no el lock) y aborta antes del restart si algo
falla, así el servicio viejo sigue arriba. Logs: `journalctl -u monitores.service -f`.

HTTPS: hoy se sirve por HTTP (IP pelada; Let's Encrypt no emite para IPs). Cuando haya
dominio con A a la IP: `bash deploy/setup-https.sh <dominio> <email>` como root, y
recién entonces `MONITOR_COOKIE_SECURE=true` + uvicorn con `--proxy-headers
--forwarded-allow-ips=127.0.0.1`.

## Configuración

`config/settings.py` (pydantic-settings). Override por env `MONITOR_*` o `.env` en la
raíz (gitignored; en el servidor, el `.env` de la raíz del clon o `Environment=` en el
unit — `monitores.service` no tiene `EnvironmentFile`).

| Variable | Default | Qué hace |
| --- | --- | --- |
| `MONITOR_DB_DIR` | `%LOCALAPPDATA%\monitor` · `~/.local/share/monitor` | Directorio de TODO lo que no va al repo: `catalog.db`, `backups/`, `history/`, `jwt_secret`, log. Si resuelve adentro del árbol la app lo denuncia con ERROR (`MONITOR_DB_IN_TREE_FATAL=true` para abortar). |
| `MONITOR_JWT_SECRET_KEY` | — | Firma de la cookie de sesión. Sin ella se genera y persiste en `db_dir/jwt_secret` (0600). Setearla en prod. |
| `MONITOR_COOKIE_SECURE` | `false` | Flag `Secure` de la cookie. Sólo con HTTPS: sobre HTTP el browser la descarta y el login queda en loop. |
| `MONITOR_MARKET_SOURCE` | `byma_open` | Fuente live: `byma_open` · `byma_realtime` (pide `BYMADATA_USER`/`BYMADATA_PASS` en `.env`) · `data912`. Data912 es siempre el piso. Cambiarla exige reiniciar. |
| `MONITOR_TRUSTED_PROXY_IPS` | `127.0.0.1,::1` | Peers cuyo `X-Forwarded-For` se cree para el rate-limit del login. Vacío = ninguno. |
| `MONITOR_ADMIN_PASSWORD` / `MONITOR_ADMIN_USER` | — / `admin` | Sólo `scripts/init_admin.py`: primer admin en una base virgen. |
| `MONITOR_DISABLE_LOOPS` | — | Con cualquier valor no arrancan los loops de fondo (smoke tests, import limpio). |
| `MONITOR_ENABLE_DOCS` | — | Monta `/docs`, `/redoc`, `/openapi.json`. Quedan públicos: nunca en prod. |
| `MONITOR_REFRESH_SEC` / `MONITOR_BEI_REFRESH_SEC` | `5` / `300` | Período de los dos loops supervisados. |

`MONITOR_AS_OF=YYYY-MM-DD` congela el "hoy" del dominio: es SÓLO para pruebas y el
server lo grita en WARNING si lo encuentra activo.

## Operación

- **Runtime**: el lifespan hace un backup de `catalog.db` (1×/día, rota a 7 en
  `db_dir/backups`), calienta el catálogo y lanza dos loops supervisados con backoff
  (`apps/web/supervisor.py`): `refresh` cada 5 s (fuente live + piso Data912, prefetch
  BCRA/dolarapi, pricing en `to_thread`, push SSE) y `bei` cada 300 s
  (`apps/cli/bei.py`). `_startup_reconcile` corre una vez: patas de moneda, ISIN BYMA,
  universo `byma_catalog`.
- **Salud**: `GET /api/health` (público, sin detalle de errores): `status` ok/degraded,
  `is_stale`, `age_seconds`, `degraded_loops` y salud del catálogo. El badge del header
  (`/health/badge`) muestra el motivo sólo con sesión (anónimo ve el estado, sin
  detalle). Si el refresh falla, la app sigue
  sirviendo el último snapshot bueno.
- **Dónde vive cada cosa**: `db_dir/catalog.db` (catálogo + usuarios: fuente de verdad,
  schema forward-only), `db_dir/backups/`, `db_dir/history/` (estado vivo de las series
  CER/TAMAR/A3500/reservas; `data/history/*.csv` es la semilla read-only),
  `db_dir/jwt_secret`, `db_dir/monitores_global.log` (WARNING+, rotativo 5 MB × 5).
  Nada de `.db` dentro del repo: es donde corre `git pull`.
- **Datos versionados**: `data/instruments_master.xlsx` (semilla del catálogo),
  `data/byma/titulos_final.csv` (universo BYMA, re-ingestado en cada arranque),
  `data/feriados_ar.xlsx` (todo el settlement cuelga de acá), `data/history/*.csv`
  (semillas de las series + piso offline del histórico de precios).

## Más documentación

- [CLAUDE.md](CLAUDE.md) — guía del codebase: arquitectura, invariantes, robustez.
- [docs/convenciones-financieras.md](docs/convenciones-financieras.md) — convenciones de
  pricing (CER NT8/2024, TAMAR, BEI, day-counts, MD BYMA).
