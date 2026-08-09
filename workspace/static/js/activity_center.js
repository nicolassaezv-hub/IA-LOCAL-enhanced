// ASTRA Workspace — Activity Center (Roadmap IV, Sección 9)
// Feed unificado en vivo: alertas del Workspace + comandos ejecutados +
// señales forex + eventos de evolución, vía /api/activity/*. Poll cada 5s
// mientras la pestaña esté abierta y "auto-actualizar" activado.

function _actEsc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

const _actSourceIcons = { alert: "🔔", command: "⌨️", signal: "📈", evolution: "🧬" };
const _actKindClass = { info: "info", success: "success", warning: "warning", error: "error" };

let _actPollTimer = null;

async function actLoadStats() {
  const el = document.getElementById("act-stats-tiles");
  try {
    const res = await fetch("/api/activity/stats");
    const d = await res.json();
    if (!d.ok) throw new Error(d.error || "error desconocido");
    const tiles = [
      ["Alertas", d.alerts_total],
      ["Comandos", d.commands_total],
      ["Señales Forex", d.signals_total],
      ["Eventos evolución", d.evolution_events_total],
    ];
    el.innerHTML = tiles.map(([label, value]) => `
      <div class="kpi-tile">
        <div class="kpi-label">${_actEsc(label)}</div>
        <div class="kpi-value">${_actEsc(value)}</div>
      </div>`).join("");
  } catch (e) {
    el.innerHTML = `<div class="train-stage-label">Error cargando resumen: ${_actEsc(e.message)}</div>`;
  }
}

async function actLoadFeed() {
  const el = document.getElementById("act-feed");
  const source = document.getElementById("act-source-filter").value;
  try {
    const url = source ? `/api/activity/feed?sources=${encodeURIComponent(source)}&limit=60` : "/api/activity/feed?limit=60";
    const res = await fetch(url);
    const d = await res.json();
    if (!d.ok) throw new Error(d.error || "error desconocido");
    const items = d.items || [];
    if (!items.length) {
      el.innerHTML = `<div class="train-stage-label">Sin actividad registrada todavía${source ? " para esta fuente" : ""}.</div>`;
      return;
    }
    el.innerHTML = items.map((it) => `
      <div class="cog-event">
        <div class="cog-event-top">
          <span>${_actSourceIcons[it.source] || "•"} ${_actEsc(it.source)}</span>
          <span>${_actEsc(it.timestamp || "")}</span>
        </div>
        <div class="cog-event-title">
          <span class="evo-status-pill ${_actKindClass[it.kind] || ""}">${_actEsc(it.kind)}</span>
          ${_actEsc(it.title)}
        </div>
        ${it.detail ? `<div class="cog-event-detail">${_actEsc(it.detail)}</div>` : ""}
      </div>`).join("");
  } catch (e) {
    el.innerHTML = `<div class="train-stage-label">Error cargando el feed: ${_actEsc(e.message)}</div>`;
  }
}

function actRefreshAll() {
  actLoadStats();
  actLoadFeed();
}

function actStartPolling() {
  if (_actPollTimer) clearInterval(_actPollTimer);
  _actPollTimer = setInterval(() => {
    if (document.getElementById("act-autorefresh-toggle").checked) actRefreshAll();
  }, 5000);
}

async function activityCenterInit() {
  document.getElementById("act-source-filter").addEventListener("change", actLoadFeed);
  await actRefreshAll();
  actStartPolling();
}

document.addEventListener("DOMContentLoaded", () => {
  const navBtn = document.querySelector('.nav-item[data-section="activity"]');
  if (navBtn) {
    let initialized = false;
    navBtn.addEventListener("click", () => {
      if (!initialized) { initialized = true; activityCenterInit(); }
      else actRefreshAll();
    });
  }
});
