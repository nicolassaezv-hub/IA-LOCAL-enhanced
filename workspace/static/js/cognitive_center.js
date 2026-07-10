// ASTRA Workspace — Cognitive Center (Roadmap IV, Sección 7)
// "Ventana exclusiva para la memoria" — todo real sobre cognitive_center.py,
// que a su vez agrega memory.py / project_memory.py / feedback/* vía
// /api/cognitive/* — nada simulado. 7.2 es búsqueda en lenguaje natural
// (LLM con fallback heurístico, calculado server-side).

function _cogEsc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function _cogShort(s, n = 90) {
  s = String(s ?? "");
  return s.length > n ? s.slice(0, n) + "…" : s;
}

// ── Resumen agregado ────────────────────────────────────────────
async function cogLoadOverview() {
  const el = document.getElementById("cog-overview-tiles");
  try {
    const res = await fetch("/api/cognitive/overview");
    const d = await res.json();
    if (d.error) throw new Error(d.error);

    const tiles = [
      ["Conversaciones", d.conversations_total],
      ["Proyectos", d.projects_total],
      ["Modelos entrenados", d.models_total],
      ["Tareas pendientes", `${d.tasks_pending}/${d.tasks_total}`],
      ["Comandos registrados", d.commands_logged],
      ["Pares con umbral propio", d.pairs_with_custom_thresholds],
    ];
    el.innerHTML = tiles.map(([label, value]) => `
      <div class="kpi-tile">
        <div class="kpi-label">${_cogEsc(label)}</div>
        <div class="kpi-value">${_cogEsc(value)}</div>
      </div>`).join("");
  } catch (e) {
    el.innerHTML = `<div class="train-stage-label">Error cargando resumen: ${_cogEsc(e.message)}</div>`;
  }
}

// ── Timeline unificado ──────────────────────────────────────────
const _cogKindLabels = {
  conversation: "💬 Conversación",
  command: "⚙ Comando",
  model: "📈 Modelo",
  model_update: "📈 Modelo actualizado",
  project: "📁 Proyecto",
  task: "✅ Tarea",
};

async function cogLoadTimeline() {
  const el = document.getElementById("cog-timeline");
  try {
    const res = await fetch("/api/cognitive/timeline?limit=30");
    const d = await res.json();
    const events = d.events || [];
    if (!events.length) {
      el.innerHTML = `<div class="train-stage-label">Sin actividad registrada todavía.</div>`;
      return;
    }
    el.innerHTML = events.map((e) => `
      <div class="cog-event">
        <div class="cog-event-top">
          <span>${_cogKindLabels[e.kind] || e.kind}</span>
          <span>${_cogEsc(e.timestamp || "")}</span>
        </div>
        <div class="cog-event-title">${_cogEsc(_cogShort(e.title, 90))}</div>
        ${e.detail ? `<div class="cog-event-detail">${_cogEsc(_cogShort(e.detail, 140))}</div>` : ""}
      </div>`).join("");
  } catch (e) {
    el.innerHTML = `<div class="train-stage-label">Error cargando línea de tiempo: ${_cogEsc(e.message)}</div>`;
  }
}

// ── Knowledge Graph (layout circular simple, sin dependencias nuevas) ──
async function cogLoadKnowledgeGraph() {
  const svg = document.getElementById("cog-graph-svg");
  const emptyEl = document.getElementById("cog-graph-empty");
  try {
    const res = await fetch("/api/cognitive/knowledge_graph");
    const d = await res.json();
    const nodes = d.nodes || [];
    const edges = d.edges || [];

    svg.innerHTML = "";
    if (!nodes.length) {
      svg.style.display = "none";
      emptyEl.style.display = "block";
      return;
    }
    svg.style.display = "block";
    emptyEl.style.display = "none";

    const cx = 210, cy = 160, r = Math.min(120, 40 + nodes.length * 6);
    const pos = {};
    nodes.forEach((n, i) => {
      const angle = (2 * Math.PI * i) / nodes.length;
      pos[n.id] = { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
    });

    const ns = "http://www.w3.org/2000/svg";
    const edgeGroup = document.createElementNS(ns, "g");
    edges.forEach((e) => {
      const a = pos[e.source], b = pos[e.target];
      if (!a || !b) return;
      const line = document.createElementNS(ns, "line");
      line.setAttribute("class", "kg-edge");
      line.setAttribute("x1", a.x); line.setAttribute("y1", a.y);
      line.setAttribute("x2", b.x); line.setAttribute("y2", b.y);
      line.setAttribute("stroke-width", Math.min(4, 1 + (e.weight || 1) * 0.5));
      edgeGroup.appendChild(line);
    });
    svg.appendChild(edgeGroup);

    const nodeGroup = document.createElementNS(ns, "g");
    nodes.forEach((n) => {
      const p = pos[n.id];
      const g = document.createElementNS(ns, "g");
      g.setAttribute("class", `kg-node-${n.group}`);
      const circle = document.createElementNS(ns, "circle");
      circle.setAttribute("cx", p.x); circle.setAttribute("cy", p.y);
      circle.setAttribute("r", n.group === "category" ? 10 : 14);
      g.appendChild(circle);
      const label = document.createElementNS(ns, "text");
      label.setAttribute("class", "kg-label");
      label.setAttribute("x", p.x); label.setAttribute("y", p.y - 16);
      label.setAttribute("text-anchor", "middle");
      label.textContent = n.label;
      g.appendChild(label);
      const titleTag = document.createElementNS(ns, "title");
      const extra = n.group === "pair"
        ? `accuracy=${n.accuracy ?? "—"} precision=${n.precision ?? "—"}`
        : n.group === "project"
        ? `estado=${n.status ?? "—"} tareas=${n.task_count ?? 0}`
        : `usos=${n.count ?? 0}`;
      titleTag.textContent = `${n.label} (${n.group}) — ${extra}`;
      g.appendChild(titleTag);
      nodeGroup.appendChild(g);
    });
    svg.appendChild(nodeGroup);
  } catch (e) {
    emptyEl.textContent = "Error cargando el knowledge graph: " + e.message;
    emptyEl.style.display = "block";
    svg.style.display = "none";
  }
}

// ── Herramientas más usadas ─────────────────────────────────────
async function cogLoadToolsTable() {
  const tbody = document.querySelector("#cog-tools-table tbody");
  try {
    const res = await fetch("/api/cognitive/tools_usage");
    const d = await res.json();
    const top = d.top_commands || [];
    if (!top.length) {
      tbody.innerHTML = `<tr><td colspan="2">Sin comandos registrados todavía.</td></tr>`;
      return;
    }
    tbody.innerHTML = top.map((c) => `
      <tr><td>${_cogEsc(c.command)}</td><td>${_cogEsc(c.count)}</td></tr>
    `).join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="2">Error: ${_cogEsc(e.message)}</td></tr>`;
  }
}

// ── Preferencias aprendidas ─────────────────────────────────────
async function cogLoadPreferences() {
  const tbody = document.querySelector("#cog-prefs-table tbody");
  const emptyEl = document.getElementById("cog-prefs-empty");
  try {
    const res = await fetch("/api/cognitive/preferences");
    const d = await res.json();
    const entries = Object.entries(d.adaptive_thresholds || {});
    if (!entries.length) {
      tbody.innerHTML = "";
      emptyEl.style.display = "block";
      return;
    }
    emptyEl.style.display = "none";
    tbody.innerHTML = entries.map(([pair, v]) => `
      <tr>
        <td>${_cogEsc(pair)}</td>
        <td>${_cogEsc(v.confidence)}</td>
        <td>${_cogEsc(v.adx)}</td>
        <td>${_cogEsc(v.n_updates ?? 0)}</td>
      </tr>`).join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="4">Error: ${_cogEsc(e.message)}</td></tr>`;
  }
}

// ── 7.2 Búsqueda en lenguaje natural ────────────────────────────
function _cogRenderSearchBlock(title, items, renderRow) {
  if (!items || !items.length) return "";
  return `
    <div class="cog-search-block">
      <h4>${_cogEsc(title)} (${items.length})</h4>
      ${items.map(renderRow).join("")}
    </div>`;
}

async function cogSearch() {
  const input = document.getElementById("cog-search-input");
  const meta = document.getElementById("cog-search-meta");
  const resultsBox = document.getElementById("cog-search-results");
  const query = input.value.trim();
  if (!query) {
    meta.textContent = "Escribe una consulta primero.";
    return;
  }
  meta.textContent = "Buscando...";
  resultsBox.style.display = "none";

  try {
    const res = await fetch("/api/cognitive/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const d = await res.json();
    if (d.error) throw new Error(d.error);

    const engineTag = d.used_llm ? "LLM" : "heurístico";
    let metaTxt = `Motor: ${engineTag} · fuentes: ${(d.sources_searched || []).join(", ")} · ${d.total_hits} resultado(s)`;
    if (d.used_fallback_unfiltered) {
      metaTxt += " · sin coincidencia exacta — mostrando lo más reciente";
    }
    meta.textContent = metaTxt;

    const r = d.results || {};
    let html = "";
    html += _cogRenderSearchBlock("Conversaciones", r.conversations, (c) => `
      <div class="cog-event">
        <div class="cog-event-top"><span>💬</span><span>${_cogEsc(c.timestamp)}</span></div>
        <div class="cog-event-title">${_cogEsc(_cogShort(c.user_input, 90))}</div>
        <div class="cog-event-detail">${_cogEsc(_cogShort(c.ai_response, 140))}</div>
      </div>`);
    html += _cogRenderSearchBlock("Comandos", r.commands, (c) => `
      <div class="cog-event">
        <div class="cog-event-top"><span>⚙ ${_cogEsc(c.category || "general")}</span><span>${_cogEsc(c.executed_at)}</span></div>
        <div class="cog-event-title">${_cogEsc(c.command)}</div>
        <div class="cog-event-detail">${_cogEsc(_cogShort(c.summary, 140))}</div>
      </div>`);
    html += _cogRenderSearchBlock("Modelos", r.models, (m) => `
      <div class="cog-event">
        <div class="cog-event-title">${_cogEsc(m.pair)} <span class="tag">accuracy=${_cogEsc(m.accuracy)}</span></div>
        <div class="cog-event-detail">precision=${_cogEsc(m.precision)} · filas=${_cogEsc(m.rows_trained)} · wfv=${_cogEsc(m.wfv_score)}</div>
      </div>`);
    html += _cogRenderSearchBlock("Proyectos", r.projects, (p) => `
      <div class="cog-event">
        <div class="cog-event-title">${_cogEsc(p.name)} <span class="tag">${_cogEsc(p.status)}</span></div>
        <div class="cog-event-detail">${_cogEsc(p.description || "")}</div>
      </div>`);
    html += _cogRenderSearchBlock("Tareas", r.tasks, (t) => `
      <div class="cog-event">
        <div class="cog-event-title">${t.done ? "✓" : "○"} ${_cogEsc(t.description)}</div>
        <div class="cog-event-detail">${_cogEsc(t.project_name || "")}</div>
      </div>`);
    if (r.preferences && Object.keys(r.preferences.adaptive_thresholds || {}).length) {
      html += _cogRenderSearchBlock(
        "Preferencias",
        Object.entries(r.preferences.adaptive_thresholds),
        ([pair, v]) => `
        <div class="cog-event">
          <div class="cog-event-title">${_cogEsc(pair)}</div>
          <div class="cog-event-detail">confidence=${_cogEsc(v.confidence)} adx=${_cogEsc(v.adx)}</div>
        </div>`
      );
    }

    if (!html) {
      html = `<div class="train-stage-label">Sin resultados para esta consulta.</div>`;
    }
    resultsBox.innerHTML = html;
    resultsBox.style.display = "block";
  } catch (e) {
    meta.textContent = "Error en la búsqueda: " + e.message;
  }
}

// ── Inicialización de la sección ─────────────────────────────────
async function cognitiveCenterInit() {
  document.getElementById("cog-search-btn").addEventListener("click", cogSearch);
  document.getElementById("cog-search-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") cogSearch();
  });
  await Promise.all([
    cogLoadOverview(),
    cogLoadTimeline(),
    cogLoadKnowledgeGraph(),
    cogLoadToolsTable(),
    cogLoadPreferences(),
  ]);
}

document.addEventListener("DOMContentLoaded", () => {
  const cogNav = document.querySelector('.nav-item[data-section="cognitive"]');
  if (cogNav) {
    let initialized = false;
    cogNav.addEventListener("click", () => {
      if (!initialized) { initialized = true; cognitiveCenterInit(); }
    });
  }
});
