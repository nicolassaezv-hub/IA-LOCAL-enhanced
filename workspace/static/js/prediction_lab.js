// ASTRA Workspace — Prediction Lab Workspace (Roadmap IV, Sección 5)
// Todo el contenido viene de datos reales servidos por /api/lab/* — nada simulado.
// Corre run_full_lab() real (prompt->dataset->viabilidad->plan->pipeline->validación)
// sobre cualquier CSV, guarda el reporte como JSON y visualiza sus métricas reales.

let _labPollTimer = null;
let _labProjectsCache = [];
let _labSort = { key: "timestamp", dir: -1 };
let _labRocChart = null, _labPrChart = null, _labFiChart = null, _labFoldChart = null;

// ── CSVs disponibles para el selector ─────────────────────────────
async function labLoadCsvOptions() {
  const sel = document.getElementById("lab-csv-select");
  if (!sel) return;
  try {
    const res = await fetch("/api/lab/available_csvs");
    const data = await res.json();
    sel.innerHTML = "";
    (data.csvs || []).forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p;
      opt.textContent = p;
      sel.appendChild(opt);
    });
    const customOpt = document.createElement("option");
    customOpt.value = "__custom__";
    customOpt.textContent = "Otra ruta (escribir abajo)...";
    sel.appendChild(customOpt);
  } catch (e) {
    console.error("labLoadCsvOptions", e);
  }
}

function _labResolveCsvPath() {
  const sel = document.getElementById("lab-csv-select");
  if (sel.value === "__custom__") {
    return prompt("Ruta del CSV (relativa al proyecto):") || "";
  }
  return sel.value;
}

// ── Lanzar un nuevo análisis ───────────────────────────────────────
async function labRun() {
  const csvPath = _labResolveCsvPath();
  const idea = document.getElementById("lab-idea-input").value.trim();
  const target = document.getElementById("lab-target-input").value.trim();
  const statusEl = document.getElementById("lab-run-status");
  const btn = document.getElementById("lab-run-btn");

  if (!csvPath) { statusEl.textContent = "Elegí o escribí un CSV primero."; return; }
  if (!idea) { statusEl.textContent = "Describí el problema a resolver."; return; }

  try {
    const res = await fetch("/api/lab/run", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ csv_path: csvPath, idea, target_variable: target || null }),
    });
    const data = await res.json();
    if (data.error) { statusEl.textContent = data.error; return; }

    btn.disabled = true;
    statusEl.textContent = "Corriendo Prediction Lab (prompt→dataset→viabilidad→plan→pipeline→validación)...";
    if (_labPollTimer) clearInterval(_labPollTimer);
    _labPollTimer = setInterval(labPollStatus, 1500);
    labPollStatus();
  } catch (e) {
    statusEl.textContent = "Error: " + e;
  }
}

async function labPollStatus() {
  const statusEl = document.getElementById("lab-run-status");
  const btn = document.getElementById("lab-run-btn");
  try {
    const res = await fetch("/api/lab/run/status");
    const s = await res.json();

    if (s.running) {
      statusEl.textContent = `Corriendo (${s.elapsed_seconds}s transcurridos)...`;
      return;
    }

    if (_labPollTimer) { clearInterval(_labPollTimer); _labPollTimer = null; }
    btn.disabled = false;

    if (s.started_at == null) {
      statusEl.textContent = "Sin análisis en curso.";
      return;
    }
    if (s.ok === false) {
      statusEl.textContent = `✘ Se detuvo en etapa '${s.stage_reached}': ${s.error}`;
    } else if (s.ok === true) {
      statusEl.textContent = `✔ Completado (etapa '${s.stage_reached}') en ${s.elapsed_seconds}s.` +
        (s.saved_path ? ` Guardado en ${s.saved_path}.` : "");
      labLoadProjects();
    }
  } catch (e) {
    console.error("labPollStatus", e);
  }
}

// ── Comparador de modelos (5.2) ────────────────────────────────────
async function labLoadProjects() {
  try {
    const res = await fetch("/api/lab/projects");
    const data = await res.json();
    _labProjectsCache = data.projects || [];
    _labRenderProjectsTable();
  } catch (e) {
    console.error("labLoadProjects", e);
  }
}

function _labRenderProjectsTable() {
  const tbody = document.getElementById("lab-projects-tbody");
  if (!tbody) return;

  const rows = [..._labProjectsCache].sort((a, b) => {
    const k = _labSort.key;
    let va = a[k], vb = b[k];
    if (va == null) va = -Infinity;
    if (vb == null) vb = -Infinity;
    if (typeof va === "string") return _labSort.dir * va.localeCompare(vb);
    return _labSort.dir * (va - vb);
  });

  tbody.innerHTML = "";
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="6">Sin proyectos guardados todavía — corré un análisis en el sandbox de arriba.</td></tr>';
    return;
  }

  rows.forEach((p) => {
    const tr = document.createElement("tr");
    const viab = p.viability_index != null ? p.viability_index.toFixed(0) + "/100" : "—";
    const score = p.mean_score != null ? p.mean_score.toFixed(3) : "—";
    const verdict = p.passes === true ? "✔ PASA" : (p.passes === false ? "✘ NO PASA" : "—");
    tr.innerHTML = `
      <td>${p.index}</td>
      <td>${p.name}</td>
      <td>${viab}</td>
      <td>${score}</td>
      <td>${verdict}</td>
      <td>${p.timestamp}</td>
    `;
    tr.addEventListener("click", () => labShowDetail(p.name));
    tbody.appendChild(tr);
  });
}

function _labWireSortHeaders() {
  document.querySelectorAll("#lab-projects-table th[data-key]").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      if (_labSort.key === key) _labSort.dir *= -1;
      else _labSort = { key, dir: 1 };
      _labRenderProjectsTable();
    });
  });
}

// ── Detalle: visualizaciones (5.3) + antes/después (5.4) ──────────
async function labShowDetail(identifier) {
  try {
    const res = await fetch(`/api/lab/projects/${encodeURIComponent(identifier)}`);
    const data = await res.json();
    if (data.error) { alert(data.error); return; }

    const card = document.getElementById("lab-detail-card");
    card.style.display = "block";
    document.getElementById("lab-detail-name").textContent = data.name;

    const v = data.validation || {};
    const fs = data.feasibility || {};
    const mp = data.model_plan || {};

    document.getElementById("lab-detail-summary").innerHTML = `
      <div class="tf-row"><span>Idea</span><span>${data.idea || "—"}</span></div>
      <div class="tf-row"><span>Viabilidad</span><span>${fs.viability_index != null ? fs.viability_index.toFixed(1) + "/100" : "—"}</span></div>
      <div class="tf-row"><span>Target</span><span>${mp.target_variable || "—"}</span></div>
      <div class="tf-row"><span>Tipo de problema</span><span>${mp.problem_type || "—"}</span></div>
      <div class="tf-row"><span>Método de validación</span><span>${v.method || "—"} (métrica: ${v.metric || "—"})</span></div>
      <div class="tf-row"><span>Score</span><span>${v.mean_score != null ? v.mean_score.toFixed(4) : "—"} ± ${v.std_score != null ? v.std_score.toFixed(4) : "—"}</span></div>
      <div class="tf-row"><span>Veredicto</span><span>${v.passes ? "✔ PASA" : "✘ NO PASA"}</span></div>
    `;

    _labRenderConfusionMatrix(v);
    _labRenderBeforeAfter(v);
    _labRenderRocChart(v);
    _labRenderPrChart(v);
    _labRenderFiChart(v);
    _labRenderFoldChart(v);

    card.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    console.error("labShowDetail", e);
  }
}

function _labRenderConfusionMatrix(v) {
  const el = document.getElementById("lab-confusion-matrix");
  if (!v.confusion_matrix || !v.classes) {
    el.innerHTML = "<div>No disponible (problema de regresión o sin datos de test).</div>";
    return;
  }
  const classes = v.classes;
  const cm = v.confusion_matrix;
  el.style.gridTemplateColumns = `auto repeat(${classes.length}, 1fr)`;
  let html = `<div class="cm-cell cm-header"></div>`;
  classes.forEach((c) => { html += `<div class="cm-cell cm-header">pred ${c}</div>`; });
  cm.forEach((row, i) => {
    html += `<div class="cm-cell cm-header">real ${classes[i]}</div>`;
    row.forEach((val, j) => {
      html += `<div class="cm-cell${i === j ? " cm-diag" : ""}">${val}</div>`;
    });
  });
  el.innerHTML = html;
}

function _labRenderBeforeAfter(v) {
  const el = document.getElementById("lab-before-after");
  if (v.mean_score == null) { el.innerHTML = "<div>Sin datos.</div>"; return; }
  const baseline = v.baseline_score || 0;
  const trained = v.mean_score;
  const label = v.is_classification ? "Baseline: predecir siempre la clase mayoritaria" : "Baseline: predecir siempre la media (R²=0)";
  el.innerHTML = `
    <div class="ba-row">
      <div class="ba-label"><span>${label}</span><span>${baseline.toFixed(3)}</span></div>
      <div class="ba-bar-outer"><div class="ba-bar-inner baseline" style="width:${Math.min(100, baseline * 100)}%"></div></div>
    </div>
    <div class="ba-row">
      <div class="ba-label"><span>Modelo entrenado (real)</span><span>${trained.toFixed(3)}</span></div>
      <div class="ba-bar-outer"><div class="ba-bar-inner" style="width:${Math.min(100, Math.max(0, trained * 100))}%"></div></div>
    </div>
    <div style="font-size:0.72rem; color:hsl(var(--muted-foreground)); margin-top:0.3rem;">
      Mejora real sobre el baseline: ${((trained - baseline) * 100).toFixed(1)} puntos.
    </div>
  `;
}

function _labChartColors() {
  const styles = getComputedStyle(document.body);
  return {
    primary: `hsl(${styles.getPropertyValue("--primary")})`,
    muted: `hsl(${styles.getPropertyValue("--muted-foreground")})`,
    border: `hsl(${styles.getPropertyValue("--border")})`,
  };
}

function _labRenderRocChart(v) {
  const canvas = document.getElementById("lab-roc-canvas");
  if (_labRocChart) { _labRocChart.destroy(); _labRocChart = null; }
  if (!v.roc_curve) return;
  const colors = _labChartColors();
  _labRocChart = new Chart(canvas, {
    type: "line",
    data: {
      labels: v.roc_curve.fpr,
      datasets: [
        { label: "ROC", data: v.roc_curve.tpr, borderColor: colors.primary, backgroundColor: "transparent", borderWidth: 2, pointRadius: 0 },
      ],
    },
    options: {
      responsive: true,
      scales: {
        x: { title: { display: true, text: "FPR", color: colors.muted }, ticks: { color: colors.muted }, grid: { color: colors.border } },
        y: { title: { display: true, text: "TPR", color: colors.muted }, ticks: { color: colors.muted }, grid: { color: colors.border } },
      },
      plugins: { legend: { display: false } },
    },
  });
}

function _labRenderPrChart(v) {
  const canvas = document.getElementById("lab-pr-canvas");
  if (_labPrChart) { _labPrChart.destroy(); _labPrChart = null; }
  if (!v.pr_curve) return;
  const colors = _labChartColors();
  _labPrChart = new Chart(canvas, {
    type: "line",
    data: {
      labels: v.pr_curve.recall,
      datasets: [
        { label: "PR", data: v.pr_curve.precision, borderColor: colors.primary, backgroundColor: "transparent", borderWidth: 2, pointRadius: 0 },
      ],
    },
    options: {
      responsive: true,
      scales: {
        x: { title: { display: true, text: "Recall", color: colors.muted }, ticks: { color: colors.muted }, grid: { color: colors.border } },
        y: { title: { display: true, text: "Precision", color: colors.muted }, ticks: { color: colors.muted }, grid: { color: colors.border } },
      },
      plugins: { legend: { display: false } },
    },
  });
}

function _labRenderFiChart(v) {
  const canvas = document.getElementById("lab-fi-canvas");
  if (_labFiChart) { _labFiChart.destroy(); _labFiChart = null; }
  const fi = v.feature_importance || {};
  const entries = Object.entries(fi).slice(0, 10);
  if (!entries.length) return;
  const colors = _labChartColors();
  _labFiChart = new Chart(canvas, {
    type: "bar",
    data: {
      labels: entries.map((e) => e[0]),
      datasets: [{ data: entries.map((e) => e[1]), backgroundColor: colors.primary, borderWidth: 0 }],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      scales: {
        x: { ticks: { color: colors.muted }, grid: { color: colors.border } },
        y: { ticks: { color: colors.muted }, grid: { display: false } },
      },
      plugins: { legend: { display: false } },
    },
  });
}

function _labRenderFoldChart(v) {
  const canvas = document.getElementById("lab-fold-canvas");
  if (_labFoldChart) { _labFoldChart.destroy(); _labFoldChart = null; }
  const folds = v.fold_results || [];
  if (!folds.length) return;
  const colors = _labChartColors();
  _labFoldChart = new Chart(canvas, {
    type: "bar",
    data: {
      labels: folds.map((f) => `Fold ${f.fold}`),
      datasets: [{ data: folds.map((f) => f.score), backgroundColor: colors.primary, borderWidth: 0 }],
    },
    options: {
      responsive: true,
      scales: {
        x: { ticks: { color: colors.muted }, grid: { display: false } },
        y: { ticks: { color: colors.muted }, grid: { color: colors.border } },
      },
      plugins: { legend: { display: false } },
    },
  });
}

// ── Inicialización de la sección ─────────────────────────────────
async function predictionLabInit() {
  await labLoadCsvOptions();
  await labLoadProjects();
  _labWireSortHeaders();

  document.getElementById("lab-run-btn").addEventListener("click", labRun);
}

document.addEventListener("DOMContentLoaded", () => {
  const predNav = document.querySelector('.nav-item[data-section="prediction"]');
  if (predNav) {
    let initialized = false;
    predNav.addEventListener("click", () => {
      if (!initialized) { initialized = true; predictionLabInit(); }
    });
  }
});
