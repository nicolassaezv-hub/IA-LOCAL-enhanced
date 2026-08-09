// ASTRA Workspace — Live Thinking (Roadmap IV, Sección 11)
// Franja transversal bajo la topbar: muestra el razonamiento paso a paso
// de la tarea larga que esté corriendo (Prediction Lab o Forex full
// pipeline), sin importar en qué panel esté parado el usuario. Objetivo
// explícito del spec: que nunca parezca que ASTRA "solo está pensando"
// sin mostrar qué hace.

function _thinkEsc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

const _thinkStatusIcon = {
  pending: "○",
  running: "◐",
  done: "✓",
  error: "✕",
  skipped: "—",
};

let _thinkPollTimer = null;
let _thinkHideTimer = null;

function _thinkRenderSession(session) {
  const strip = document.getElementById("thinking-strip");
  const label = document.getElementById("thinking-strip-label");
  const stepsEl = document.getElementById("thinking-strip-steps");

  label.textContent = session.task_label || session.task_key;
  stepsEl.innerHTML = session.steps.map((s, i) => {
    const icon = `<span class="think-step-icon">${_thinkStatusIcon[s.status] || "○"}</span>`;
    const arrow = i < session.steps.length - 1 ? `<span class="think-step-arrow">→</span>` : "";
    return `<span class="think-step ${s.status}" title="${_thinkEsc(s.detail)}">${icon} ${_thinkEsc(s.label)}</span>${arrow}`;
  }).join("");
  strip.style.display = "flex";
}

async function thinkingRefresh() {
  try {
    const res = await fetch("/api/thinking");
    const d = await res.json();
    if (!d.ok) return;

    // Prioriza la sesión activa; si ninguna está activa, muestra la más
    // reciente por unos segundos (para que el usuario vea el resultado
    // final) y luego oculta la franja.
    const sessions = Object.values(d.sessions || {});
    const active = sessions.find((s) => s.active);

    if (active) {
      if (_thinkHideTimer) { clearTimeout(_thinkHideTimer); _thinkHideTimer = null; }
      _thinkRenderSession(active);
      return;
    }

    const finished = sessions
      .filter((s) => s.finished_at)
      .sort((a, b) => b.finished_at - a.finished_at)[0];

    if (finished && (Date.now() / 1000 - finished.finished_at) < 15) {
      _thinkRenderSession(finished);
      if (!_thinkHideTimer) {
        _thinkHideTimer = setTimeout(() => {
          document.getElementById("thinking-strip").style.display = "none";
          _thinkHideTimer = null;
        }, 15000);
      }
    } else if (!_thinkHideTimer) {
      document.getElementById("thinking-strip").style.display = "none";
    }
  } catch (e) {
    console.error("thinkingRefresh", e);
  }
}

function liveThinkingInit() {
  thinkingRefresh();
  _thinkPollTimer = setInterval(thinkingRefresh, 2000);
}

document.addEventListener("DOMContentLoaded", liveThinkingInit);
