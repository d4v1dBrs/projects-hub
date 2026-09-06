/* Bond popup lifecycle: lazy history, scoped charts, abortable requests. */
(function () {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const finite = n => typeof n === 'number' && Number.isFinite(n);
  const fmt = (n, digits = 2) => finite(n) ? n.toLocaleString('es-AR', {minimumFractionDigits: digits, maximumFractionDigits: digits}) : '--';
  const pct = n => finite(n) ? fmt(n * 100) + '%' : '--';
  const percent = n => finite(n) ? fmt(n) + '%' : '--';
  const signed = n => finite(n) ? (n > 0 ? '+' : '') + fmt(n) : '--';
  const tone = n => finite(n) ? n > 0 ? 'bw-up' : n < 0 ? 'bw-down' : '' : '';
  const date = value => value ? String(value).slice(0, 10).split('-').reverse().join('/') : '--';
  const icon = name => `<i data-lucide="${name}" aria-hidden="true"></i>`;
  const kpi = (label, value, note = '', cls = '') => `<div class="bw-kpi"><small>${esc(label)}</small><strong class="${cls}">${esc(value)}</strong>${note ? `<em>${esc(note)}</em>` : ''}</div>`;
  const command = (action, label, glyph = 'calculator', primary = false) => `<button type="button" class="bw-command${primary ? ' bw-primary' : ''}" data-action="${action}">${icon(glyph)}${esc(label)}</button>`;
  const note = text => `<p class="bw-note">${esc(text)}</p>`;
  const table = (headers, rows) => `<div class="bw-table-wrap"><table><thead><tr>${headers.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;
  const tr = cells => `<tr>${cells.map(c => `<td>${c}</td>`).join('')}</tr>`;
  const notes = values => (values || []).map(note).join('');
  const defaults = {nominal:10000, capital:100000, entry_fee_pct:.5, exit_fee_pct:.5, annual_fee_pct:0, horizon_days:365, shock_bps:100, income_target:0, inflation_pct:20};
  let libraryPromise, current;

  function chartLibrary() {
    if (window.LightweightCharts) return Promise.resolve(window.LightweightCharts);
    if (!libraryPromise) libraryPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = '/static/vendor/lightweight-charts-5.2.1.min.js';
      script.onload = () => resolve(window.LightweightCharts);
      script.onerror = () => { libraryPromise = null; script.remove(); reject(new Error('No se pudo cargar el motor del grafico.')); };
      document.head.appendChild(script);
    });
    return libraryPromise;
  }

  class Workbench {
    constructor(root) {
      this.root = root;
      this.data = JSON.parse(root.querySelector('.bw-data').textContent);
      this.previousOverflow = document.documentElement.style.overflow;
      document.documentElement.style.overflow = 'hidden';
      this.ticker = root.dataset.ticker;
      this.lag = Number(root.dataset.lag);
      this.params = {...defaults};
      this.drafts = {};
      this.active = 'trading';
      this.controllers = new Map();
      this.plots = new Map();
      this.range = 1096;
      this.historyMode = 'line';
      this.renderHeader();
      this.renderActive();
      this.onClick = e => this.click(e);
      this.onChange = e => this.change(e);
      this.onInput = e => this.rememberInput(e);
      this.onSubmit = e => this.submit(e);
      this.onKey = e => this.key(e);
      root.addEventListener('click', this.onClick);
      root.addEventListener('change', this.onChange);
      root.addEventListener('input', this.onInput);
      root.addEventListener('submit', this.onSubmit);
      root.addEventListener('keydown', this.onKey);
      root.parentElement.addEventListener('click', e => { if (e.target === root.parentElement) this.close(); });
      this.timer = setInterval(() => {
        if (!document.hidden && this.active === 'trading' && !this.root.querySelector('input:focus') && !this.dirty) this.refresh(false);
      }, 15000);
      this.icons();
    }

    slot(name) { return this.root.querySelector(`[data-slot="${name}"]`); }
    pane(name = this.active) { return this.root.querySelector(`[data-pane="${name}"]`); }
    icons() { if (window.lucide) window.lucide.createIcons({root:this.root}); }
    status(message = '') { const el = this.slot('status'); el.textContent = message; el.hidden = !message; }
    close() { this.dispose(); document.getElementById('modal').replaceChildren(); }
    dispose() {
      if (this.disposed) return;
      this.disposed = true;
      document.documentElement.style.overflow = this.previousOverflow;
      clearInterval(this.timer);
      this.controllers.forEach(c => c.abort());
      this.plots.forEach(p => p.destroy());
      if (this.historyChart) this.historyChart.remove();
      if (this.resizeObserver) this.resizeObserver.disconnect();
      this.root.removeEventListener('click', this.onClick);
      this.root.removeEventListener('change', this.onChange);
      this.root.removeEventListener('input', this.onInput);
      this.root.removeEventListener('submit', this.onSubmit);
      this.root.removeEventListener('keydown', this.onKey);
    }

    async request(kind, path, options = {}) {
      this.controllers.get(kind)?.abort();
      const controller = new AbortController();
      this.controllers.set(kind, controller);
      try {
        const response = await fetch(`/bond/${encodeURIComponent(this.ticker)}/${path}`, {...options, signal:controller.signal});
        if (!response.ok) throw new Error(response.status === 422 ? 'Parametros fuera de rango. Revisar los importes y las tasas.' : 'No se pudo obtener el analisis. Reintentar.');
        const result = await response.json();
        if (this.disposed || controller.signal.aborted) return null;
        return result;
      } finally {
        if (this.controllers.get(kind) === controller) this.controllers.delete(kind);
      }
    }

    input(name, label, min = 0, max = 1e12, step = 'any', fallback = '', type = 'number') {
      const value = this.drafts[name] ?? this.params[name] ?? fallback;
      return `<label>${esc(label)}<input name="${name}" type="${type}" min="${min}" max="${max}" step="${step}" value="${esc(value)}" placeholder="Mercado"></label>`;
    }
    submitButton(label = 'Calcular') { return `<button class="bw-command bw-primary" type="submit">${icon('calculator')}${esc(label)}</button>`; }
    inflationInput() {
      const meta = this.data.detail.meta;
      return meta.is_cer_proj && !meta.is_tamar_family ? this.input('inflation_pct','Inflacion escenario CER (%)',-50,1000,.1) : '';
    }

    renderHeader() {
      const d = this.data.detail, m = d.metrics || {}, q = d.market || {}, s = this.data.source || {};
      this.currency = this.data.trading?.currency || d.meta.quote_currency || d.meta.currency || d.meta.moneda || '';
      this.slot('quote').innerHTML = kpi('Ultimo / 100 VN', fmt(q.price), this.currency) + kpi('TIR (TEA)', pct(m.tir), this.data.trading?.yield_basis || '', tone(m.tir)) + kpi('Variacion diaria', percent(q.change_pct), '', tone(q.change_pct)) + kpi('Duration modificada', fmt(m.duration), 'anos') + kpi('Paridad', pct(m.parity)) + kpi('Vencimiento', date(d.meta.fecha_vencimiento || d.meta.maturity_date || d.meta.maturity));
      this.slot('source').textContent = `${s.label || 'Snapshot del monitor'} | ${s.snapshot_at ? 'Refresco ' + s.snapshot_at.slice(11,19) + ' AR' : 'Sin snapshot'} | ${s.note || ''}`;
      this.root.querySelector('.bw-identity > span').textContent = `${d.meta.instrument_type || ''} | ${d.meta.cupon || ''}`;
      this.slot('foot').textContent = `Liquidacion ${date(d.settle_date)} | ${this.lag ? '24hs' : 'CI'} | ${d.meta.instrument_type || d.meta.type || ''}`;
      const scenario = this.root.querySelector('.bw-scenario') || document.createElement('div');
      scenario.className = 'bw-scenario bw-source';
      scenario.textContent = finite(this.params.price) ? `Escenario de entrada: ${fmt(this.params.price)} ${this.currency} por 100 VN. La cabecera conserva la cotizacion observada.` : finite(this.params.yield_pct) ? `TIR de escenario: ${percent(this.params.yield_pct)} en Trading y Docencia. WM conserva el precio de entrada; la cabecera muestra el mercado.` : '';
      scenario.hidden = !scenario.textContent;
      this.slot('source').after(scenario);
      this.root.querySelectorAll('.bw-head [data-lag]').forEach(b => b.setAttribute('aria-pressed', String(Number(b.dataset.lag) === this.lag)));
    }

    activate(name) {
      this.active = name;
      this.root.querySelectorAll('[data-tab]').forEach(button => {
        const selected = button.dataset.tab === name;
        button.setAttribute('aria-selected', String(selected));
        button.tabIndex = selected ? 0 : -1;
      });
      this.root.querySelectorAll('[data-pane]').forEach(p => { p.hidden = p.dataset.pane !== name; });
      this.root.querySelector('.bw-content').scrollTop = 0;
      this.renderActive();
    }

    renderActive() {
      if (this.disposed) return;
      if (this.active === 'trading') this.renderTrading();
      if (this.active === 'wealth') this.renderWealth();
      if (this.active === 'teaching') this.renderTeaching();
      if (this.active === 'chart' || this.active === 'quant') this.loadHistory();
      this.icons();
    }

    stressTable(rows = this.data.trading?.stress || []) {
      return table(['Shock TIR', 'TIR escenario', 'Precio', 'Variacion precio', `P&L ${this.currency}`], rows.map(r => tr([signed(r.shock_bps) + ' pb', pct(r.yield), fmt(r.price), `<span class="${tone(r.return_pct)}">${percent(r.return_pct)}</span>`, `<span class="${tone(r.pnl)}">${signed(r.pnl)}</span>`])));
    }

    renderTrading() {
      const d = this.data.detail, q = d.market || {}, t = this.data.trading || {};
      const peers = (this.data.peers || []).map(p => tr([`<button data-peer="${esc(p.ticker)}">${esc(p.ticker)}</button>`, fmt(p.price), pct(p.yield), fmt(p.duration), signed(p.spread_bps)]));
      this.pane().innerHTML = `<div class="bw-grid bw-section"><div><h3>${icon('arrow-left-right')}Puntas y liquidez</h3>
        <div class="bw-book">${kpi('Demanda / BID', fmt(q.bid), 'TIR ' + pct(t.bid_yield), 'bw-up')}${kpi('Oferta / ASK', fmt(q.ask), 'TIR ' + pct(t.ask_yield), 'bw-down')}</div>
        <div class="bw-stats">${kpi('Spread', fmt(t.spread), fmt(t.spread_bps) + ' pb del medio')}${kpi('Precio medio', fmt(t.midpoint))}${kpi('Monto negociado', fmt(q.volume, 0), 'Importe informado; no VN')}${kpi('Operaciones', fmt(q.operations, 0))}</div>
        ${note('Puntas indicativas con demora. El feed no permite afirmar profundidad ejecutable, prioridad ni volumen disponible a cada precio.')}
        </div><div><h3>${icon('crosshair')}Posicion y sensibilidad</h3>
        <form class="bw-form" data-form="position">${this.input('nominal','Posicion (VN)')}${this.input('cost_price','Costo / 100 VN',.000001,1e9)}${this.submitButton('Valuar')}</form>
        <div class="bw-stats">${kpi('Valor de mercado', fmt(t.market_value), this.currency)}${kpi('P&L sin cupones', signed(t.unrealized_pnl), this.currency, tone(t.unrealized_pnl))}${kpi('DV01 posicion', fmt(t.dv01_position), this.currency + ' / 1 pb')}${kpi('Nominales', fmt(t.nominal, 0))}</div>
        </div></div>
        <div class="bw-section"><h3>${icon('sliders-horizontal')}Precio, rendimiento y stress</h3>
        <form class="bw-form" data-form="simulation">${this.input('price','Precio escenario / 100 VN',.000001,1e9)}${this.input('yield_pct','TIR escenario (%)',-90,1000)}${this.input('shock_bps','Shock adicional (pb)',-5000,5000,1)}${this.submitButton('Simular')}${command('reset','Restablecer mercado','rotate-ccw')}</form>
        ${note('Precio o TIR: al modificar uno se despeja el otro. La simulacion mantiene las convenciones del instrumento; no representa una orden.')}
        <div class="bw-stats">${kpi('Precio base escenario', fmt(t.base_price ?? t.simulated_price), this.currency)}${kpi('TIR base escenario', pct(t.base_yield ?? t.simulated_yield))}${kpi('Precio con shock',fmt(t.stressed_price),this.currency)}${kpi('TIR con shock',pct(t.stressed_yield))}</div>${this.stressTable()}
        </div><div class="bw-section"><h3>${icon('calendar-range')}Salida a horizonte</h3>
        <form class="bw-form" data-form="horizons">${this.input('entry_fee_pct','Comision entrada (%)',0,10,.01)}${this.input('exit_fee_pct','Comision salida (%)',0,10,.01)}${this.submitButton('Recalcular costos')}</form>
        ${notes(t.horizons_assumptions)}${(t.horizons || []).length ? table(['Dias','Salida','Shock TIR','Precio salida','Cupones','Amortizacion','Retorno bruto','Neto comisiones'],t.horizons.map(r=>tr([fmt(r.days,0),date(r.date),signed(r.yield_shift_bps)+' pb',fmt(r.exit_price),fmt(r.coupons),fmt(r.amortization),percent(r.return_pct),`<span class="${tone(r.net_return_pct)}">${percent(r.net_return_pct)}</span>`]))) : note(t.horizons_reason || 'Sin flujos suficientes para este escenario.')}
        </div><div><h3>${icon('list-filter')}Comparables por duration</h3>${note('Misma familia y moneda de cotizacion; snapshot 24hs. Diferencia de TIR frente al bono elegido, sin ajuste por curva ni recomendacion de compra.')}
        ${peers.length ? table(['Bono','Precio','TIR','MD','Diferencia (pb)'],peers) : note('Sin comparables disponibles para esta familia y moneda.')}</div>${notes(this.data.warnings)}`;
    }

    renderWealth() {
      const w = this.data.wealth || {};
      this.pane().innerHTML = `<h3 class="bw-print-title">Propuesta de inversion: ${esc(this.ticker)}</h3>
        <div class="bw-toolbar"><h3>${icon('briefcase-business')}Propuesta y costo total</h3><span class="bw-spacer"></span>${command('print','Imprimir propuesta','printer')}${command('flows-csv','Flujos CSV','download')}</div>
        <form class="bw-form" data-form="wealth">${this.input('capital','Capital disponible (' + (w.currency || this.currency) + ')',.01)}${this.input('price','Precio de entrada / 100 VN',.000001,1e9)}${this.input('horizon_days','Horizonte (dias)',1,10950,1)}${this.input('income_target','Objetivo de cupones en el horizonte',0)}${this.input('entry_fee_pct','Comision entrada (%)',0,10,.01)}${this.input('exit_fee_pct','Comision salida (%)',0,10,.01)}${this.input('annual_fee_pct','Asesoramiento anual (%)',0,10,.01)}${this.inflationInput()}${this.submitButton('Calcular propuesta')}</form>
        ${!w.supported ? `<div class="bw-empty">${esc(w.reason || 'No hay flujos suficientes para construir una propuesta.')}</div>` : `
        <div class="bw-stats bw-section">${kpi('TIR bruta escenario',pct(w.gross_yield))}${kpi('TIR neta escenario',pct(w.net_yield),'Convencion de dias del bono',tone(w.net_yield))}${kpi('Costo total',fmt(w.fees_total),w.currency)}${kpi('Nominales teoricos',fmt(w.nominal,2),'Verificar lote minimo')}${kpi('Inversion inicial',fmt(w.initial_outlay),w.currency + ', incluye entrada')}${kpi('Cupones del horizonte',fmt(w.income_in_horizon),w.currency)}${kpi('Amortizaciones',fmt(w.principal_in_horizon),w.currency)}${kpi('Capital para objetivo',fmt(w.capital_for_target),'Solo cupones, no amortizacion')}</div>
        <div class="bw-grid bw-section"><div><h3>Impacto de la comision de entrada</h3>${table(['Entrada','TIR neta'],(w.fee_comparison || []).map(r => tr([percent(r.entry_fee_pct),pct(r.net_yield)])))}</div>
        <div><h3>Supuestos de la propuesta</h3>${notes(w.assumptions)}${note('No incluye impuestos ni garantiza reinversion a la TIR. Riesgos: credito soberano, liquidez, tasas, moneda y, cuando corresponde, indexacion. No sustituye la evaluacion de idoneidad del cliente.')}</div></div>
        <h3>Calendario de cobros y costos</h3>${note(`Horizonte efectivo: ${date(w.horizon_date)}. Valor estimado de venta: ${fmt(w.sale_value)} ${w.currency}.`)}${table(['Fecha','Cupon','Amortizacion','Venta','Bruto','Costos','Neto'],(w.cashflows || []).map(r => tr([date(r.date),fmt(r.interest),fmt(r.amortization),fmt(r.sale ?? 0),fmt(r.gross),fmt(r.fee),fmt(r.net)])))}`}`;
      this.icons();
    }

    renderTeaching() {
      const t = this.data.teaching || {}, e = t.next_event;
      const glossary = [
        ['Valor nominal (VN)','Unidad contractual de capital. Precio y flujos se expresan por 100 VN; no equivale al efectivo invertido.'],
        ['Precio sucio','Valor del bono con los intereses corridos incluidos. Es la base economica del desembolso, antes de comisiones.'],
        ['Precio limpio','Precio sucio menos intereses corridos. No implica que la pantalla del mercado cotice necesariamente en limpio.'],
        ['Intereses corridos','Renta devengada desde el inicio del periodo. Depende de la convencion de dias y del nominal residual.'],
        ['Corte de cupon','La separacion del derecho al cobro reduce los flujos que compra el nuevo tenedor. La fecha ex y la liquidacion deben verificarse en el aviso del emisor.'],
        ['Amortizacion','Devolucion de capital, no renta. Reduce el nominal residual y puede reducir cupones futuros.'],
        ['TIR / TEA','Tasa que iguala el precio con el valor presente de los flujos. No asegura retorno realizado: importan default, venta y reinversion.'],
        ['Duration modificada','Sensibilidad local: variacion de precio aproximada = -MD x cambio de TIR, con la tasa expresada en decimal.'],
        ['DV01','Cambio monetario aproximado por un movimiento de un punto basico (0,01 punto porcentual) en la TIR. Escala con los VN.'],
        ['Convexidad','Curvatura de la relacion precio-tasa. Mejora la aproximacion de duration para shocks mayores, pero no elimina el riesgo del modelo.'],
        ['CER y tasa real','En bonos CER, una TIR real no es una tasa nominal en pesos. Los cobros futuros dependen del indice y su rezago contractual.'],
        ['Retorno total','Cambio de precio mas cobros, con una regla explicita de reinversion. Un grafico de cierres sin ajustes no es retorno total.']
      ];
      this.pane().innerHTML = `<h3 class="bw-print-title">Clase de bonos: ${esc(this.ticker)}</h3><div class="bw-toolbar"><h3>${icon('graduation-cap')}Laboratorio del bono</h3><span class="bw-spacer"></span>${command('print','Imprimir clase','printer')}</div>
        <form class="bw-form" data-form="teaching">${this.input('yield_pct','TIR del experimento (%)',-90,1000)}${this.input('shock_bps','Shock de tasa (pb)',-5000,5000,25)}${this.input('nominal','Nominales del ejercicio',0,1e12)}${this.inflationInput()}${this.submitButton('Aplicar escenario')}${command('reset','Restablecer mercado','rotate-ccw')}</form>
        ${notes(t.assumptions)}
        ${!t.supported ? `<div class="bw-empty">${esc(t.reason || 'No hay un calendario de flujos valido para este experimento.')}</div>` : `
        <div class="bw-section"><h3>Corte del proximo pago ${e ? '| ' + date(e.date) : ''}</h3>
        ${e ? `<div class="bw-event">${kpi('Antes del corte',fmt(e.before_dirty),'Precio sucio teorico')}${kpi('Pago separado',fmt(e.interest + e.amortization),'Cupon ' + fmt(e.interest) + ' + capital ' + fmt(e.amortization),'bw-up')}${kpi('Despues del corte',fmt(e.after_dirty),'Precio sucio teorico')}</div>
        ${note('Comparacion instantanea a igual TIR y misma fecha: precio antes = precio despues + pago. El patrimonio no cae por cobrar; cambia su composicion entre bono y efectivo. La cotizacion real tambien depende de tasas, riesgo y liquidez.')}
        ${table(['Identidad de patrimonio','Antes','Despues'],[tr(['Bono + efectivo',fmt(e.total_wealth_before),fmt(e.total_wealth_after)])])}` : note('No hay pagos futuros en el calendario.')}
        <h4>Precio limpio, sucio e intereses corridos</h4><div class="bw-chart bw-small-chart"><canvas data-plot="coupon"></canvas></div>
        ${note('Trayectoria teorica; el modelo separa pagos en su fecha contractual y excluye flujos del dia de liquidacion. No reemplaza el aviso de pago ni confirma la fecha ex del mercado.')}</div>
        <div class="bw-grid bw-section"><div><h3>Relacion precio / TIR</h3><div class="bw-chart bw-small-chart"><canvas data-plot="yield"></canvas></div></div><div><h3>Prueba de stress</h3>${this.stressTable(t.stress || [])}${note('El shock mantiene constantes los demas supuestos. No simula simultaneamente cambios de credito, inflacion o liquidez.')}</div></div>
        <div class="bw-section"><h3>Practica sobre ${esc(this.ticker)}</h3>${(t.exercises || []).map((x,i) => `<div class="bw-exercise"><p><b>${i+1}.</b> ${esc(x.question)}</p><details><summary>Ver resolucion</summary><p><b>${esc(x.answer)}</b></p><p>${esc(x.working)}</p></details></div>`).join('')}</div>`}
        <details><summary>Glosario de renta fija</summary><dl class="bw-glossary">${glossary.map(([term,definition]) => `<dt>${esc(term)}</dt><dd>${esc(definition)}</dd>`).join('')}</dl></details>
        <details><summary>Ficha contractual y flujos base</summary>${note('Calendario del catalogo por 100 VN base. En instrumentos indexados, estos importes no son cobros nominales futuros garantizados.')}
        ${table(['Fecha','Renta base','Capital base','Total base'],(this.data.detail.cashflows || []).map(r => tr([date(r.date),fmt(r.interest),fmt(r.amortization),fmt(r.total)])))}</details>
        <p class="bw-note">Referencias: <a href="https://www.finra.org/investors/investing/investment-products/bonds" target="_blank" rel="noopener">FINRA: bonos y riesgos</a> · <a href="https://www.imf.org/external/np/sta/wgsd/pdf/hss.pdf" target="_blank" rel="noopener">FMI: precios y devengamiento</a>. La convencion local del instrumento prevalece.</p>`;
      if (t.supported) {
        this.plot('coupon', (t.timeline || []).map(r => date(r.date)), [
          {label:'Sucio',data:(t.timeline || []).map(r=>r.dirty),borderColor:'#16b9b0'},
          {label:'Limpio',data:(t.timeline || []).map(r=>r.clean),borderColor:'#ddae49'},
          {label:'Intereses corridos (eje derecho)',data:(t.timeline || []).map(r=>r.accrued),borderColor:'#af85db',yAxisID:'accrued'}
        ]);
        this.plot('yield',[],[{label:'Precio / TIR (%)',data:(t.price_yield || []).map(r=>({x:r.yield*100,y:r.price})),borderColor:'#16b9b0'}], 'line', true);
      }
      this.icons();
    }

    async loadHistory() {
      if (this.history) { this.active === 'chart' ? this.renderHistory() : this.renderQuant(); return; }
      if (!this.historyLoading) {
        this.historyLoading = this.request('history','history-analysis').then(data => { this.history = data; }).finally(() => { this.historyLoading = null; });
      }
      const target = this.active;
      this.pane().innerHTML = `<div class="bw-empty" role="status">Consultando cierres diarios de ${esc(this.ticker)}...</div>`;
      try {
        await this.historyLoading;
        if (!this.disposed && this.active === target && this.history) this.renderActive();
      } catch (error) {
        if (error.name !== 'AbortError' && this.active === target) this.pane().innerHTML = `<div class="bw-empty">${esc(error.message)}</div>${command('history-retry','Reintentar','refresh-cw')}`;
        this.icons();
      }
    }

    coverage() {
      const h = this.history;
      return `${date(h.from)} a ${date(h.to)} | ${h.count} cierres | ${Object.entries(h.sources).map(([s,n])=>`${s}: ${n}`).join(', ')} | 24hs`;
    }

    async renderHistory() {
      const generation = this.chartGeneration = (this.chartGeneration || 0) + 1;
      if (this.historyChart) { this.historyChart.remove(); this.historyChart = null; }
      this.resizeObserver?.disconnect();
      const h = this.history;
      if (!h.bars.length) { this.pane().innerHTML = `<div class="bw-empty">Sin historico disponible para esta especie.</div>${notes(h.warnings)}${command('history-retry','Reintentar','refresh-cw')}`; this.icons(); return; }
      this.pane().innerHTML = `<div class="bw-toolbar"><div class="bw-segment" aria-label="Rango historico">${[[30,'1M'],[90,'3M'],[365,'1A'],[1096,'3A']].map(([days,label])=>`<button type="button" data-range="${days}" aria-pressed="${this.range===days}">${label}</button>`).join('')}</div>
        <div class="bw-segment" aria-label="Tipo de grafico"><button type="button" data-chart-mode="line" title="Cierres" aria-pressed="${this.historyMode==='line'}">${icon('chart-line')}</button><button type="button" data-chart-mode="candles" title="Velas OHLC disponibles" aria-pressed="${this.historyMode==='candles'}" ${h.ohlc_count ? '' : 'disabled'}>${icon('chart-candlestick')}</button></div>
        <label><input type="checkbox" data-chart-log ${this.logScale ? 'checked' : ''}>Log</label><label><input type="checkbox" data-chart-volume ${this.showVolume ? 'checked' : ''} ${h.volume_count ? '' : 'disabled'}>Volumen</label>
        <span class="bw-spacer"></span><button type="button" class="bw-icon" data-action="fit" title="Ajustar vista" aria-label="Ajustar vista">${icon('maximize')}</button>${command('history-csv','CSV','download')}</div>
        <div class="bw-chart-legend" data-slot="crosshair">${esc(this.coverage())}</div><div class="bw-chart bw-history-chart" data-history-chart></div>
        ${note(h.methodology)}${note(`Ventana solicitada: ${date(h.requested_from)} a ${date(h.requested_to)}. ${h.ohlc_count} ruedas con OHLC; no se completan velas con valores ficticios.`)}${notes(h.warnings)}
        <p class="bw-note"><a href="https://www.tradingview.com/" target="_blank" rel="noopener">TradingView Lightweight Charts</a> 5.2.1</p>`;
      this.icons();
      try {
        const lib = await chartLibrary();
        const container = this.pane('chart').querySelector('[data-history-chart]');
        if (this.disposed || generation !== this.chartGeneration || this.active !== 'chart' || !container) return;
        const style = getComputedStyle(this.root);
        this.historyChart = lib.createChart(container, {width:container.clientWidth,height:container.clientHeight,
          layout:{background:{type:'solid',color:style.getPropertyValue('--panel-bg').trim()},textColor:style.getPropertyValue('--text-dim').trim(),fontFamily:'Arial',fontSize:11,attributionLogo:true},
          grid:{vertLines:{color:style.getPropertyValue('--panel-border').trim()},horzLines:{color:style.getPropertyValue('--panel-border').trim()}},
          rightPriceScale:{mode:this.logScale ? lib.PriceScaleMode.Logarithmic : lib.PriceScaleMode.Normal},
          timeScale:{borderVisible:false,timeVisible:false},crosshair:{mode:lib.CrosshairMode.Normal}});
        this.historySeries = this.historyChart.addSeries(this.historyMode === 'candles' ? lib.CandlestickSeries : lib.LineSeries,
          this.historyMode === 'candles' ? {upColor:'#20b899',downColor:'#e6747a',borderVisible:false,wickUpColor:'#20b899',wickDownColor:'#e6747a'} : {color:'#16b9b0',lineWidth:2});
        this.historySeries.setData(h.bars.map(b=>this.historyMode === 'candles' ? ('open' in b ? {time:b.time,open:b.open,high:b.high,low:b.low,close:b.close} : {time:b.time}) : {time:b.time,value:b.value}));
        if (this.showVolume && h.volume_count) {
          const volume = this.historyChart.addSeries(lib.HistogramSeries,{priceFormat:{type:'volume'},priceScaleId:'volume',color:'#6a889480',lastValueVisible:false,priceLineVisible:false});
          volume.priceScale().applyOptions({scaleMargins:{top:.82,bottom:0}});
          volume.setData(h.bars.filter(b=>finite(b.volume)).map(b=>({time:b.time,value:b.volume,color:'#6a889480'})));
        }
        this.historyChart.subscribeCrosshairMove(param=>{
          const bar = param.seriesData.get(this.historySeries);
          const readout = this.slot('crosshair');
          if (readout) readout.textContent = bar ? `${typeof bar.time === 'string' ? date(bar.time) : ''} | ${'open' in bar ? `O ${fmt(bar.open)} H ${fmt(bar.high)} L ${fmt(bar.low)} C ${fmt(bar.close)}` : `Cierre ${fmt(bar.value)}`}` : this.coverage();
        });
        this.resizeObserver = new ResizeObserver(()=>{ if(this.historyChart && container.clientWidth > 0) this.historyChart.resize(container.clientWidth,container.clientHeight); });
        this.resizeObserver.observe(container);
        this.setRange();
      } catch (error) { if (!this.disposed) this.status(error.message); }
    }

    setRange() {
      if (!this.historyChart || !this.history?.to) return;
      const end = new Date(this.history.to + 'T12:00:00Z');
      const start = new Date(end); start.setUTCDate(start.getUTCDate() - this.range);
      const from = start.toISOString().slice(0,10) < this.history.from ? this.history.from : start.toISOString().slice(0,10);
      this.historyChart.timeScale().setVisibleRange({from,to:this.history.to});
      this.pane('chart').querySelectorAll('[data-range]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.range)===this.range)));
    }

    renderQuant() {
      const h = this.history, q = h.quant;
      const m = this.data.detail.metrics || {}, t = this.data.trading || {};
      this.pane().innerHTML = `<div class="bw-toolbar"><h3>${icon('chart-scatter')}Distribucion y riesgo observado</h3><span class="bw-spacer"></span>${command('history-csv','Serie CSV','download')}</div>${note(this.coverage())}
        <div class="bw-stats bw-section">${kpi('Retorno de precio',percent(q.price_return_pct),'No incluye cupones',tone(q.price_return_pct))}${kpi('Volatilidad anualizada',percent(q.annual_vol_pct),'252 observaciones / ano')}${kpi('Drawdown maximo',percent(q.max_drawdown_pct),'Precio sin ajustar','bw-down')}${kpi('VaR historico 95%',percent(q.var95_pct),'Perdida por observacion')}${kpi('CVaR historico 95%',percent(q.cvar95_pct),'Media de la cola')}${kpi('Mejor observacion',percent(q.best_day_pct),'','bw-up')}${kpi('Peor observacion',percent(q.worst_day_pct),'','bw-down')}${kpi('Observaciones',fmt(q.observations,0))}</div>
        <div class="bw-grid bw-section"><div><h3>Volatilidad movil (20 observaciones)</h3><div class="bw-chart bw-small-chart"><canvas data-plot="vol"></canvas></div></div><div><h3>Caida desde el maximo</h3><div class="bw-chart bw-small-chart"><canvas data-plot="drawdown"></canvas></div></div></div>
        <div class="bw-grid bw-section"><div><h3>Distribucion de retornos de precio</h3><div class="bw-chart bw-small-chart"><canvas data-plot="distribution"></canvas></div></div><div><h3>Correlacion y beta</h3><form class="bw-form" data-form="compare"><label>Referencia<select name="compare"><option value="">Seleccionar bono</option>${(this.data.peers || []).map(p=>`<option value="${esc(p.ticker)}">${esc(p.ticker)}</option>`).join('')}</select></label>${this.submitButton('Comparar')}</form><div data-slot="comparison">${note('Retornos de precio sobre fechas comunes. Minimo 20 observaciones; no ajusta cupones ni diferencias de duration.')}</div></div></div>
        ${note(q.methodology || 'No hay suficientes observaciones para calcular estadisticas.')}
        <details><summary>Riesgo de tasa del instrumento</summary><div class="bw-stats">${kpi('DV01 por 100 VN',fmt(t.dv01_per100,4),this.currency)}${kpi('Convexidad numerica',fmt(t.convexity),'Repricing del motor +/- 1 pb')}${kpi('Duration numerica',fmt(t.modified_duration),'Sensibilidad local del precio')}${kpi('Intereses corridos base',fmt(m.accrued_interest,4),'Unidad contractual del motor')}</div>${this.stressTable()}</details>
        ${(q.large_moves || []).length ? `<details><summary>Control de calidad: ${q.large_moves.length} saltos mayores al 20%</summary>${note('Observaciones conservadas, no depuradas automaticamente. Revisar corte de pagos, unidades, fuente y cotizaciones aisladas antes de usar VaR o volatilidad para decidir una operacion.')}${table(['Desde','Hasta','Cambio precio'],q.large_moves.map(r=>tr([date(r.from),date(r.time),percent(r.value)])))}</details>` : ''}
        <details data-api-details><summary>Explorador de la API Open BYMADATA</summary><div class="bw-toolbar">${command('api-load','Consultar campos','database')}${command('api-json','JSON','download')}</div><div data-slot="api">${note('Endpoint publico de mercado; valores crudos y campos ausentes de la especie/plazo seleccionado.')}</div></details>
        <details><summary>Solicitud y cobertura del historico</summary><pre>${esc(JSON.stringify({endpoint:h.endpoint,params:h.request,coverage:{from:h.from,to:h.to,sources:h.sources},fetched_at:h.fetched_at},null,2))}</pre></details>`;
      this.plot('vol',(q.volatility || []).map(r=>date(r.time)),[{label:'Volatilidad anual %',data:(q.volatility || []).map(r=>r.value),borderColor:'#dbae49'}]);
      this.plot('drawdown',(q.drawdown || []).map(r=>date(r.time)),[{label:'Drawdown %',data:(q.drawdown || []).map(r=>r.value),borderColor:'#e6747a',backgroundColor:'#e6747a18',fill:true}]);
      this.plot('distribution',(q.histogram || []).map(r=>`${fmt(r.from,1)} a ${fmt(r.to,1)}%`),[{label:'Observaciones',data:(q.histogram || []).map(r=>r.count),backgroundColor:'#16b9b0'}],'bar');
      if (this.raw) this.renderRaw();
      this.icons();
    }

    plot(name, labels, datasets, type = 'line', numericX = false) {
      this.plots.get(name)?.destroy();
      const canvas = this.root.querySelector(`[data-plot="${name}"]`);
      if (!canvas || !window.Chart) return;
      const style = getComputedStyle(this.root), text = style.getPropertyValue('--text-dim').trim(), border = style.getPropertyValue('--panel-border').trim();
      this.plots.set(name, new Chart(canvas, {
        type,
        data: {labels, datasets: datasets.map(d => ({pointRadius:0, pointHitRadius:10, borderWidth:2, tension:0, ...d}))},
        options: {
          responsive:true, maintainAspectRatio:false, animation:false,
          interaction:{intersect:false, mode:'index'},
          plugins:{legend:{labels:{color:text, boxWidth:12, font:{size:10}}}},
          scales:{
            x:{type:numericX ? 'linear' : 'category', ticks:{color:text, maxTicksLimit:6, font:{size:10}}, grid:{display:false}},
            y:{ticks:{color:text, font:{size:10}}, grid:{color:border}},
            ...(datasets.some(d=>d.yAxisID === 'accrued') ? {accrued:{position:'right',ticks:{color:'#af85db',font:{size:10}},grid:{drawOnChartArea:false}}} : {})
          }
        }
      }));
    }

    async loadRaw() {
      const slot = this.slot('api');
      if (slot) slot.textContent = 'Consultando Open BYMADATA...';
      try {
        this.raw = await this.request('raw',`api-fields?lag=${this.lag}`);
        if (this.raw) this.renderRaw();
      } catch (error) { if (error.name !== 'AbortError') this.status(error.message); }
    }
    renderRaw() {
      const slot = this.slot('api'), r = this.raw;
      if (!slot || !r) return;
      slot.innerHTML = note(r.message) + note(`${r.method} ${r.endpoint} | ${r.fetched_at}`) + table(['Campo','Valor recibido','Unidad','Significado'],r.fields.map(f=>tr([esc(f.field),`<span class="bw-left">${esc(typeof f.value === 'object' ? JSON.stringify(f.value) : f.value ?? 'No disponible')}</span>`,esc(f.unit),`<span class="bw-left">${esc(f.description)}</span>`]))) + `<details><summary>Respuesta y solicitudes</summary><pre>${esc(JSON.stringify(r,null,2))}</pre></details>`;
    }

    async refresh(explicit = true) {
      if (this.controllers.has('workbench') && !explicit) return;
      const requestLag = this.pendingLag ?? this.lag;
      const generation = this.refreshGeneration = (this.refreshGeneration || 0) + 1;
      if (explicit) this.status('Calculando...');
      try {
        const data = await this.request('workbench',`workbench?lag=${requestLag}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(this.params)});
        if (!data || generation !== this.refreshGeneration) return;
        this.lag = requestLag;
        this.pendingLag = null;
        this.data = data;
        this.renderHeader();
        this.renderActive();
        if (explicit) this.dirty = Object.keys(this.drafts).length > 0;
        this.status();
      } catch (error) {
        if (error.name !== 'AbortError' && generation === this.refreshGeneration) {
          this.pendingLag = null;
          this.renderHeader();
          this.status(error.message);
        }
      }
    }

    async submit(event) {
      const form = event.target.closest('form[data-form]');
      if (!form) return;
      event.preventDefault();
      if (!form.reportValidity()) return;
      if (form.dataset.form === 'compare') {
        const symbol = new FormData(form).get('compare');
        if (!symbol) return;
        this.slot('comparison').textContent = 'Calculando sobre fechas comunes...';
        try {
          const result = await this.request('compare','history-analysis?compare=' + encodeURIComponent(symbol));
          if (result && this.slot('comparison')) {
            const c = result.comparison;
            this.slot('comparison').innerHTML = `<div class="bw-stats">${kpi('Correlacion',fmt(c.correlation,3))}${kpi('Beta',fmt(c.beta,3))}${kpi('Fechas comunes',fmt(c.observations,0))}</div>${note(`${date(c.from)} a ${date(c.to)}`)}`;
          }
        } catch(error) { if(error.name !== 'AbortError') this.status(error.message); }
        return;
      }
      for (const [key,value] of new FormData(form)) {
        if (value === '') delete this.params[key]; else this.params[key] = Number(value);
        delete this.drafts[key];
      }
      this.refresh();
    }

    rememberInput(event) {
      const input = event.target;
      if (input.name && input.closest('form') && input.name !== 'compare') {
        this.dirty = true;
        this.drafts[input.name] = input.value;
        if (input.name === 'price' || input.name === 'yield_pct') {
          const other = input.name === 'price' ? 'yield_pct' : 'price';
          delete this.params[other];
          this.drafts[other] = '';
          this.root.querySelectorAll(`input[name="${other}"]`).forEach(el=>{el.value='';});
        }
      }
    }

    change(event) {
      const input = event.target;
      if (input.matches('[data-chart-log]')) { this.logScale = input.checked; this.renderHistory(); }
      if (input.matches('[data-chart-volume]')) { this.showVolume = input.checked; this.renderHistory(); }
    }

    click(event) {
      const button = event.target.closest('button');
      if (!button || !this.root.contains(button)) return;
      if (button.dataset.tab) { this.activate(button.dataset.tab); return; }
      if (button.hasAttribute('data-lag')) {
        this.pendingLag = Number(button.dataset.lag);
        this.controllers.get('raw')?.abort();
        this.raw = null;
        this.refresh();
        return;
      }
      if (button.dataset.range) { this.range = Number(button.dataset.range); this.setRange(); return; }
      if (button.dataset.chartMode) { this.historyMode = button.dataset.chartMode; this.renderHistory(); return; }
      if (button.dataset.peer) { window.htmx.ajax('GET',`/bond/${encodeURIComponent(button.dataset.peer)}/detail?lag=${this.lag}`,{target:'#modal',swap:'innerHTML'}); return; }
      switch (button.dataset.action) {
        case 'close': this.close(); break;
        case 'refresh': this.refresh(); break;
        case 'reset': delete this.params.price; delete this.params.yield_pct; delete this.drafts.price; delete this.drafts.yield_pct; delete this.drafts.shock_bps; this.params.shock_bps = 100; this.refresh(); break;
        case 'print': window.print(); break;
        case 'fit': this.historyChart?.timeScale().fitContent(); break;
        case 'history-retry': this.history = null; this.loadHistory(); break;
        case 'history-csv': this.download(`${this.ticker}-historico.csv`,this.csv(this.history?.bars || []),'text/csv'); break;
        case 'flows-csv': {
          const w = this.data.wealth;
          const rows = w?.supported ? [{date:this.data.detail.settle_date,interest:0,amortization:0,sale:0,gross:-w.gross_outlay,fee:w.entry_fee,net:-w.initial_outlay},...w.cashflows] : [];
          this.download(`${this.ticker}-flujos.csv`,this.csv(rows),'text/csv'); break;
        }
        case 'api-load': this.loadRaw(); break;
        case 'api-json': if (this.raw) this.download(`${this.ticker}-byma.json`,JSON.stringify(this.raw,null,2),'application/json'); else this.status('Consultar primero los campos de la API.'); break;
      }
    }
    key(event) {
      const tab = event.target.closest('[data-tab]');
      if (!tab || !['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
      event.preventDefault();
      const tabs = [...this.root.querySelectorAll('[data-tab]')], i = tabs.indexOf(tab);
      const next = event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs.at(-1) : tabs[(i + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length];
      next.focus(); this.activate(next.dataset.tab);
    }
    csv(rows) {
      if (!rows.length) return '';
      const fields = [...new Set(rows.flatMap(Object.keys))];
      const cell = x => finite(x) ? String(x) : '"' + String(x ?? '').replace(/^[=+@-]/,'\t$&').replace(/"/g,'""') + '"';
      return [fields.map(cell).join(','),...rows.map(r=>fields.map(f=>cell(r[f])).join(','))].join('\r\n');
    }
    download(filename, content, type) {
      const url = URL.createObjectURL(new Blob([content],{type}));
      const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
  }

  function mount() {
    const root = document.querySelector('#modal .bw');
    if (current?.root === root && !current.disposed) return;
    current?.dispose(); current = null;
    if (root) {
      try { current = new Workbench(root); }
      catch(error) { const status = root.querySelector('[data-slot="status"]'); if (status) {status.hidden=false;status.textContent='No se pudo iniciar el analisis.';} console.error(error); }
    }
  }
  function init() {
    const modal = document.getElementById('modal');
    if (modal) new MutationObserver(mount).observe(modal,{childList:true});
    mount();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',init,{once:true}); else init();
})();
