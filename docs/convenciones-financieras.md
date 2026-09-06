# Convenciones financieras — pricing core (`core/domain/**`)

Contrato financiero del motor de bonos: CER (NT N°8/2024), TAMAR/Dual, Dólar Linked,
ON hard-dollar, LECAP/BONCAP, day-counts, MD BYMA/IAMC, settlement T+0/T+1, curvas y BEI.
Sale del `agents.md` del monitor original (MonitorMercadoArgy), del que este repo es un
fork recortado: acá quedó **sólo** lo que sigue vigente para `core/domain/**`, con las
referencias a archivos ajustadas a este árbol. **CLAUDE.md manda leerlo antes de tocar
pricing**; el código lo cita por nombre de sección (`tamar.py`, `strategies.py`,
`indices_provider.py`), así que los headings de abajo no se renombran a la ligera.

---

## SCHEMA DE LAS HOJAS (Excel semilla = campos del ABM)

El catálogo **vivo** es SQLite (`catalog.db` en `settings.db_dir`); el Excel
`data/instruments_master.xlsx` es **semilla** (auto-siembra si la DB está vacía) y sus
hojas son las mismas que expone el ABM (`/abm`, `instruments_abm.SHEET_SCHEMAS`): cada fila
se guarda con su `sheet` + `raw_fields` y el parser de fila → `Instrument` es único
(`core/infrastructure/repositories.py::build_instrument`), lo lea de la semilla o del ABM.

| Hoja | Columnas | Notas |
|---|---|---|
| **Soberanos** | ticker, short_name, tipo, fecha_vencimiento, fecha_emision, cupon anual %, frecuencia pagos, base calculo, tipo amortizacion, amort inicio, amort cantidad | BONAR/GLOBAL/BOPREAL. Si no hay cashflows explícitos, `cashflow_synth.synth_cashflows()` los crea. El ABM consolida las 3 especies (ticker_ars / ticker_mep / ticker_ccl) en un solo form; en la DB siguen siendo filas por ticker. |
| **Tasa_Fija** | ticker, clase, fecha_emision, fecha_pago, tem_licit, precio_fallback | LECAP/BONCAP capitalizable: payoff = 100 × (1+tem_licit)^months (30/360). BONOFIJA usa Cashflows_Fija. |
| **CER** | ticker, tipo, fecha emision, fecha vencimiento, cupon anual %, frecuencia pagos, base calculo, tipo amortizacion, amort inicio, amort cantidad, capital factor, meses cupon, cer emision, categoria | `cer emision` es crítico (ver convenciones). `categoria` es la etiqueta de mercado (ej. "BONCERES CERO CUPON"). |
| **Dolar_Linked** | ticker, fecha_vencimiento, tc_inicial, fecha_emision, cupon anual %, frecuencia pagos, base calculo | Valor par 100 USD. V.Téc en pesos = 100 × mayorista venta. La hoja no lleva `tipo`: el default es `DOLAR_LINKED`. |
| **TAMAR** | ticker, tipo, fecha_emision, fecha_vencimiento, tasa_fija_mensual, spread, cer_base, cer_spread | tipo ∈ {PURO, DUAL, DUAL_CER_TAMAR}. `spread` aplica al rail TAMAR; `cer_spread` solo para DUAL_CER_TAMAR. |
| **Obligaciones_Negociables** | short_name (emisor), serie_clase, sector_override, ley_aplicable, tipo, fecha_emision, fecha_vencimiento, cupon anual %, frecuencia pagos, base calculo, tipo amortizacion, denom_base, denom_incremento, valor_nominal, + ticker_ars/ticker_mep/ticker_ccl, isin | **Hoja sólo-ABM** (no existe en el Excel semilla). tipo ∈ {HARD DOLLAR, DOLLAR LINKED}. Sin `tipo` el default es HARD DOLLAR y deja WARNING (ver `repositories.AMBIGUOUS_DEFAULT_SHEETS`). |
| **Cashflows** | ticker, fecha_pago, amortizacion, cupon_interes | Sobreescribe el generador sintético. Per-100-VN en términos base. |
| **Cashflows_Fija** | ticker, fecha_pago, monto | Para BONOFIJA / pagos únicos. |

(`Cotizaciones` también está en el Excel pero no es una hoja de instrumentos.)

---

## CÓMO AGREGAR UNA NUEVA CURVA

1. **Agregar el tipo PRIMERO** a la constante adecuada en
   [`core/domain/instrument_groups.py`](../core/domain/instrument_groups.py). Todo el
   read-path filtra por **igualdad exacta** de `instrument_type`: un tipo que no esté ahí
   deja el bono cargado pero **invisible** (no se precia, no se muestra). Recién después
   cargar las filas (ABM, o Excel semilla en una DB vacía).
2. **Web**: registrar el panel en `apps/web/routers/panels_schema.py` (`PANELS` +
   `PANEL_ORDER`: título, set de tipos, columnas); las filas se arman en
   `apps/web/panels_rows.py`; `templates/pages/index.html` itera `PANELS` y pone el
   `<tbody hx-get="/panels/{id}/rows">`.
3. **Si requiere matemática nueva**: una `PricingStrategy` nueva en
   `core/domain/pricing/strategies.py` (heredar de `VanillaStrategy` y sobreescribir sólo
   lo que cambia), su predicado en `core/domain/pricing/registry.py` (`_RULES`, "más
   específico primero") y, si hace falta, la property `is_*` en `core/domain/models.py`.
   `FinancialEngine` es una fachada que **preserva firmas**: no le agregues ramas por
   tipo. Para nuevo tipo de cashflow synth, agregar dispatch en
   `cashflow_synth.synth_cashflows`.
4. **Si querés el chart TIR vs MD**: lo sirve `routers/panels.py::panel_chart` +
   `fragments/panel_chart.html` para cualquier panel con MD/TIR — no hay nada que cablear.

**Nunca**:
- Hardcodear listas de tickers en un panel (usar `instrument_groups.py`).
- Crear un cliente HTTP nuevo para precios live (usar el `ProviderHub` / la `MarketSource` activa).
- Crear un cliente HTTP nuevo para otra fuente sin pasar por `core/infrastructure/async_http.py::ResilientClient` (perdés pool, breaker y el retry sobre transients). Si por algún motivo va sync, usar `httpx` con cache por TTL y correrlo en `to_thread` — y saber que ahí NO hay retry.
- Reimplementar TIR / duration / NPV (usar `FinancialEngine`).
- Reimplementar cashflow synthesis (usar `cashflow_synth.synth_cashflows`).
- Leer el catálogo fuera de `CatalogRepository` (SQLite). El Excel master sólo se lee para **sembrar** la DB (bootstrap); el editor de runtime es la ABM (`instruments_abm.py`, escribe SQLite transaccional).
- Tratar al Excel master como fuente de verdad viva: es semilla. Las altas/ediciones del runtime van por la ABM → SQLite.

---

## CÓMO AGREGAR UN NUEVO INSTRUMENTO (por la ABM, sin tocar el Excel)

Usar **`/abm`** (permiso por pestaña; `routers/abm.py` + `instruments_abm.py`, HTMX SSR):
- Buscador de ticker existente → carga la fila + cashflows (`/abm/form`).
- "Nueva especie" → elige hoja → completa form → preview de cashflows sintetizados en vivo
  (`POST /abm/cashflows`, `cashflow_synth.synth_cashflows` sobre los fields actuales) →
  `POST /abm/save`.
- `POST /abm/calc` recalcula métricas del form sin persistir.
- Eliminar por ticker (`DELETE /abm/instrument/{ticker}`, con confirmación): borra fila +
  cashflows huérfanos.

`save_instrument` escribe **SQLite directo, transaccional** (fila + cashflows en una sola
transacción), **rechaza el alta si el tipo no pasa `is_known_type()`** y después del save
hace `repo.reload()` (relee el cache desde SQLite, NUNCA re-siembra): el ciclo siguiente del
motor ya precia el alta, sin reiniciar. Para Soberanos basta llenar los 11 campos (emisión +
cupón + freq + amort + ...) y el cashflow se genera solo vía `cashflow_synth.synth_cashflows`.

---

## CONVENCIONES CRÍTICAS

### Bonos CER (NT N°8/2024)

#### `CER_BASE` en la hoja de instrumentos

La columna `cer emision` / `cer_emision` (en el ABM: "CER base (10h pre-emisión)") debe
contener el **CER 10 días hábiles antes de la fecha de emisión**, no el del día de emisión.

Ejemplo del paper (T2X5):
- Fecha de Emisión: 14/03/2023
- Valor a cargar: CER del **28/02/2023** (= emisión − 10 días hábiles BYMA) = **81.22**

#### Cashflows en términos "base"

La hoja `Cashflows` (o la tabla de flujos del ABM) debe almacenar montos per-100-nominal en
términos de "base", NO valores nominales-al-pago. El sistema multiplica internamente por
`CER_LIQ-10h / CER_BASE` al deflactar el precio (factor de indexación, NT N°8/2024 Eq. 13,
en `pricing/base.py::VanillaStrategy.technical_value`; TIR real en
`pricing/strategies.py::CerStrategy.tir`, que deflacta el precio por ese mismo factor y
resuelve el IRR contra los flujos nominales-base). Si los flujos vienen indexados, hay
**doble-conteo**. Bonos con `capital factor` > 1 (DICP/DIP0/CUAP) se normalizan a base-100
antes de indexar.

#### Lag de 10 días hábiles BYMA

`dias habiles previos` / `dias_lag` controla el lag. Default = 10 (`Instrument.cer_lag`).
El CER que indexa un pago de fecha D es el de `cer_lag` hábiles BYMA **antes** de D
(`conventions.cer_reference_date`), y D es la **liquidación** (T+N vía
`settlement_byma_date`), no la fecha de rueda. El índice sale de `BCRAIndicesProvider`
(BCRA Monetarias var 30); semilla read-only en `data/history/cer_diario.csv`, estado vivo en
`db_dir/history/` (`core/infrastructure/history_paths.py`).

### Bonos TAMAR (PURO, DUAL, DUAL_CER_TAMAR)

- **`spread`**: anual decimal sobre TAMAR (ej. 0.05 = TAMAR + 5%). El rail **NO** es diario
  `(1+(TAMAR_d+spread)/365)` (descripción vieja, errónea). El BONTE TAMAR capitaliza
  **mensualmente** con day-count 30/360 — fórmula oficial, en `conventions.py`
  (`_TAMAR_K = 365/32`, `tamar_tem`) y `pricing/tamar.py::tamar_dual_payoff_at`:
  - `TAMAR_TEM = ((1 + TNA/k)^k)^(1/12) − 1` con `k = 365/32`, sobre la TAMAR **promedio**
    del período emisión→vto (`avg_tamar_tna`, pasado real + forecast para el tramo futuro)
    más el `spread`.
  - `payoff = 100·(1+tem_max)^n_months`, con `n_months = days_30_360(emisión, vto)/30`.
  - Validado contra la referencia IAMC para TTJ26: precio 158.20 → V.Téc 146.39, payback
    164.32, TIR_EA 39.06%. Ver el docstring de `tamar.py`.
- **`tasa_fija_mensual`** (solo DUAL): floor **mensual** decimal. Bond paga `max(tem_tamar, floor_mensual)` por mes (no diario).
- **`cer_base` + `cer_spread`** (solo DUAL_CER_TAMAR, serie TXMJ*): rail CER independiente. Payoff a vto = max(rail_TAMAR, CER_ratio × (1+cer_spread)^years). Para futuros lejanos el CER se proyecta **compuesto**, NO linealmente — `tamar.project_cer_at` (toma el crecimiento de los últimos 30 días y lo capitaliza `(1+g)^meses`). El `cer_spread` se devenga act/365.25 desde la emisión.
- **Contrato del V.Téc / payoff de los DUAL_CER_TAMAR** (invariante de CLAUDE.md; ya se rompió
  dos veces): la cadena es **settlement T+N → lag CER de 10 hábiles → spread → max de
  rieles**, en ese orden. El escalón T+N corre sólo en el camino V.Téc (`to_date == ref`,
  `cer_settle_lag` provisto); el payoff a vencimiento va sin escalón (`end` ya es la fecha
  de pago). El paso a paso completo está en el docstring de `core/domain/pricing/tamar.py`:
  leerlo ANTES de tocar `tamar_dual_payoff_at` o `calculate_technical_value`.
- **TIR** TAMAR-family: TEA nominal contra el payoff proyectado, `(payoff/precio)^(1/años) − 1`
  (1 solo flujo, cerrada). Inversa exacta: `price_from_tir = payback / (1+tir)^años`. Para
  DUAL_CER_TAMAR la TIR es **nominal** (no real): es la que hace comparable la columna con los
  DUAL TAMAR del mismo panel y la única consistente con el max de rieles (ver docstring de
  `DualCerTamarStrategy`).
- **MD bullet** TAMAR/DUAL usa **m=12** (capitalización mensual) → `MD = years / (1+TEA)^(1/12)`. DL usa m=1.
  (DUAL_CER_TAMAR también m=12. El "m=1" de DL es porque hereda la duración vanilla
  `Macaulay/(1+TEA)^(1/freq)` sobre sus flujos reales y con un único flujo `freq=1`.)
- **Revaluaciones** `_TAM` / `_TF`: `FinancialEngine.recompute_as_tamar_puro` re-valúa un DUAL
  como PURO (rail TAMAR solo, sin floor) y `recompute_as_tasa_fija` como si sólo corriera el
  floor (TAMAR=0, `pricing/stubs.py::ZeroTamar`); el modal (`bond_detail.py`) parsea esos
  sufijos de leg. El panel `tamar` de este fork lista PURO + DUAL + DUAL_CER_TAMAR juntos.

### Bonos DOLAR LINKED

- Precio en pesos; **par = 100 USD**.
- V.Téc en pesos = `residual_USD × mayorista_venta` (FX desde dolarapi; residual = suma de
  amortizaciones USD futuras + accrued USD).
- Paridad = `price_pesos / V.Téc_pesos` (en rango 80-105% típico).
- TIR es **USD TIR**: precio se deflacta por FX antes de XIRR (day-count `ACT/365`, ver Day-count),
  sobre los flujos USD **reales** (maneja amortizables; no asume bullet).
- **Multi-pata** (`DolarLinkedStrategy`): la pata **pesos** (sufijo `…O` o mono-ticker tipo
  TZV*) se divide por el **oficial** (mayorista venta = A3500); **MEP** (`…D`) y **CABLE**
  (`…C`) ya cotizan en USD → cálculo directo, sin /FX, y su V.Téc queda en USD.

### Obligaciones Negociables (ON hard-dollar)

- Categoría `HARD DOLLAR`, **multi-ticker** (`…O` = pesos, `…D` = MEP, `…C` = CABLE; panel default `…D`).
  Cashflows en USD. `HardDollarStrategy` hereda toda la mecánica multi-pata de Dólar Linked y
  sólo cambia el FX de la pata pesos: **MEP** (dólar bolsa) si el bono es **Ley Argentina**,
  **CCL/cable** si es Ley Extranjera **o sin ley declarada** (el universo ON es mayormente ley
  NY) — `Instrument.is_ley_argentina` normaliza las grafías (`Argentina`/`ARG`/`Local`/…).
- **Day-count por instrumento**: las ON del informe usan `ACT/365` ("real/365", base de
  intereses del calculador del broker); es el default de `build_instrument` para
  `HARD DOLLAR`/`DOLLAR LINKED` con `base calculo` en blanco. Las ON de bancos cargadas por
  ABM varían: ej. **BACH = 30/360**, **BF37/BPCV/BYCV/CACB/CICA = ACT/365**. El motor descuenta
  con la convención declarada de cada una (ver Day-count). Validadas contra la referencia
  (ej. CICA 7.56%).
- **Serie/Clase + Ley Aplicable**: campos `serie_clase` (ej. "Clase XXXI", del listado
  IAMC/BYMA) y `ley_aplicable` (`Argentina` / `Extranjera`) en el form ABM de ONs;
  `serie_clase` se agrega al `short_name` para display (`"EMISOR - Clase X"`) y ambos van a
  `raw_fields`.
- **En este fork las ON viven SOLO en SQLite** (hoja `Obligaciones_Negociables` del ABM). El
  `core/infrastructure/on_catalog.py` del monitor (ingesta destructiva de
  `data/obligaciones_negociables.csv`) **no existe acá**: el CSV se conserva como semilla sin
  camino de ingesta (decisión pendiente). Para agregar/editar una ON: ABM.

### Bonos LECAP / BONCAP capitalizables

- Generador sintético usa `tem_licit` + `fecha_emision` + day-count **30/360** (`days_30_360`) para computar `payoff = 100 × (1+tem)^months`. Para S29Y6: con 30/360 → 359 días → 11.97 meses → payoff 132.05 (matchea la referencia). Con `base calculo = "Act/..."` usa days/30 en su lugar.
- V.Téc(t) = `100 × (payoff/100)^(elapsed/total)` (interpolación geométrica desde emisión).
  Si el capitalizable además es CER (LECER con `cer_base`), ese valor se multiplica por el
  factor CER.
- TIR es TEA pura; TNA y TEM se derivan en base 365 (act/365):
  - `TEM = (1+TEA)^(30/365) − 1`
  - `TNA = 365 × ((1+TEA)^(1/365) − 1)`
- Otras conversiones disponibles en `conventions.py`: `tea_to_tna_monthly` (m=12,
  "Tir Nominal" de TAMAR/LECAP en el modal), `tea_to_tna_freq` (TNA nominal a la
  frecuencia del cupón, convención IAMC para bonos con cupón), `tea_to_tem_m12`.

### Modified Duration — convención BYMA/IAMC

`MD = Macaulay_years / (1+TEA)^(1/freq)`, donde `freq` es la frecuencia anual de pagos
(2 = semestral). El campo `payment_frequency` del Instrument se infiere automáticamente del
gap mediano entre cashflows si no viene en la fila
(`repositories._infer_payment_frequency`). Con un solo flujo futuro, `freq = 1` (bullet).
TAMAR-family: m=12 (ver arriba).

### Day-count / convención de descuento (centralizado en `core/domain/daycount.py`)

> **Refactor 2026-05-30 (v7.2).** Antes el descuento (TIR/duration/PV/convexidad) estaba cableado a
> `_JULIAN_YEAR = 365.25` salvo la rama 30/360 — **ignorando el `day_count` declarado del bono**. Las
> ONs `ACT/365` se descontaban a 365.25 → error sistemático de ~1bp+. Ahora se respeta lo declarado.

- **Fuente única**: `daycount.year_fraction(start, end, DayCount)` es la ÚNICA fracción de año de
  descuento. Convenciones: `ACT/365` (días/365), `ACT/365.25` (días/365.25 — año juliano, **default
  soberano**), `30/360` (ISDA, `days_30_360/360`), `ACT/ACT` (ISDA actual/actual). `parse_day_count()`
  tolera alias/blanks/basura. `Instrument.day_count_enum` resuelve la convención (BOPREAL → 30/360).
- **Defaults al construir** (`build_instrument`): `base calculo` en blanco → BOPREAL `30/360`
  (prospecto BCRA), ON `HARD DOLLAR`/`DOLLAR LINKED` → `ACT/365`, resto → `ACT/365.25`.
- **Respetar lo declarado**: todos los sitios de descuento (`pricing/base.py`, `pricing/metrics.py`,
  `pricing/strategies.py`, `services.calculate_theoretical_price`) descuentan con
  `inst.year_fraction_to(date, ref)`. Para `30/360` y `ACT/365.25` el resultado es **bit-idéntico** al
  motor viejo (sólo cambian los `ACT/365`: ONs hard-dollar + Dólar-Linked, que ahora matchean la referencia —
  ej. CICA 7.56%, antes 7.57%).
- **Stub final** (`metrics.discount_year_fractions`): un último cupón corto genuino (vto bien
  antes del fin del período regular, cupón ~completo, el anterior es cupón y no amort-only) se
  descuenta al **fin del período regular** — convención ISMA para reestructurados (ej. CLISA
  2031: último cupón 12/10/2031, período regular cerraba 10/12/2031 → se descuenta al 10/12).
  Para bonos regulares no cambia nada.
- **Solver Brent** (`core/domain/xirr.py`): `xirr(flows, dates, day_count=None)`. brentq con
  auto-bracketing geométrico (encuentra yields >1000% que el bracket fijo `[-0.999,10]` perdía); Newton
  sólo como pre-paso rápido. `_npv` overflow-safe; `duration`/`vanilla_pv` con guard de `OverflowError`
  → `None` limpio (mata el crash histórico de CUAP con TIR degenerada). TIR ≤ −100% → `None`
  (elevar una base ≤ 0 a exponente fraccional da un complejo, no una excepción).
- **Invariante de cashflows**: `Instrument` ordena sus cashflows por fecha en un `field_validator` (el
  schedule es cronológico por definición) → el hot-path de pricing ya no re-sortea defensivamente.
- **Ex-cupón**: un flujo que paga EXACTAMENTE en la fecha de liquidación lo cobra el
  **vendedor** (el comprador liquida ese día y no es tenedor de registro) → cuenta como
  pasado. Corte estricto en todo el motor: futuros = `date > ref`, pasados = `date <= ref`.

### Soberanos: 3 especies por moneda (ARS / MEP / CABLE) + pricing de la pata ARS

> Reemplaza el viejo "filtro MEP-only": ya **no** se ocultan las patas pesos/CABLE.
> Ahora se muestran las 3 monedas y la pata ARS se pricea bien (ver abajo).

Cada bono soberano (BONAR/GLOBAL) cotiza en 3 monedas con tickers distintos pero **mismo flujo** — solo cambia el precio: **ARS** (sin sufijo, ej. AL30), **MEP** (sufijo `D`, AL30D), **CABLE** (sufijo `C`, AL30C). AO27D/AO28D son sólo-MEP. Convención de moneda por sufijo (single source of truth: `core/domain/currency.py::ccy_from_suffix` / `position_currency`; `panels_rows._ticker_ccy` e `instruments_abm._sob_slot` son wrappers): última letra **D→MEP, C→CABLE, resto→ARS**.

**Pricing de la pata ARS** (corrige el mismatch ARS-price / USD-cashflows que antes daba TIR −94% / paridad 130000%): la pata peso cotiza en pesos pero los cashflows son USD, así que para las métricas se usa el **precio USD implícito = precio_pesos ÷ offer (venta)**, **MEP si BONAR o BOPREAL (ley local) / CABLE si GLOBAL (ley NY)** (dolarapi: `bolsa`=MEP, `contadoconliqui`=CABLE). Vive en `core/use_cases/generate_report.py::_enrich_metrics` + `_sovereign_ars_usd_price` (NO en el motor, para no romper la equivalencia): TIR / V.Téc / MD / paridad se calculan sobre el precio dolarizado, pero la columna **Precio** del panel muestra los **pesos sin decimales**. La pata pesos se detecta por NO terminar en D/C; BOPREAL pesos = base BPO* (BPOC7).

**ABM**: las 3 especies se consolidan en **1 solo bono** (form con los 3 tickers, agrupadas por sufijo, `_sob_group`). Siguen siendo filas independientes en SQLite (el pricing las pricea por ticker como siempre); la consolidación es solo de la capa ABM. **Panel BONARES**: botones **ARS/MEP/CABLE** filtran las filas por moneda (default MEP; `panels_schema.CCY_FILTER_PANELS`).

### Date parsing — bug histórico

`repositories._parse_date_value` detecta strings ISO (`YYYY-MM-DD`) y los parsea con `dayfirst=False`. Sin esto, pandas con `dayfirst=True` swappeaba mes/día en strings ISO (ej. `2026-07-09` → `2026-09-07`), corrompiendo el schedule de cupones de los soberanos (que guardan fechas ISO en `Cashflows`). El módulo `cashflow_synth` además normaliza `datetime → date` para evitar TypeError al comparar tipos mixtos (`cf.date >= settle_date`).

### Accrued period para soberanos mid-amortización

Los soberanos mid-amort (AL29D/AL30D/GD30D/...) suelen cargar **sólo cashflows futuros** (no traen los cupones ya pagados). Antes, el helper `_period_bounds` y el accrued en `calculate_technical_value` caían a `emission_date` como inicio del período corriente cuando no había past flows — y como emisión puede ser de hace 5+ años, accrued y V.Téc venían completamente inflados (ej. AL29D: 2082 días en vez de 130).

**Regla actual** (`pricing/metrics.py::period_bounds`; `FinancialEngine._period_bounds` delega ahí):

1. Si hay past flow (`date <= ref`, ex-cupón) → tomar el último.
2. Sin past flow, inferir `prev = next_cf − (12/freq) meses` usando `relativedelta` (aritmética calendario exacta, no `days=365/freq` que daba off-by-1 entre cupones).
3. Si la emisión está a **menos de 2 períodos** del próximo cupón (`emission ≥ next_cf − 2·(12/freq) meses`), el bono está en su **primer período** y acumula desde `emission_date` — cubre 1er cupón regular, corto o largo (ej. CS50: emisión 10/12 → 1er cupón 10/09, 9 meses = 1.5 períodos).
4. Si la emisión es más vieja que eso, es un bono mid-life con flows pasados recortados → usar `prev` inferido, NO la emisión.

`accrued_interest` (`pricing/metrics.py`) es la única implementación; `calculate_technical_value` delega ahí — no duplica la lógica. Detalles que mueven el número:
- **30/360**: `period_days` y `elapsed` con `days_30_360`, contando desde la fecha **programada** del cupón anterior, sin correr a día hábil (cupón sáb 30/05 → 10 días al 10/06, no 9).
- **ACT/\***: los días corren desde la fecha de **pago real** del cupón anterior (día hábil *following* del corte programado; cupón sáb 17/01 → pagado lun 19/01 → días desde el 19). La tasa diaria se deriva del período **programado** del cupón pasado (= tasa anual/365; robusto ante "long last coupon"); en el primer período se prorratea `next_cf` sobre los días reales.
- 0 para zero-coupon / capitalizables (LECER, LECAP, BONCER ZC, PURO, DUAL).

---

## CÓMO EXTENDER LA MATEMÁTICA FINANCIERA

`core/domain/services.py::FinancialEngine` es una **fachada delgada** que preserva las firmas
públicas (consumidores: `bond_detail`, `generate_report`, `bei`) y delega: dispatch por tipo →
`pricing/registry.strategy_for`; cálculo → `PricingStrategy.{technical_value,tir,duration,price_from_tir}`
(`pricing/base.py` + `pricing/strategies.py`); métricas del modal → `pricing/metrics.py`;
conversiones/tasas → `conventions.py`; XIRR → `xirr.py`. Matemática nueva va en esos módulos,
no como rama nueva en la fachada. Métodos disponibles:

| Método | Devuelve |
|---|---|
| `xirr(flows, dates)` | TIR de un cashflow (decimal fraction; 0.30 = 30%). Debajo, `xirr.xirr(flows, dates, day_count=None)`. |
| `calculate_tir(snapshot, indices_provider, fx_provider, settle_date=None, tamar_forecast=None)` | TIR del instrumento; strategies específicas: CER, DL, hard-dollar, TAMAR PURO/DUAL, DUAL_CER_TAMAR. `settle_date` override usado por la calculadora del modal (T+0/T+1). |
| `calculate_duration(snapshot, tir, settle_date=None)` | Modified Duration con convención BYMA (`m=freq`); bullets TAMAR/DUAL usan m=12 |
| `calculate_technical_value(snapshot, indices_provider, fx_provider, ref_date=None, settle_lag=1)` | V.Téc universal: residual + accrued; branches para DL (en pesos), CER (× CER_ratio), TAMAR PURO/DUAL (capitalizado), DUAL_CER_TAMAR (max rails). `settle_lag` (1 = 24hs, 0 = CI) es el escalón de liquidación que se aplica a la referencia CER. |
| `calculate_theoretical_price(instrument, tir, ref_date)` | Precio implícito al descontar al TIR dado (con el day-count declarado) |
| `tir_from_price(snapshot, price_override, indices, fx, settle_date=None)` | Inversa de `calculate_tir`: TIR para un precio (dirty) dado. Reusa toda la lógica per-type vía `model_copy` del snapshot. |
| `price_from_tir(snapshot, tir, indices, fx, settle_date=None)` | Precio (dirty) implícito al TIR dado. Branches por tipo: vanilla (PV), CER (real × CER_ratio), DL (USD/FX), TAMAR PURO/DUAL/DUAL_CER_TAMAR (payback / (1+tir)^t). |
| `projected_payoff(instrument, indices_provider, tamar_forecast=None, ref_date=None)` | Payback proyectado per-100 a vencimiento para bonos TAMAR-family. |
| `accrued_interest(instrument, ref_date)` | Intereses corridos per-100-VN, accrual lineal sobre el cupón corriente. 0 para zero-coupon / capitalizables. |
| `days_since_last_coupon(instrument, ref_date)` | Días transcurridos desde el pago real del último cupón (o desde emisión si nunca pagó). |
| `residual_nominal(instrument, ref_date)` | Valor Residual per-100 = suma de amortizaciones futuras. Fallback: 100 − amortizado. |
| `current_yield(instrument, price_dirty, ref_date)` | Cupones próximos 12 meses / dirty price (decimal). |
| `dv01(instrument, tir, ref_date)` | ΔP per-100 ante -1bp en TIR. Signo positivo (precio sube cuando yield baja). |
| `convexity(instrument, tir, ref_date)` | Convexidad en años² (PPV en la calculadora del modal). Pareja con MD: `ΔP/P ≈ -MD×Δy + 0.5×C×(Δy)²`. |
| `calculate_pct_change(current, previous)` | Variación porcentual (None-safe + epsilon guard) |
| `tea_to_tem(tea)` | TEA → TEM act/365 |
| `tea_to_tna(tea)` | TEA → TNA base 365 (diaria capitalizada) |
| `tea_to_tna_monthly(tea)` / `tea_to_tna_freq(tea, freq)` / `tea_to_tem_m12(tea)` | TEA → TNA m=12 · TNA nominal a la frecuencia del cupón (IAMC) · TEM m=12 |
| `recompute_as_tamar_puro(snapshot, indices_provider)` | Re-valúa un DUAL como si fuera PURO (rail TAMAR solo). Leg `_TAM`. |
| `recompute_as_tasa_fija(snapshot, indices_provider)` | Re-valúa un DUAL como si sólo corriera el floor fijo (TAMAR=0). Leg `_TF`. |

### Override de settle_date (T+0/T+1)

Los métodos públicos que dependen del settle date aceptan un parámetro opcional `settle_date`
(o `ref_date` para V.Téc) que sobrescribe el default. Sin override, cada método cae a
`conventions.settlement_for(instrument_type)` o `date.today()`. La calculadora del modal usa
esto para exponer un toggle T+0/T+1 que recalcula TODO desde la fecha elegida — sin esto,
accrued/V.Téc quedaban en T+0 mientras TIR estaba en T+1 (inconsistencia silenciosa de 1 día).

Helper: `conventions.resolve_settle(instrument_type, override)` —
`override if override is not None else settlement_for(instrument_type)`.

**Convención T+0 / T+1**: `conventions.settlement_for` usa **lag=1 (T+1) para TODOS los tipos**,
LECAP/BONCAP/LECER incluidos (el `instrument_type` se mantiene en la firma por compat). La
regla vieja "T+0 para LECAP/BONCAP/LECER/token CI, T+1 el resto" **ya no rige**. El toggle
T+0/T+1 del modal sigue siendo del usuario: `bond_detail._resolve_ref(lag)` (0 → hoy, 1 →
siguiente hábil BYMA vía `holiday_engine.settlement_byma`). `settlement_byma_date` sólo
acepta lag ∈ {0, 1}; CI = mismo día si es hábil, si no el siguiente. TODO el settlement cuelga
del calendario de `core/holiday_engine.py` (`data/feriados_ar.xlsx`): un feriado mal cargado
mueve el V.Téc de cada bono indexado.

### Curvas y BEI (`core/domain/yield_curve.py`)

| Función | Origen |
|---|---|
| `NelsonSiegelCurve` (4 params) | NT8 Eq.11 |
| `NelsonSiegelSvenssonCurve` (6 params) | NT3 Eq.17 |
| `bootstrap_zero_rates(bonds, today)` | NT3 Eq.11-16 |
| `fisher_break_even(i, r)` | NT8 Eq.8 — `π = (1+i)/(1+r) − 1` |
| `gamma_known_cer_factor(cer_liq, cer_last)` | NT8 Eq.A4 — `γ = CER_ULT / CER_LIQ-10h` |
| `forward_rate(curve, t1, t2)` | NT3 Eq.8'/9' — `F = ((1+s_t2)^t2 / (1+s_t1)^t1)^(1/(t2−t1)) − 1` |
| `forward_bei_between_tenors(...)` | NT3 Eq.10 — `π_fwd = (1+F^i)/(1+F^r) − 1` |
| `pair_delta(...)` | NT8 Apéndice Eq.A13 — `δ = P_cer · (1+i_lecap)^(d/365) / [(Principal+cupón) · (CER_LIQ-10h/CER_BASE) · γ]`; devuelve δ−1 (validado: da exactamente 3.81% para S14F5/T2X5) |
| `pair_monthly_inflation(δ, days)` | NT8 Eq.A12 — `(1+δ)^(31/days) − 1` |
| `real_fx_drift(dev_rate, infl_rate)` | Fisher sobre FX — `(1+dev)/(1+π) − 1` |

Convenciones del módulo: tenores en años, tasas como fracción decimal (0.30 = 30% anual).
Consumidor: `apps/cli/bei.py::compute_bei_tables` (NT3/2019 + NT8/2024 completo: bootstrap →
NSS con fallback NS y lineal → BEI spot Fisher → forward entre tenores → sendero mensual →
método de pares → rail TAMAR forward + BEI TAMAR → deval DLR y TC real → ajuste γ opcional),
que alimenta los paneles `bei_tenor` / `bei_sendero` / `bei_pares`.

**Reglas operativas (§BEI)**:
- El compute BEI corre en su **propio loop supervisado** (`app.py::_bei_loop`, eager al
  arrancar y después cada `settings.bei_refresh_sec` = 300s), vía `to_thread` — es pesado
  (segundos) y no puede vivir dentro del refresh de 5s.
- **I/O y parsing FUERA del lock**: cualquier provider/cache que serialice con un lock
  (índices BCRA, histórico BEI) hace la red y el parseo sin retenerlo; adentro sólo el
  swap del estado. Retener un lock de CLASE a través de 4 `httpx.get` (10s c/u) congelaba
  la app entera hasta que BCRA respondiera (`indices_provider._fetch_all` / `prefetch`).
- `data/history/bei_diario.csv` es **semilla** read-only; el histórico vivo se acumula en
  `db_dir/history/` (`history_paths.resolve_read` / `state_path`).

### Sendero mensual (`core/domain/inflation_path.py`)

`monthly_inflation_path(nom_curve, real_curve, today, months_ahead=12)` — implementa la Fig.4
de NT8/2024. Para cada mes calendario, computa BEI forward usando las curvas y la convención
de Fisher por intervalo. El primer mes es parcial (de `today` a fin de mes) y su tasa mensual
se interpola desde la tasa del período parcial; meses con menos de `min_segment_days` (5) de
cobertura se saltean.
