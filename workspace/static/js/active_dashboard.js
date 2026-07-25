/**
 * V.16 + VI — Dashboard Activo
 * =============================
 * Panel 8 del Workspace: estado en tiempo real del sistema autónomo completo.
 * Sección 13 del Roadmap V + Roadmap VI Data Intelligence.
 *
 * Polling cada 10s al endpoint /api/roadmap6/status (agrega todo VI).
 * Polling adicional a /api/sentinel/status, /api/scheduler/tasks,
 * /api/signals/active, /api/datasets/status.
 *
 * Endpoints V:
 *   GET  /api/sentinel/status       — Market Sentinel
 *   GET  /api/scheduler/tasks       — Scheduler
 *   GET  /api/signals/active        — Señales activas
 *   GET  /api/datasets/status       — Datasets CSV
 *   POST /api/sentinel/add          — Añadir par
 *   POST /api/sentinel/remove       — Quitar par
 *   POST /api/scheduler/pause       — Pausar
 *   POST /api/scheduler/resume      — Reanudar
 *   POST /api/datasets/force_update — Actualización forzada
 *   POST /api/retrain/force         — Reentrenamiento forzado
 *
 * Endpoints VI:
 *   GET  /api/roadmap6/status            — Estado completo VI
 *   POST /api/roadmap6/self_test         — Self-test diagnóstico
 *   POST /api/roadmap6/sentinel/scan     — Escaneo forzado
 *   GET  /api/roadmap6/opportunity_ranking — Ranking de oportunidades
 */

function _adEsc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

const ActiveDashboard = {
  pollInterval: 15000,
  pollTimer: null,
  vi6PollTimer: null,
  state: {
    sentinel: null,
    scheduler: null,
    signals: [],
    datasets: [],
    roadmap6: null,
  },

  init(containerId = "active-dashboard") {
    const container = document.getElementById(containerId);
    if (!container) return;
    this.render(container);
    this.startPolling();
  },

  render(container) {
    container.innerHTML = `
      <!-- ═══ SECCIÓN V — Market Sentinel + Scheduler + Señales + Datasets ═══ -->
      <div class="dashboard-section">
        <div class="dashboard-header">
          <h2>Dashboard Activo — Sistema Autónomo</h2>
          <div class="dashboard-controls">
            <button id="btn-force-scan" class="btn btn-primary">⟳ Escanear ahora</button>
            <button id="btn-pause-scheduler" class="btn btn-warning">⏸ Pausar Scheduler</button>
            <button id="btn-resume-scheduler" class="btn btn-success" style="display:none">▶ Reanudar Scheduler</button>
          </div>
        </div>

        <div class="dashboard-grid">
          <div class="dashboard-card" id="card-sentinel">
            <div class="card-title">🛡 Market Sentinel</div>
            <div class="card-body" id="sentinel-status"><span class="text-muted">Cargando…</span></div>
          </div>
          <div class="dashboard-card" id="card-scheduler">
            <div class="card-title">⏰ Scheduler</div>
            <div class="card-body" id="scheduler-status"><span class="text-muted">Cargando…</span></div>
          </div>
          <div class="dashboard-card" id="card-signals">
            <div class="card-title">📈 Señales Activas</div>
            <div class="card-body" id="signals-list"><span class="text-muted">Cargando…</span></div>
          </div>
          <div class="dashboard-card" id="card-datasets">
            <div class="card-title">📂 Datasets CSV</div>
            <div class="card-body" id="datasets-status"><span class="text-muted">Cargando…</span></div>
          </div>
        </div>

        <div class="dashboard-section-controls">
          <div class="control-group">
            <label>Añadir par al Sentinel:</label>
            <input type="text" id="input-add-pair" placeholder="EURUSD" style="width:90px" />
            <button id="btn-add-pair" class="btn btn-primary">+ Añadir</button>
            <button id="btn-remove-pair" class="btn btn-secondary">− Quitar</button>
          </div>
          <div class="control-group">
            <label>Forzar actualización CSV:</label>
            <select id="select-update-pair"><option value="">Seleccionar par…</option></select>
            <button id="btn-force-update" class="btn btn-secondary">Actualizar</button>
          </div>
          <div class="control-group">
            <label>Forzar reentrenamiento:</label>
            <select id="select-retrain-pair"><option value="">Seleccionar par…</option></select>
            <button id="btn-force-retrain" class="btn btn-secondary">Reentrenar</button>
          </div>
        </div>
      </div>

      <!-- ═══ SECCIÓN VI — Roadmap VI: Data Intelligence & Autonomía ═══ -->
      <div class="dashboard-section" style="margin-top:1.5rem;">
        <div class="dashboard-header">
          <h2>Roadmap VI — Data Intelligence & Autonomía</h2>
          <div class="dashboard-controls">
            <button id="btn-self-test" class="btn btn-primary">🔬 Self-Test</button>
            <button id="btn-refresh-vi6" class="btn btn-secondary">⟳ Actualizar VI</button>
          </div>
        </div>

        <div class="dashboard-grid" style="grid-template-columns: repeat(3, 1fr);">
          <div class="dashboard-card" id="card-hparam">
            <div class="card-title">🧠 Hyperparameter Cache</div>
            <div class="card-body" id="hparam-status"><span class="text-muted">Cargando…</span></div>
          </div>
          <div class="dashboard-card" id="card-modelcache">
            <div class="card-title">💾 Model Cache</div>
            <div class="card-body" id="modelcache-status"><span class="text-muted">Cargando…</span></div>
          </div>
          <div class="dashboard-card" id="card-rolling">
            <div class="card-title">🔄 Rolling Datasets</div>
            <div class="card-body" id="rolling-status"><span class="text-muted">Cargando…</span></div>
          </div>
        </div>

        <!-- Opportunity Ranking (VI.8.A) -->
        <div class="dashboard-card" style="margin-top:1rem;" id="card-opportunity">
          <div class="card-title">🎯 Opportunity Ranking — Top señales por OpScore</div>
          <div class="card-body" id="opportunity-list"><span class="text-muted">Cargando…</span></div>
        </div>

        <!-- Sentinel scan results (VI — predicciones reales) -->
        <div class="dashboard-card" style="margin-top:1rem;" id="card-scan-results">
          <div class="card-title">📡 Sentinel — Resultados de escaneo</div>
          <div class="card-body" id="scan-results"><span class="text-muted">Sin escaneos ejecutados todavía. Presiona "Escanear ahora".</span></div>
        </div>

        <!-- Self-test output -->
        <div class="dashboard-card" style="margin-top:1rem; display:none;" id="card-self-test">
          <div class="card-title">🔬 Self-Test — Diagnóstico del sistema (VI.2.B)</div>
          <div class="card-body" id="self-test-output"></div>
        </div>

        <!-- Candlestick section -->
        <div class="dashboard-card" style="margin-top:1rem;">
          <div class="card-title">🕯 Patrones de Vela (VI.5.D)</div>
          <div class="card-body">
            <div class="control-group" style="margin-bottom:0.5rem;">
              <label>CSV a analizar:</label>
              <select id="select-candlestick-csv" style="flex:1;"></select>
              <button id="btn-candlestick" class="btn btn-secondary">Detectar patrones</button>
            </div>
            <div id="candlestick-result" class="train-stage-label" style="white-space:pre-wrap;font-size:0.8rem;max-height:200px;overflow-y:auto;"></div>
          </div>
        </div>
      </div>
    `;
    this.attachEvents();
  },

  attachEvents() {
    document.getElementById("btn-pause-scheduler")?.addEventListener("click", () => this.pauseScheduler());
    document.getElementById("btn-resume-scheduler")?.addEventListener("click", () => this.resumeScheduler());
    document.getElementById("btn-add-pair")?.addEventListener("click", () => this.addPair());
    document.getElementById("btn-remove-pair")?.addEventListener("click", () => this.removePair());
    document.getElementById("btn-force-update")?.addEventListener("click", () => this.forceUpdate());
    document.getElementById("btn-force-retrain")?.addEventListener("click", () => this.forceRetrain());
    document.getElementById("btn-force-scan")?.addEventListener("click", () => this.forceSentinelScan());
    document.getElementById("btn-self-test")?.addEventListener("click", () => this.runSelfTest());
    document.getElementById("btn-refresh-vi6")?.addEventListener("click", () => this.fetchRoadmap6());
    document.getElementById("btn-candlestick")?.addEventListener("click", () => this.runCandlestick());
  },

  startPolling() {
    this.fetchAll();
    this.pollTimer = setInterval(() => this.fetchAll(), this.pollInterval);
    // VI: poll cada 30s
    this.vi6PollTimer = setInterval(() => this.fetchRoadmap6(), 30000);
    this.fetchRoadmap6();
    this.populateCandlestickSelect();
  },

  stopPolling() {
    if (this.pollTimer) clearInterval(this.pollTimer);
    if (this.vi6PollTimer) clearInterval(this.vi6PollTimer);
  },

  async fetchAll() {
    await Promise.all([
      this.fetchSentinel(),
      this.fetchScheduler(),
      this.fetchSignals(),
      this.fetchDatasets(),
    ]);
  },

  // ── V: Sentinel ──────────────────────────────────────────────
  async fetchSentinel() {
    try {
      const res = await fetch("/api/sentinel/status");
      const data = await res.json();
      this.state.sentinel = data;
      this.renderSentinel();
    } catch (e) {
      document.getElementById("sentinel-status").innerHTML =
        `<span class="text-error">Error: ${_adEsc(e.message)}</span>`;
    }
  },

  renderSentinel() {
    const s = this.state.sentinel;
    if (!s) return;
    const cbColor = s.circuit_breaker_active ? "text-error" : "text-success";
    const stateColor = s.state === "running" ? "text-success" : s.state === "idle" ? "text-muted" : "text-warning";
    let html = `
      <div class="status-row"><span>Estado:</span> <span class="${stateColor}">${_adEsc(s.state)}</span></div>
      <div class="status-row"><span>Circuit Breaker:</span> <span class="${cbColor}">${s.circuit_breaker_active ? "⚠ ACTIVO" : "✔ OK"}</span></div>
      <div class="status-row"><span>Pares vigilados:</span> <span>${s.assets_monitored}</span></div>
      <div class="status-row"><span>Total scans:</span> <span>${s.total_scans}</span></div>
    `;
    if (s.assets && Object.keys(s.assets).length) {
      html += "<div class='asset-list'>";
      for (const [pair, a] of Object.entries(s.assets)) {
        const sigColor = a.last_signal === "BUY" ? "text-success" :
                         a.last_signal === "SELL" ? "text-error" : "text-muted";
        html += `<div class="asset-row">
          <span class="pair-name">${_adEsc(pair)}</span>
          <span class="${sigColor}">${_adEsc(a.last_signal)}</span>
          <span>R=${a.last_reliability.toFixed(1)}</span>
          <span class="text-muted">scans=${a.scan_count}</span>
        </div>`;
      }
      html += "</div>";
    } else {
      html += `<div class="text-muted" style="margin-top:.5rem;font-size:.78rem;">Sin pares configurados</div>`;
    }
    document.getElementById("sentinel-status").innerHTML = html;
  },

  // ── V: Scheduler ──────────────────────────────────────────────
  async fetchScheduler() {
    try {
      const res = await fetch("/api/scheduler/tasks");
      const data = await res.json();
      this.state.scheduler = data;
      this.renderScheduler();
    } catch (e) {
      document.getElementById("scheduler-status").innerHTML =
        `<span class="text-error">Error: ${_adEsc(e.message)}</span>`;
    }
  },

  renderScheduler() {
    const s = this.state.scheduler;
    if (!s) return;
    const runColor = s.running ? "text-success" : "text-warning";
    let html = `
      <div class="status-row"><span>Estado:</span> <span class="${runColor}">${s.running ? "▶ Activo" : "⏸ Pausado"}</span></div>
      <div class="status-row"><span>Tareas:</span> <span>${s.task_count}</span></div>
    `;
    if (s.tasks && Object.keys(s.tasks).length) {
      html += "<div class='task-list'>";
      for (const [name, t] of Object.entries(s.tasks)) {
        const icon = t.last_status === "success" ? "✓" : t.last_status === "failed" ? "✗" : "○";
        html += `<div class="task-row">
          <span>${icon}</span>
          <span class="task-name">${_adEsc(name)}</span>
          <span class="text-muted">${t.interval_sec}s</span>
          <span class="text-muted">runs=${t.run_count}</span>
        </div>`;
      }
      html += "</div>";
    } else {
      html += `<div class="text-muted" style="margin-top:.5rem;font-size:.78rem;">Scheduler listo — sin tareas programadas actualmente</div>`;
    }
    document.getElementById("scheduler-status").innerHTML = html;

    const pauseBtn = document.getElementById("btn-pause-scheduler");
    const resumeBtn = document.getElementById("btn-resume-scheduler");
    if (s.running) {
      if (pauseBtn) pauseBtn.style.display = "";
      if (resumeBtn) resumeBtn.style.display = "none";
    } else {
      if (pauseBtn) pauseBtn.style.display = "none";
      if (resumeBtn) resumeBtn.style.display = "";
    }
  },

  // ── V: Signals ────────────────────────────────────────────────
  async fetchSignals() {
    try {
      const res = await fetch("/api/signals/active");
      const data = await res.json();
      this.state.signals = data.signals || [];
      this.renderSignals();
    } catch (e) {
      document.getElementById("signals-list").innerHTML =
        `<span class="text-error">Error: ${_adEsc(e.message)}</span>`;
    }
  },

  renderSignals() {
    const signals = this.state.signals;
    if (!signals.length) {
      document.getElementById("signals-list").innerHTML =
        `<span class="text-muted">Sin señales activas (Reliability < 50)</span>`;
      return;
    }
    let html = "<div class='signal-list'>";
    for (const s of signals.slice(0, 10)) {
      const sigColor = s.signal === "BUY" ? "text-success" :
                       s.signal === "SELL" ? "text-error" : "text-muted";
      const relColor = s.reliability_score >= 85 ? "text-success" :
                       s.reliability_score >= 70 ? "text-warning" : "text-muted";
      html += `<div class="signal-row">
        <span class="pair-name">${_adEsc(s.pair)}</span>
        <span class="${sigColor}">${_adEsc(s.signal)}</span>
        <span class="${relColor}">R=${s.reliability_score.toFixed(1)}</span>
        <span class="text-muted">${_adEsc(s.regime || "")}</span>
      </div>`;
    }
    html += "</div>";
    document.getElementById("signals-list").innerHTML = html;
  },

  // ── V: Datasets ───────────────────────────────────────────────
  async fetchDatasets() {
    try {
      const res = await fetch("/api/datasets/status");
      const data = await res.json();
      this.state.datasets = data.datasets || [];
      this.renderDatasets();
    } catch (e) {
      document.getElementById("datasets-status").innerHTML =
        `<span class="text-error">Error: ${_adEsc(e.message)}</span>`;
    }
  },

  renderDatasets() {
    const datasets = this.state.datasets;
    if (!datasets.length) {
      document.getElementById("datasets-status").innerHTML =
        `<span class="text-muted">Sin datasets configurados</span>`;
      return;
    }
    let html = "<div class='dataset-list'>";
    for (const d of datasets) {
      const ageColor = d.age_hours < 2 ? "text-success" :
                       d.age_hours < 24 ? "text-warning" : "text-error";
      html += `<div class="dataset-row">
        <span class="pair-name">${_adEsc(d.pair)} ${_adEsc(d.timeframe)}</span>
        <span class="text-muted">rows: ${d.rows.toLocaleString()}</span>
        <span class="${ageColor}">${d.age_hours.toFixed(1)}h</span>
      </div>`;
    }
    html += "</div>";
    document.getElementById("datasets-status").innerHTML = html;

    const updateSel = document.getElementById("select-update-pair");
    const retrainSel = document.getElementById("select-retrain-pair");
    const opts = datasets.map(d =>
      `<option value="${_adEsc(d.pair)}_${_adEsc(d.timeframe)}">${d.pair} ${d.timeframe}</option>`
    ).join("");
    if (updateSel) updateSel.innerHTML = `<option value="">Seleccionar par…</option>${opts}`;
    if (retrainSel) retrainSel.innerHTML = `<option value="">Seleccionar par…</option>${opts}`;
  },

  // ── VI: Roadmap VI status ────────────────────────────────────
  async fetchRoadmap6() {
    try {
      const res = await fetch("/api/roadmap6/status");
      const data = await res.json();
      this.state.roadmap6 = data;
      this.renderHparamCache(data.hparam_cache);
      this.renderModelCache(data.model_cache);
      this.renderRollingDatasets(data.rolling_datasets);
      this.renderOpportunityRanking(data.opportunity_ranking);
      this.renderScanResults(data.sentinel);
    } catch (e) {
      console.error("fetchRoadmap6:", e);
    }
  },

  renderHparamCache(d) {
    const el = document.getElementById("hparam-status");
    if (!d) return;
    if (!d.ok) {
      el.innerHTML = `<span class="text-error">Error: ${_adEsc(d.error)}</span>`;
      return;
    }
    let html = `<div class="status-row"><span>Entradas:</span> <span class="text-success">${d.total}</span></div>`;
    if (d.entries && d.entries.length) {
      html += "<div class='task-list' style='margin-top:.4rem;'>";
      for (const e of d.entries) {
        html += `<div class="task-row">
          <span class="pair-name">${_adEsc(e.pair)}/${_adEsc(e.horizon)}</span>
          <span class="text-success">acc=${e.accuracy}%</span>
          <span class="text-muted">trials=${e.trials}</span>
        </div>`;
      }
      html += "</div>";
    } else {
      html += `<div class="text-muted" style="font-size:.78rem;">Sin entradas en caché todavía</div>`;
    }
    el.innerHTML = html;
  },

  renderModelCache(d) {
    const el = document.getElementById("modelcache-status");
    if (!d) return;
    if (!d.ok) {
      el.innerHTML = `<span class="text-error">Error: ${_adEsc(d.error)}</span>`;
      return;
    }
    let html = `<div class="status-row"><span>Modelos:</span> <span class="text-success">${d.total}</span></div>`;
    if (d.entries && d.entries.length) {
      html += "<div class='task-list' style='margin-top:.4rem;'>";
      for (const e of d.entries) {
        html += `<div class="task-row">
          <span class="pair-name">${_adEsc(e.pair)}/${_adEsc(e.horizon)}</span>
          <span class="text-success">acc=${e.accuracy}%</span>
          <span class="text-muted">rows=${e.rows}</span>
        </div>`;
      }
      html += "</div>";
    } else {
      html += `<div class="text-muted" style="font-size:.78rem;">Sin modelos en caché todavía</div>`;
    }
    el.innerHTML = html;
  },

  renderRollingDatasets(d) {
    const el = document.getElementById("rolling-status");
    if (!d) return;
    if (!d.ok) {
      el.innerHTML = `<span class="text-error">Error: ${_adEsc(d.error)}</span>`;
      return;
    }
    if (!d.datasets || !d.datasets.length) {
      el.innerHTML = `<span class="text-muted">Sin rolling datasets disponibles</span>`;
      return;
    }
    let html = `<div class="status-row"><span>Datasets:</span> <span>${d.total}</span></div><div class='dataset-list' style='margin-top:.4rem;'>`;
    for (const ds of d.datasets) {
      const validColor = ds.valid ? "text-success" : "text-warning";
      const errTxt = ds.errors && ds.errors.length ? ` ⚠ ${_adEsc(ds.errors[0])}` : "";
      html += `<div class="dataset-row">
        <span class="pair-name">${_adEsc(ds.pair)} ${_adEsc(ds.timeframe)}</span>
        <span class="text-muted">rows=${ds.rows.toLocaleString()}</span>
        <span class="${validColor}">${ds.valid ? "✔" : "⚠"}${errTxt}</span>
      </div>`;
    }
    html += "</div>";
    el.innerHTML = html;
  },

  renderOpportunityRanking(d) {
    const el = document.getElementById("opportunity-list");
    if (!d) return;
    if (!d.ok) {
      el.innerHTML = `<span class="text-error">Error: ${_adEsc(d.error)}</span>`;
      return;
    }
    if (!d.opportunities || !d.opportunities.length) {
      el.innerHTML = `<span class="text-muted">Sin oportunidades activas en este momento (se generan cuando haya señales con Reliability ≥ 70).<br>
        <button id="btn-manual-rank" class="btn btn-secondary" style="margin-top:.5rem;">🔄 Solicitar ranking ahora</button></span>`;
      document.getElementById("btn-manual-rank")?.addEventListener("click", () => this.fetchManualRanking());
      return;
    }
    let html = "<div class='signal-list'>";
    for (const op of d.opportunities) {
      const sigColor = op.signal === "BUY" ? "text-success" :
                       op.signal === "SELL" ? "text-error" : "text-muted";
      const scoreColor = op.score >= 80 ? "text-success" : op.score >= 60 ? "text-warning" : "text-muted";
      html += `<div class="signal-row">
        <span class="pair-name">${_adEsc(op.pair)}</span>
        <span class="${sigColor}">${_adEsc(op.signal)}</span>
        <span class="${scoreColor}">OpScore=${op.score}</span>
        <span class="text-muted">${_adEsc(op.regime || "")}</span>
      </div>`;
    }
    html += "</div>";
    el.innerHTML = html;
  },

  async fetchManualRanking() {
    const el = document.getElementById("opportunity-list");
    el.innerHTML = `<span class="text-muted">Consultando ranking…</span>`;
    try {
      const res = await fetch("/api/roadmap6/opportunity_ranking?n=10");
      const d = await res.json();
      el.innerHTML = `<pre style="font-size:.75rem;white-space:pre-wrap;max-height:200px;overflow-y:auto;">${_adEsc(d.text || d.error || "Sin datos")}</pre>`;
    } catch (e) {
      el.innerHTML = `<span class="text-error">Error: ${_adEsc(e.message)}</span>`;
    }
  },

  renderScanResults(sentinel) {
    const el = document.getElementById("scan-results");
    if (!sentinel) return;
    const results = sentinel.scan_results || {};
    if (!Object.keys(results).length) {
      el.innerHTML = `<span class="text-muted">Sin escaneos ejecutados todavía. Presiona "Escanear ahora" para obtener señales reales.</span>`;
      return;
    }
    let html = "<div class='signal-list'>";
    for (const [pair, r] of Object.entries(results)) {
      const sigColor = r.signal === "BUY" ? "text-success" :
                       r.signal === "SELL" ? "text-error" : "text-muted";
      const relColor = r.reliability >= 70 ? "text-success" :
                       r.reliability >= 50 ? "text-warning" : "text-muted";
      const ts = r.timestamp ? r.timestamp.replace("T", " ").slice(0, 16) : "";
      html += `<div class="signal-row">
        <span class="pair-name">${_adEsc(pair)}</span>
        <span class="${sigColor}">${_adEsc(r.signal)}</span>
        <span class="${relColor}">R=${r.reliability.toFixed(1)}</span>
        <span class="text-muted">${_adEsc(ts)}</span>
      </div>`;
    }
    html += "</div>";
    el.innerHTML = html;
  },

  // ── VI: Self-Test ─────────────────────────────────────────────
  async runSelfTest() {
    const btn = document.getElementById("btn-self-test");
    const card = document.getElementById("card-self-test");
    const out = document.getElementById("self-test-output");
    btn.disabled = true;
    btn.textContent = "🔬 Ejecutando…";
    card.style.display = "";
    out.innerHTML = `<span class="text-muted">Ejecutando diagnóstico completo del sistema…</span>`;
    try {
      const res = await fetch("/api/roadmap6/self_test", { method: "POST" });
      const d = await res.json();
      if (!d.ok) {
        out.innerHTML = `<span class="text-error">Error: ${_adEsc(d.error)}</span>`;
        return;
      }
      let html = `<div class="status-row" style="font-weight:600;">${_adEsc(d.summary)}</div>`;
      if (d.errors && d.errors.length) {
        html += `<div style="margin-top:.5rem;"><strong class="text-error">❌ Errores (${d.errors.length})</strong><ul style="margin:.3rem 0 0 1rem;">`;
        d.errors.forEach(e => html += `<li class="text-error" style="font-size:.78rem;">${_adEsc(e)}</li>`);
        html += "</ul></div>";
      }
      if (d.warnings && d.warnings.length) {
        html += `<div style="margin-top:.4rem;"><strong class="text-warning">⚠ Advertencias (${d.warnings.length})</strong><ul style="margin:.3rem 0 0 1rem;">`;
        d.warnings.forEach(w => html += `<li class="text-warning" style="font-size:.78rem;">${_adEsc(w)}</li>`);
        html += "</ul></div>";
      }
      if (d.ok_checks && d.ok_checks.length) {
        html += `<div style="margin-top:.4rem;"><strong class="text-success">✔ OK (${d.ok_checks.length})</strong></div>`;
      }
      out.innerHTML = html;
    } catch (e) {
      out.innerHTML = `<span class="text-error">Error ejecutando self-test: ${_adEsc(e.message)}</span>`;
    } finally {
      btn.disabled = false;
      btn.textContent = "🔬 Self-Test";
    }
  },

  // ── VI: Sentinel scan forzado ─────────────────────────────────
  async forceSentinelScan() {
    const btn = document.getElementById("btn-force-scan");
    btn.disabled = true;
    btn.textContent = "⟳ Escaneando…";
    try {
      await fetch("/api/roadmap6/sentinel/scan", { method: "POST" });
      // El scan corre en background; esperamos 8s y refrescamos
      await new Promise(r => setTimeout(r, 8000));
      await Promise.all([this.fetchSentinel(), this.fetchRoadmap6()]);
    } catch (e) {
      console.error("forceScan:", e);
    } finally {
      btn.disabled = false;
      btn.textContent = "⟳ Escanear ahora";
    }
  },

  // ── VI: Candlestick patterns ──────────────────────────────────
  async populateCandlestickSelect() {
    try {
      // /api/forex/csvs devuelve {timeframe, files} para H1 por defecto
      const res = await fetch("/api/forex/csvs");
      const data = await res.json();
      const sel = document.getElementById("select-candlestick-csv");
      if (!sel) return;
      const opts = [];
      const files = data.files || [];
      const tf = data.timeframe || "H1";
      for (const f of files) {
        if (f.path && !f.name.includes("TESTPAIR") && !f.name.startsWith("TPAIR")) {
          opts.push(`<option value="${_adEsc(f.path)}">${f.name.replace(".csv","")} ${tf}</option>`);
        }
      }
      sel.innerHTML = `<option value="">Seleccionar CSV…</option>${opts.join("")}`;
    } catch (e) { console.error("populateCandlestickSelect:", e); }
  },

  async runCandlestick() {
    const sel = document.getElementById("select-candlestick-csv");
    const out = document.getElementById("candlestick-result");
    const btn = document.getElementById("btn-candlestick");
    if (!sel || !sel.value) { out.textContent = "Selecciona un CSV primero."; return; }
    btn.disabled = true;
    out.textContent = "Analizando patrones de vela…";
    try {
      const res = await fetch("/api/roadmap6/candlestick", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ csv_path: sel.value, pair: "AUTO", timeframe: "H1" }),
      });
      const d = await res.json();
      out.textContent = d.ok ? (d.text || "Sin patrones detectados") : ("Error: " + d.error);
    } catch (e) {
      out.textContent = "Error: " + e.message;
    } finally {
      btn.disabled = false;
    }
  },

  // ── V: Actions ────────────────────────────────────────────────
  async pauseScheduler() {
    await fetch("/api/scheduler/pause", { method: "POST" });
    this.fetchScheduler();
  },

  async resumeScheduler() {
    await fetch("/api/scheduler/resume", { method: "POST" });
    this.fetchScheduler();
  },

  async addPair() {
    const pair = document.getElementById("input-add-pair").value.toUpperCase().trim();
    if (!pair) return;
    await fetch("/api/sentinel/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pair }),
    });
    document.getElementById("input-add-pair").value = "";
    this.fetchSentinel();
  },

  async removePair() {
    const pair = document.getElementById("input-add-pair").value.toUpperCase().trim();
    if (!pair) return;
    await fetch("/api/sentinel/remove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pair }),
    });
    document.getElementById("input-add-pair").value = "";
    this.fetchSentinel();
  },

  async forceUpdate() {
    const val = document.getElementById("select-update-pair").value;
    if (!val) return;
    const [pair, tf] = val.split("_");
    await fetch("/api/datasets/force_update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pair, timeframe: tf }),
    });
    this.fetchDatasets();
  },

  async forceRetrain() {
    const val = document.getElementById("select-retrain-pair").value;
    if (!val) return;
    const [pair, tf] = val.split("_");
    await fetch("/api/retrain/force", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pair, timeframe: tf }),
    });
  },
};

// Auto-init cuando el panel sea visible
if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    const navBtn = document.querySelector('.nav-item[data-section="sentinel"]');
    if (navBtn) {
      let initialized = false;
      navBtn.addEventListener("click", () => {
        if (!initialized) {
          initialized = true;
          if (document.getElementById("active-dashboard")) {
            ActiveDashboard.init("active-dashboard");
          }
        }
      });
    }
  });
}
