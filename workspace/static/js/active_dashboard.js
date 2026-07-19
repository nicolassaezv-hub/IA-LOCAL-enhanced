/**
 * V.16 — Dashboard Activo
 * ========================
 * Seccion 13 del Workspace — estado en tiempo real de todo el sistema autonomo.
 *
 * Polling cada 10s a los endpoints del Sentinel, Scheduler, y Signals.
 *
 * Endpoints requeridos (definir en server.py):
 *   GET /api/sentinel/status      — estado del Market Sentinel
 *   GET /api/scheduler/tasks      — tareas programadas
 *   GET /api/signals/active       — signals activas con reliability >= threshold
 *   GET /api/datasets/status      — ultima actualizacion de cada dataset
 *   POST /api/sentinel/add        — anadir par al sentinel
 *   POST /api/sentinel/remove     — quitar par del sentinel
 *   POST /api/scheduler/pause      — pausar scheduler
 *   POST /api/scheduler/resume     — reanudar scheduler
 *   POST /api/datasets/force_update — forzar actualizacion de dataset
 *   POST /api/retrain/force        — forzar reentrenamiento
 */

const ActiveDashboard = {
  pollInterval: 10000,
  pollTimer: null,
  state: {
    sentinel: null,
    scheduler: null,
    signals: [],
    datasets: [],
  },

  init(containerId = "active-dashboard") {
    const container = document.getElementById(containerId);
    if (!container) return;
    this.render(container);
    this.startPolling();
  },

  render(container) {
    container.innerHTML = `
      <div class="dashboard-section">
        <div class="dashboard-header">
          <h2>Dashboard Activo — Sistema Autonomo</h2>
          <div class="dashboard-controls">
            <button id="btn-pause-scheduler" class="btn btn-warning">Pausar Scheduler</button>
            <button id="btn-resume-scheduler" class="btn btn-success" style="display:none">Reanudar Scheduler</button>
          </div>
        </div>

        <div class="dashboard-grid">
          <div class="dashboard-card" id="card-sentinel">
            <div class="card-title">Market Sentinel</div>
            <div class="card-body" id="sentinel-status">Cargando...</div>
          </div>

          <div class="dashboard-card" id="card-scheduler">
            <div class="card-title">Scheduler</div>
            <div class="card-body" id="scheduler-status">Cargando...</div>
          </div>

          <div class="dashboard-card" id="card-signals">
            <div class="card-title">Signals Activas</div>
            <div class="card-body" id="signals-list">Cargando...</div>
          </div>

          <div class="dashboard-card" id="card-datasets">
            <div class="card-title">Datasets</div>
            <div class="card-body" id="datasets-status">Cargando...</div>
          </div>
        </div>

        <div class="dashboard-section-controls">
          <div class="control-group">
            <label>Anadir par al Sentinel:</label>
            <input type="text" id="input-add-pair" placeholder="EURUSD" />
            <button id="btn-add-pair" class="btn btn-primary">Anadir</button>
          </div>
          <div class="control-group">
            <label>Forzar actualizacion:</label>
            <select id="select-update-pair">
              <option value="">Seleccionar par...</option>
            </select>
            <button id="btn-force-update" class="btn btn-secondary">Actualizar</button>
          </div>
          <div class="control-group">
            <label>Forzar reentrenamiento:</label>
            <select id="select-retrain-pair">
              <option value="">Seleccionar par...</option>
            </select>
            <button id="btn-force-retrain" class="btn btn-secondary">Reentrenar</button>
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
    document.getElementById("btn-force-update")?.addEventListener("click", () => this.forceUpdate());
    document.getElementById("btn-force-retrain")?.addEventListener("click", () => this.forceRetrain());
  },

  startPolling() {
    this.fetchAll();
    this.pollTimer = setInterval(() => this.fetchAll(), this.pollInterval);
  },

  stopPolling() {
    if (this.pollTimer) clearInterval(this.pollTimer);
  },

  async fetchAll() {
    await Promise.all([
      this.fetchSentinel(),
      this.fetchScheduler(),
      this.fetchSignals(),
      this.fetchDatasets(),
    ]);
  },

  async fetchSentinel() {
    try {
      const res = await fetch("/api/sentinel/status");
      const data = await res.json();
      this.state.sentinel = data;
      this.renderSentinel();
    } catch (e) {
      document.getElementById("sentinel-status").innerHTML = `<span class="text-error">Error: ${e.message}</span>`;
    }
  },

  renderSentinel() {
    const s = this.state.sentinel;
    if (!s) return;
    const cbColor = s.circuit_breaker_active ? "text-error" : "text-success";
    const stateColor = s.state === "running" ? "text-success" : "text-warning";
    let html = `
      <div class="status-row"><span>Estado:</span> <span class="${stateColor}">${s.state}</span></div>
      <div class="status-row"><span>Circuit Breaker:</span> <span class="${cbColor}">${s.circuit_breaker_active ? "ACTIVO" : "OK"}</span></div>
      <div class="status-row"><span>Activos vigilados:</span> <span>${s.assets_monitored}</span></div>
      <div class="status-row"><span>Total scans:</span> <span>${s.total_scans}</span></div>
    `;
    if (s.assets) {
      html += "<div class='asset-list'>";
      for (const [pair, a] of Object.entries(s.assets)) {
        const sigColor = a.last_signal === "BUY" ? "text-success" : a.last_signal === "SELL" ? "text-error" : "text-muted";
        html += `<div class="asset-row">
          <span class="pair-name">${pair}</span>
          <span class="${sigColor}">${a.last_signal}</span>
          <span>R=${a.last_reliability.toFixed(1)}</span>
          <span>scans=${a.scan_count}</span>
        </div>`;
      }
      html += "</div>";
    }
    document.getElementById("sentinel-status").innerHTML = html;
  },

  async fetchScheduler() {
    try {
      const res = await fetch("/api/scheduler/tasks");
      const data = await res.json();
      this.state.scheduler = data;
      this.renderScheduler();
    } catch (e) {
      document.getElementById("scheduler-status").innerHTML = `<span class="text-error">Error: ${e.message}</span>`;
    }
  },

  renderScheduler() {
    const s = this.state.scheduler;
    if (!s) return;
    let html = `
      <div class="status-row"><span>Running:</span> <span class="${s.running ? "text-success" : "text-warning"}">${s.running}</span></div>
      <div class="status-row"><span>Tasks:</span> <span>${s.task_count}</span></div>
    `;
    if (s.tasks) {
      html += "<div class='task-list'>";
      for (const [name, t] of Object.entries(s.tasks)) {
        const statusIcon = t.last_status === "success" ? "✓" : t.last_status === "failed" ? "✗" : "○";
        html += `<div class="task-row">
          <span>${statusIcon}</span>
          <span class="task-name">${name}</span>
          <span>${t.interval_sec}s</span>
          <span>runs=${t.run_count}</span>
        </div>`;
      }
      html += "</div>";
    }
    document.getElementById("scheduler-status").innerHTML = html;

    const pauseBtn = document.getElementById("btn-pause-scheduler");
    const resumeBtn = document.getElementById("btn-resume-scheduler");
    if (s.running) {
      pauseBtn.style.display = "";
      resumeBtn.style.display = "none";
    } else {
      pauseBtn.style.display = "none";
      resumeBtn.style.display = "";
    }
  },

  async fetchSignals() {
    try {
      const res = await fetch("/api/signals/active");
      const data = await res.json();
      this.state.signals = data.signals || [];
      this.renderSignals();
    } catch (e) {
      document.getElementById("signals-list").innerHTML = `<span class="text-error">Error: ${e.message}</span>`;
    }
  },

  renderSignals() {
    const signals = this.state.signals;
    if (!signals.length) {
      document.getElementById("signals-list").innerHTML = "<span class='text-muted'>No hay signals activas</span>";
      return;
    }
    let html = "<div class='signal-list'>";
    for (const s of signals.slice(0, 10)) {
      const sigColor = s.signal === "BUY" ? "text-success" : s.signal === "SELL" ? "text-error" : "text-muted";
      const relColor = s.reliability_score >= 85 ? "text-success" : s.reliability_score >= 70 ? "text-warning" : "text-muted";
      html += `<div class="signal-row">
        <span class="pair-name">${s.pair}</span>
        <span class="${sigColor}">${s.signal}</span>
        <span class="${relColor}">R=${s.reliability_score.toFixed(1)}</span>
        <span>${s.regime || ""}</span>
      </div>`;
    }
    html += "</div>";
    document.getElementById("signals-list").innerHTML = html;
  },

  async fetchDatasets() {
    try {
      const res = await fetch("/api/datasets/status");
      const data = await res.json();
      this.state.datasets = data.datasets || [];
      this.renderDatasets();
    } catch (e) {
      document.getElementById("datasets-status").innerHTML = `<span class="text-error">Error: ${e.message}</span>`;
    }
  },

  renderDatasets() {
    const datasets = this.state.datasets;
    if (!datasets.length) {
      document.getElementById("datasets-status").innerHTML = "<span class='text-muted'>Sin datasets configurados</span>";
      return;
    }
    let html = "<div class='dataset-list'>";
    for (const d of datasets) {
      const ageColor = d.age_hours < 2 ? "text-success" : d.age_hours < 24 ? "text-warning" : "text-error";
      html += `<div class="dataset-row">
        <span class="pair-name">${d.pair} ${d.timeframe}</span>
        <span>rows: ${d.rows}</span>
        <span class="${ageColor}">${d.age_hours.toFixed(1)}h ago</span>
      </div>`;
    }
    html += "</div>";
    document.getElementById("datasets-status").innerHTML = html;

    const updateSelect = document.getElementById("select-update-pair");
    const retrainSelect = document.getElementById("select-retrain-pair");
    if (updateSelect) {
      updateSelect.innerHTML = '<option value="">Seleccionar par...</option>' +
        datasets.map(d => `<option value="${d.pair}_${d.timeframe}">${d.pair} ${d.timeframe}</option>`).join("");
    }
    if (retrainSelect) {
      retrainSelect.innerHTML = '<option value="">Seleccionar par...</option>' +
        datasets.map(d => `<option value="${d.pair}_${d.timeframe}">${d.pair} ${d.timeframe}</option>`).join("");
    }
  },

  async pauseScheduler() {
    await fetch("/api/scheduler/pause", { method: "POST" });
    this.fetchScheduler();
  },

  async resumeScheduler() {
    await fetch("/api/scheduler/resume", { method: "POST" });
    this.fetchScheduler();
  },

  async addPair() {
    const pair = document.getElementById("input-add-pair").value.toUpperCase();
    if (!pair) return;
    await fetch("/api/sentinel/add", {
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

// Auto-init if container exists
if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("active-dashboard")) {
      ActiveDashboard.init("active-dashboard");
    }
  });
}
