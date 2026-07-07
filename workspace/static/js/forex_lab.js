// ASTRA Workspace — Forex Lab Workspace (Roadmap IV, Sección 4)
// Todo el contenido viene de datos reales servidos por /api/forex/* — nada simulado.

let _forexChart = null;
let _forexCandleSeries = null;
let _forexSmaSeries = null;
let _forexPriceLines = [];
let _forexTrainPollTimer = null;

function _fmtPct(v) {
  return v != null ? v.toFixed(1) + "%" : "n/d";
}

// ── Pares disponibles ────────────────────────────────────────────
async function forexLoadPairs() {
  const sel = document.getElementById("forex-pair-select");
  if (!sel) return;
  try {
    const res = await fetch("/api/forex/pairs");
    const data = await res.json();
    const current = sel.value;
    sel.innerHTML = "";
    (data.pairs || []).forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p;
      opt.textContent = p;
      sel.appendChild(opt);
    });
    if (current && data.pairs.includes(current)) sel.value = current;
  } catch (e) {
    console.error("forexLoadPairs", e);
  }
}

// ── Dashboard multi-timeframe ────────────────────────────────────
async function forexLoadDashboard() {
  const pair = document.getElementById("forex-pair-select").value;
  if (!pair) return;
  try {
    const res = await fetch(`/api/forex/dashboard?pair=${encodeURIComponent(pair)}`);
    const d = await res.json();

    ["H1", "H4", "D1"].forEach((tf) => {
      const card = document.getElementById(`tf-card-${tf}`);
      const info = d.timeframes[tf];
      if (!info || !info.available) {
        card.innerHTML = `<h4>${tf}</h4><p class="tf-unavailable">Sin CSV</p>`;
        return;
      }
      if (info.error) {
        card.innerHTML = `<h4>${tf}</h4><p class="tf-unavailable">${info.error}</p>`;
        return;
      }
      card.innerHTML = `
        <h4>${tf}</h4>
        <div class="tf-row"><span>Filas</span><span>${info.rows}</span></div>
        <div class="tf-row"><span>Último cierre</span><span>${info.last_close ?? "n/d"}</span></div>
        <div class="tf-row"><span>Desde</span><span>${(info.date_from || "").slice(0, 10)}</span></div>
        <div class="tf-row"><span>Hasta</span><span>${(info.date_to || "").slice(0, 10)}</span></div>
      `;
    });

    const summaryCard = document.getElementById("model-summary-card");
    if (d.model) {
      summaryCard.innerHTML = `
        <div><strong>Último modelo — ${d.pair}</strong></div>
        <div class="tf-row"><span>Tendencia</span><span>${d.model.trend ?? "n/d"}</span></div>
        <div class="tf-row"><span>Confianza</span><span>${d.model.confidence != null ? d.model.confidence : "n/d"}</span></div>
        <div class="tf-row"><span>Accuracy</span><span>${d.model.accuracy != null ? d.model.accuracy + "%" : "n/d"}</span></div>
        <div class="tf-row"><span>Precision</span><span>${d.model.precision != null ? d.model.precision + "%" : "n/d"}</span></div>
        <div class="tf-row"><span>WFV avg</span><span>${d.model.wfv_avg_precision != null ? d.model.wfv_avg_precision + "%" : "n/d"}</span></div>
        <div style="margin-top:0.4rem; font-size:0.72rem; color:hsl(var(--muted-foreground));">${d.model_architecture_note}</div>
      `;
    } else {
      summaryCard.innerHTML = `<div>${d.model_note || "Sin análisis registrado aún."}</div>
        <div style="margin-top:0.4rem; font-size:0.72rem; color:hsl(var(--muted-foreground));">${d.model_architecture_note}</div>`;
    }
  } catch (e) {
    console.error("forexLoadDashboard", e);
  }
}

// ── Gráfico de velas (lightweight-charts) ────────────────────────
function _forexEnsureChart() {
  if (_forexChart) return;
  const el = document.getElementById("forex-chart");
  if (!el || typeof LightweightCharts === "undefined") return;

  const styles = getComputedStyle(document.body);
  const fg = `hsl(${styles.getPropertyValue("--foreground")})`;
  const border = `hsl(${styles.getPropertyValue("--border")})`;

  _forexChart = LightweightCharts.createChart(el, {
    width: el.clientWidth,
    height: 360,
    layout: { background: { type: "solid", color: "transparent" }, textColor: fg },
    grid: { vertLines: { color: border }, horzLines: { color: border } },
    timeScale: { borderColor: border },
    rightPriceScale: { borderColor: border },
  });
  _forexCandleSeries = _forexChart.addCandlestickSeries();
  _forexSmaSeries = _forexChart.addLineSeries({ color: "#d98e5c", lineWidth: 2 });

  window.addEventListener("resize", () => {
    if (_forexChart) _forexChart.applyOptions({ width: el.clientWidth });
  });
}

function _sma(values, period) {
  const out = [];
  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) { out.push(null); continue; }
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += values[j];
    out.push(sum / period);
  }
  return out;
}

async function forexLoadChart() {
  const pair = document.getElementById("forex-pair-select").value;
  const tf = document.getElementById("forex-tf-select").value;
  if (!pair) return;
  try {
    const res = await fetch(`/api/forex/csvs?timeframe=${tf}`);
    const csvData = await res.json();
    const match = (csvData.files || []).find((f) => f.name.toUpperCase() === `${pair}.CSV`);
    if (!match) return;

    const ohlcRes = await fetch(`/api/forex/csv/ohlc?path=${encodeURIComponent(match.path)}&limit=400`);
    const ohlc = await ohlcRes.json();
    if (ohlc.error) return;

    _forexEnsureChart();
    if (!_forexCandleSeries) return;

    _forexCandleSeries.setData(ohlc.data);

    const smaToggle = document.getElementById("forex-sma-toggle");
    if (smaToggle && smaToggle.checked) {
      const closes = ohlc.data.map((d) => d.close);
      const smaVals = _sma(closes, 20);
      const smaData = ohlc.data
        .map((d, i) => (smaVals[i] != null ? { time: d.time, value: smaVals[i] } : null))
        .filter(Boolean);
      _forexSmaSeries.setData(smaData);
    } else {
      _forexSmaSeries.setData([]);
    }

    _forexChart.timeScale().fitContent();
  } catch (e) {
    console.error("forexLoadChart", e);
  }
}

function forexAddPriceLine() {
  if (!_forexCandleSeries) return;
  const val = prompt("Precio para la línea horizontal:");
  const num = parseFloat(val);
  if (isNaN(num)) return;
  const line = _forexCandleSeries.createPriceLine({
    price: num, color: "#d98e5c", lineWidth: 1, lineStyle: 2,
    axisLabelVisible: true, title: `nivel ${num}`,
  });
  _forexPriceLines.push(line);
}

// ── Gestión de CSV ────────────────────────────────────────────────
async function forexLoadCsvList() {
  const tf = document.getElementById("forex-tf-select").value;
  const listEl = document.getElementById("csv-file-list");
  if (!listEl) return;
  try {
    const res = await fetch(`/api/forex/csvs?timeframe=${tf}`);
    const data = await res.json();
    listEl.innerHTML = "";
    (data.files || []).forEach((f) => {
      const row = document.createElement("div");
      row.className = "csv-file-row";
      row.style.cursor = "pointer";
      row.innerHTML = `<span>${f.name}</span><span>${f.size_kb} KB</span>`;
      row.addEventListener("click", () => forexValidateCsv(f.path));
      listEl.appendChild(row);
    });
  } catch (e) {
    console.error("forexLoadCsvList", e);
  }
}

async function forexValidateCsv(path) {
  const out = document.getElementById("csv-validation");
  if (!out) return;
  out.textContent = "Validando...";
  try {
    const res = await fetch(`/api/forex/csv/info?path=${encodeURIComponent(path)}`);
    const info = await res.json();
    if (info.error) {
      out.textContent = info.error;
      out.classList.add("invalid");
      return;
    }
    out.classList.toggle("invalid", !info.valid);
    out.innerHTML = `
      <div><strong>${path}</strong> — ${info.rows} filas</div>
      <div>${info.valid ? "✔ Columnas OHLC OK" : "✘ Faltan columnas: " + info.missing_required.join(", ")}</div>
      ${info.stats.close_mean != null ? `<div>Cierre: min ${info.stats.close_min} · max ${info.stats.close_max} · media ${info.stats.close_mean}</div>` : ""}
      ${info.date_range ? `<div>Rango: ${info.date_range.from} → ${info.date_range.to}</div>` : ""}
    `;
  } catch (e) {
    out.textContent = "Error validando CSV: " + e;
  }
}

// ── Entrenamiento ─────────────────────────────────────────────────
async function forexStartTraining() {
  const pair = document.getElementById("forex-pair-select").value;
  const tf = document.getElementById("forex-tf-select").value;
  if (!pair) return;
  const path = `CSVs/${tf}/${pair}.csv`;
  try {
    const res = await fetch("/api/forex/train/start", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ csv_path: path }),
    });
    const data = await res.json();
    if (data.error) {
      document.getElementById("train-stage-label").textContent = data.error;
      return;
    }
    if (_forexTrainPollTimer) clearInterval(_forexTrainPollTimer);
    _forexTrainPollTimer = setInterval(forexPollTraining, 2000);
    forexPollTraining();
  } catch (e) {
    console.error("forexStartTraining", e);
  }
}

async function forexPollTraining() {
  try {
    const res = await fetch("/api/forex/train/status");
    const s = await res.json();

    document.getElementById("train-progress-bar").style.width = `${s.progress_pct || 0}%`;
    document.getElementById("train-stage-label").textContent = s.running
      ? `${s.stage || "Iniciando..."} (${s.progress_pct || 0}%)`
      : (s.error ? `Error: ${s.error}` : (s.result_summary || "Sin entrenamiento en curso."));

    const metrics = document.getElementById("train-metrics");
    metrics.innerHTML = `
      ${s.accuracy != null ? `<div>Accuracy: <span class="metric-value">${s.accuracy}%</span></div>` : ""}
      ${s.precision != null ? `<div>Precision: <span class="metric-value">${s.precision}%</span></div>` : ""}
      ${s.wfv_avg_precision != null ? `<div>WFV avg: <span class="metric-value">${s.wfv_avg_precision}%</span></div>` : ""}
      ${s.confidence != null ? `<div>Confidence: <span class="metric-value">${s.confidence}</span></div>` : ""}
    `;

    if (!s.running && _forexTrainPollTimer) {
      clearInterval(_forexTrainPollTimer);
      _forexTrainPollTimer = null;
      forexLoadDashboard();
      forexLoadAlerts();
    }
  } catch (e) {
    console.error("forexPollTraining", e);
  }
}

// ── Circuit Breaker ───────────────────────────────────────────────
async function forexLoadCircuit() {
  const out = document.getElementById("circuit-status");
  if (!out) return;
  try {
    const res = await fetch("/api/forex/circuit");
    const c = await res.json();
    if (c.error) { out.textContent = c.error; return; }
    const stateClass = c.open === false ? "circuit-closed" : "circuit-open";
    out.innerHTML = `
      <div class="${stateClass}">${c.open === false ? "⛔ TRADING BLOQUEADO" : "✔ TRADING ABIERTO"}</div>
      ${c.reason ? `<div class="tf-row"><span>Motivo</span><span>${c.reason}</span></div>` : ""}
      <div class="tf-row"><span>Pérdida diaria</span><span>${_fmtPct(c.daily_loss_pct)}</span></div>
      <div class="tf-row"><span>Pérdida semanal</span><span>${_fmtPct(c.weekly_loss_pct)}</span></div>
      <div class="tf-row"><span>Drawdown</span><span>${_fmtPct(c.drawdown_pct)}</span></div>
      <div class="tf-row"><span>Balance</span><span>${c.balance ?? "n/d"}</span></div>
      ${c.cooldown_remaining_h ? `<div class="tf-row"><span>Cooldown restante</span><span>${c.cooldown_remaining_h.toFixed(1)}h</span></div>` : ""}
    `;
  } catch (e) {
    out.textContent = "Sin datos del Circuit Breaker.";
  }
}

// ── Alertas ───────────────────────────────────────────────────────
async function forexLoadAlerts() {
  const out = document.getElementById("alerts-list");
  if (!out) return;
  try {
    const res = await fetch("/api/forex/alerts");
    const data = await res.json();
    out.innerHTML = "";
    (data.alerts || []).forEach((a) => {
      const row = document.createElement("div");
      row.className = `alert-row alert-${a.kind}`;
      row.innerHTML = `<span class="alert-ts">${a.ts}</span><span>${a.message}</span>`;
      out.appendChild(row);
    });
    if (!data.alerts || !data.alerts.length) out.innerHTML = "<div>Sin alertas todavía.</div>";
  } catch (e) {
    console.error("forexLoadAlerts", e);
  }
}

// ── Inicialización de la sección ─────────────────────────────────
async function forexLabInit() {
  await forexLoadPairs();
  const sel = document.getElementById("forex-pair-select");
  if (sel && !sel.value && sel.options.length) sel.selectedIndex = 0;

  await Promise.all([forexLoadDashboard(), forexLoadChart(), forexLoadCsvList(), forexLoadCircuit(), forexLoadAlerts()]);

  document.getElementById("forex-pair-select").addEventListener("change", () => {
    forexLoadDashboard();
    forexLoadChart();
  });
  document.getElementById("forex-tf-select").addEventListener("change", () => {
    forexLoadChart();
    forexLoadCsvList();
  });
  document.getElementById("forex-sma-toggle").addEventListener("change", forexLoadChart);
  document.getElementById("forex-refresh-btn").addEventListener("click", () => {
    forexLoadDashboard(); forexLoadChart(); forexLoadCsvList(); forexLoadCircuit(); forexLoadAlerts();
  });
  document.getElementById("forex-add-line-btn").addEventListener("click", forexAddPriceLine);
  document.getElementById("train-start-btn").addEventListener("click", forexStartTraining);

  setInterval(forexLoadAlerts, 15000);
  setInterval(forexLoadCircuit, 20000);
}

document.addEventListener("DOMContentLoaded", () => {
  const forexNav = document.querySelector('.nav-item[data-section="forex"]');
  if (forexNav) {
    let initialized = false;
    forexNav.addEventListener("click", () => {
      if (!initialized) { initialized = true; forexLabInit(); }
    });
  }
});
