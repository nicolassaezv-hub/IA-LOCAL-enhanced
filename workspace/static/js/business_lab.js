// ASTRA Workspace — Business Lab Workspace (Roadmap IV, Sección 6)
// Todo real sobre forex/business/ (kpi_engine + business_predictor, ya
// probados por CLI) vía /api/business/* — nada simulado. El forecast usa
// la misma fórmula que sme_consultant.sme_forecast() (extrapolación lineal
// real + banda de incertidumbre según R^2 real), calculado server-side.

let _bizForecastChart = null;

function _bizChartColors() {
  const styles = getComputedStyle(document.body);
  return {
    primary: `hsl(${styles.getPropertyValue("--primary")})`,
    muted: `hsl(${styles.getPropertyValue("--muted-foreground")})`,
    border: `hsl(${styles.getPropertyValue("--border")})`,
  };
}

async function bizLoadFileOptions() {
  const sel = document.getElementById("biz-file-select");
  if (!sel) return;
  try {
    const res = await fetch("/api/business/csvs");
    const data = await res.json();
    sel.innerHTML = "";
    (data.files || []).forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p;
      opt.textContent = p;
      sel.appendChild(opt);
    });
    const customOpt = document.createElement("option");
    customOpt.value = "__custom__";
    customOpt.textContent = "Otra ruta (escribir abajo)...";
    sel.appendChild(customOpt);
    if (!(data.files || []).length) {
      sel.value = "__custom__";
    }
  } catch (e) {
    console.error("bizLoadFileOptions", e);
  }
}

function _bizResolvePath() {
  const sel = document.getElementById("biz-file-select");
  if (!sel.value || sel.value === "__custom__") {
    return prompt("Ruta del archivo (CSV/Excel, relativa al proyecto):") || "";
  }
  return sel.value;
}

function _bizFmtMoney(v) {
  if (v === null || v === undefined) return "—";
  return "$" + Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function _bizFmtPct(v) {
  if (v === null || v === undefined) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${Number(v).toFixed(1)}%`;
}

function _bizKpiTile(label, value, cls) {
  const div = document.createElement("div");
  div.className = "kpi-tile" + (cls ? ` ${cls}` : "");
  div.innerHTML = `<div class="kpi-label">${label}</div><div class="kpi-value">${value}</div>`;
  return div;
}

function _bizRenderKpis(kpis) {
  const card = document.getElementById("biz-kpi-card");
  const tag = document.getElementById("biz-type-tag");
  const tiles = document.getElementById("biz-kpi-tiles");
  const anomaliesEl = document.getElementById("biz-anomalies");
  card.style.display = "block";
  tag.textContent = kpis.business_type || "generic";
  tiles.innerHTML = "";

  tiles.appendChild(_bizKpiTile("Ingresos totales", _bizFmtMoney(kpis.total_revenue)));
  tiles.appendChild(_bizKpiTile("Ingreso promedio", _bizFmtMoney(kpis.avg_revenue)));
  tiles.appendChild(_bizKpiTile("Último período", _bizFmtMoney(kpis.latest_revenue)));
  tiles.appendChild(_bizKpiTile(
    "Crecimiento", _bizFmtPct(kpis.growth_rate_pct),
    kpis.growth_rate_pct > 0 ? "kpi-good" : kpis.growth_rate_pct < 0 ? "kpi-bad" : ""
  ));
  tiles.appendChild(_bizKpiTile(
    "Margen bruto", kpis.gross_margin_pct != null ? kpis.gross_margin_pct.toFixed(1) + "%" : "—"
  ));
  tiles.appendChild(_bizKpiTile(
    "Margen neto", kpis.net_margin_pct != null ? kpis.net_margin_pct.toFixed(1) + "%" : "—",
    kpis.net_margin_pct > 0 ? "kpi-good" : kpis.net_margin_pct < 0 ? "kpi-bad" : ""
  ));
  tiles.appendChild(_bizKpiTile(
    "Ratio de gastos", kpis.expense_ratio_pct != null ? kpis.expense_ratio_pct.toFixed(1) + "%" : "—"
  ));
  tiles.appendChild(_bizKpiTile(
    "Tendencia",
    { growing: "▲ Creciendo", declining: "▼ Bajando", stable: "─ Estable" }[kpis.trend_direction] || "—",
    kpis.trend_direction === "growing" ? "kpi-good" : kpis.trend_direction === "declining" ? "kpi-bad" : ""
  ));
  tiles.appendChild(_bizKpiTile(
    "Health Score", `${kpis.health_score ?? "—"}/100`,
    kpis.health_score >= 70 ? "kpi-good" : kpis.health_score < 40 ? "kpi-bad" : ""
  ));
  tiles.appendChild(_bizKpiTile(
    "Nivel de riesgo", kpis.risk_level || "—",
    kpis.risk_level === "LOW" ? "kpi-good" : kpis.risk_level === "HIGH" ? "kpi-bad" : ""
  ));

  const anomalies = kpis.anomalies || [];
  if (anomalies.length) {
    anomaliesEl.innerHTML = `<div style="margin-top:0.4rem;font-weight:600;">Anomalías detectadas (caída &gt;20%):</div>` +
      anomalies.map(a => `<div class="anomaly-row">${a.period}: ${a.change_pct.toFixed(1)}%</div>`).join("");
  } else {
    anomaliesEl.innerHTML = "";
  }
}

function _bizRenderSignal(predict, train) {
  const card = document.getElementById("biz-signal-card");
  const actionEl = document.getElementById("biz-signal-action");
  const metaEl = document.getElementById("biz-signal-meta");
  const trainMetaEl = document.getElementById("biz-train-meta");
  card.style.display = "block";

  const action = predict.action || "STABLE";
  actionEl.textContent = action;
  actionEl.className = "biz-signal-action action-" + action.toLowerCase();
  metaEl.textContent = `Confianza: ${(predict.confidence * 100).toFixed(1)}%  |  Health: ${predict.health_score}/100  |  Riesgo: ${predict.risk_level}`;

  if (train && train.trained) {
    trainMetaEl.textContent = `Modelo entrenado sobre ${train.rows} filas — accuracy ${(train.accuracy * 100).toFixed(1)}%, precision ${(train.precision * 100).toFixed(1)}%.`;
  } else if (train) {
    trainMetaEl.textContent = `Modelo no entrenado (${train.reason || "datos insuficientes"}, ${train.rows || 0} filas) — usando heurística de tendencia.`;
  } else {
    trainMetaEl.textContent = "";
  }
}

function _bizRenderForecast(forecast) {
  const card = document.getElementById("biz-forecast-card");
  const summaryEl = document.getElementById("biz-forecast-summary");
  if (!forecast) {
    card.style.display = "none";
    return;
  }
  card.style.display = "block";
  const canvas = document.getElementById("biz-forecast-canvas");
  if (_bizForecastChart) { _bizForecastChart.destroy(); _bizForecastChart = null; }
  const colors = _bizChartColors();

  const labels = forecast.points.map(p => `Mes ${p.month}`);
  _bizForecastChart = new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "Optimista", data: forecast.points.map(p => p.optimistic), borderColor: colors.primary, backgroundColor: "transparent", borderWidth: 1, borderDash: [4, 3], pointRadius: 0 },
        { label: "Esperado", data: forecast.points.map(p => p.expected), borderColor: colors.primary, backgroundColor: "transparent", borderWidth: 2, pointRadius: 2 },
        { label: "Conservador", data: forecast.points.map(p => p.conservative), borderColor: colors.muted, backgroundColor: "transparent", borderWidth: 1, borderDash: [4, 3], pointRadius: 0 },
      ],
    },
    options: {
      responsive: true,
      scales: {
        x: { ticks: { color: colors.muted }, grid: { display: false } },
        y: { ticks: { color: colors.muted }, grid: { color: colors.border } },
      },
      plugins: { legend: { labels: { color: colors.muted } } },
    },
  });

  summaryEl.textContent = `Proyección a ${forecast.months} meses: ${_bizFmtMoney(forecast.final_expected)} ` +
    `(${_bizFmtPct(forecast.pct_change_vs_latest)} vs actual)  |  Confianza del modelo (R²): ${forecast.confidence_pct}%  |  ` +
    `Banda de incertidumbre: ±${_bizFmtMoney(forecast.uncertainty_band)}`;
}

function _bizRenderPreview(path) {
  fetch(`/api/business/csv/info?path=${encodeURIComponent(path)}`)
    .then(r => r.json())
    .then(info => {
      if (info.error) return;
      const card = document.getElementById("biz-preview-card");
      card.style.display = "block";
      const table = document.getElementById("biz-preview-table");
      const cols = info.normalized_columns || [];
      table.querySelector("thead").innerHTML = "<tr>" + cols.map(c => `<th>${c}</th>`).join("") + "</tr>";
      table.querySelector("tbody").innerHTML = (info.preview || []).map(row =>
        "<tr>" + cols.map(c => `<td>${row[c] !== undefined && row[c] !== null ? row[c] : "—"}</td>`).join("") + "</tr>"
      ).join("");
    })
    .catch(e => console.error("_bizRenderPreview", e));
}

async function bizRun() {
  const btn = document.getElementById("biz-run-btn");
  const statusEl = document.getElementById("biz-run-status");
  const path = _bizResolvePath();
  if (!path) return;
  const months = parseInt(document.getElementById("biz-months-input").value, 10) || 6;

  btn.disabled = true;
  statusEl.textContent = "Corriendo análisis real (KPIs → entrenamiento → predicción → forecast)...";

  try {
    const res = await fetch("/api/business/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ csv_path: path, months }),
    });
    const data = await res.json();
    if (data.error) {
      statusEl.textContent = "Error: " + data.error;
      btn.disabled = false;
      return;
    }
    _bizRenderKpis(data.kpis);
    _bizRenderSignal(data.predict, data.train);
    _bizRenderForecast(data.forecast);
    _bizRenderPreview(path);
    statusEl.textContent = `Análisis completado — ${data.kpis.rows} filas, tipo "${data.business_type}".`;
  } catch (e) {
    statusEl.textContent = "Error de red: " + e;
  } finally {
    btn.disabled = false;
  }
}

// ── Inicialización de la sección ─────────────────────────────────
async function businessLabInit() {
  await bizLoadFileOptions();
  document.getElementById("biz-run-btn").addEventListener("click", bizRun);
}

document.addEventListener("DOMContentLoaded", () => {
  const bizNav = document.querySelector('.nav-item[data-section="business"]');
  if (bizNav) {
    let initialized = false;
    bizNav.addEventListener("click", () => {
      if (!initialized) { initialized = true; businessLabInit(); }
    });
  }
});
