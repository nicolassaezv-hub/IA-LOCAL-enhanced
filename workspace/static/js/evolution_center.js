// ASTRA Workspace — Evolution Center (Roadmap IV, Sección 8)
// "Cómo evoluciona ASTRA, visualmente" — todo real sobre evolution/,
// constitution/ y evolutionary_cycle.py (Fases 7-9, ya operativas) vía
// /api/evolution/*. 8.2 permite aprobar/rechazar propuestas de verdad
// (crea rollback points reales, escribe en el audit log real).

function _evoEsc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function _evoShort(s, n = 90) {
  s = String(s ?? "");
  return s.length > n ? s.slice(0, n) + "…" : s;
}

function _evoStatusPill(status) {
  return `<span class="evo-status-pill ${_evoEsc(status)}">${_evoEsc(status)}</span>`;
}

// ── 8.1 Resumen del ciclo evolutivo ─────────────────────────────
async function evoLoadOverview() {
  const el = document.getElementById("evo-overview-tiles");
  try {
    const res = await fetch("/api/evolution/overview");
    const d = await res.json();
    if (!d.ok) throw new Error(d.error || "error desconocido");

    const snap = d.latest_snapshot;
    const tiles = [
      ["Propuestas totales", d.proposals_total],
      ["Pendientes", d.proposals_by_status?.pending || 0],
      ["Aprobadas", d.proposals_by_status?.approved || 0],
      ["Rollback points", d.rollback_points_total],
      ["Audit log", d.audit_total],
      ["Señales (últ. snapshot)", snap ? snap.total_signals : "—"],
    ];
    el.innerHTML = tiles.map(([label, value]) => `
      <div class="kpi-tile">
        <div class="kpi-label">${_evoEsc(label)}</div>
        <div class="kpi-value">${_evoEsc(value)}</div>
      </div>`).join("");
  } catch (e) {
    el.innerHTML = `<div class="train-stage-label">Error cargando resumen: ${_evoEsc(e.message)}</div>`;
  }
}

async function evoRunCycle() {
  const btn = document.getElementById("evo-run-cycle-btn");
  const resultEl = document.getElementById("evo-cycle-result");
  btn.disabled = true;
  resultEl.textContent = "Ejecutando ciclo evolutivo (monitor → detecta → propone → valida → aprueba → feedback → audit)...";
  try {
    const res = await fetch("/api/evolution/cycle/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ auto_approve_minor: false }),
    });
    const d = await res.json();
    if (!d.ok) throw new Error(d.error || "error desconocido");
    resultEl.textContent = `Ciclo completo: ${d.opportunities_found} oportunidad(es), ` +
      `${d.proposals_created} propuesta(s) creada(s), ${d.proposals_approved} aprobada(s), ` +
      `${d.proposals_rejected} rechazada(s), ${d.threshold_updates} umbral(es) ajustado(s).`;
    await Promise.all([evoLoadOverview(), evoLoadTimeline(), evoLoadPerformanceHistory(), evoLoadProposals()]);
  } catch (e) {
    resultEl.textContent = "Error ejecutando el ciclo: " + e.message;
  } finally {
    btn.disabled = false;
  }
}

// ── Historial de eventos ─────────────────────────────────────────
const _evoKindIcons = {
  performance_snapshot: "📊", proposal_created: "📝", proposal_status_changed: "🔄",
  threshold_update: "🎯", context_saved: "🧠",
};

async function evoLoadTimeline() {
  const el = document.getElementById("evo-timeline");
  try {
    const res = await fetch("/api/evolution/timeline?limit=30");
    const d = await res.json();
    if (!d.ok) throw new Error(d.error || "error desconocido");
    const events = d.events || [];
    if (!events.length) {
      el.innerHTML = `<div class="train-stage-label">Sin eventos de evolución registrados todavía.</div>`;
      return;
    }
    el.innerHTML = events.map((e) => `
      <div class="cog-event">
        <div class="cog-event-top">
          <span>${_evoKindIcons[e.event_type] || "•"} ${_evoEsc(e.event_type)}</span>
          <span>${_evoEsc(e.timestamp || "")}</span>
        </div>
        <div class="cog-event-title">${_evoEsc(_evoShort(e.description, 90))}</div>
      </div>`).join("");
  } catch (e) {
    el.innerHTML = `<div class="train-stage-label">Error cargando historial: ${_evoEsc(e.message)}</div>`;
  }
}

// ── Historial de rendimiento ──────────────────────────────────────
async function evoLoadPerformanceHistory() {
  const tbody = document.querySelector("#evo-perf-table tbody");
  try {
    const res = await fetch("/api/evolution/performance_history?limit=15");
    const d = await res.json();
    if (!d.ok) throw new Error(d.error || "error desconocido");
    const snaps = d.snapshots || [];
    if (!snaps.length) {
      tbody.innerHTML = `<tr><td colspan="5">Sin snapshots todavía — corre el ciclo evolutivo.</td></tr>`;
      return;
    }
    tbody.innerHTML = snaps.map((s) => `
      <tr>
        <td>${_evoEsc((s.timestamp || "").slice(0, 19))}</td>
        <td>${_evoEsc(s.total_signals)}</td>
        <td>${_evoEsc((s.feedback_approval * 100).toFixed(1))}%</td>
        <td>${_evoEsc(s.models_trained)}</td>
        <td>${_evoEsc(s.active_pairs)}</td>
      </tr>`).join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="5">Error: ${_evoEsc(e.message)}</td></tr>`;
  }
}

// ── 8.2 Propuestas ────────────────────────────────────────────────
async function evoLoadProposals() {
  const tbody = document.querySelector("#evo-proposals-table tbody");
  const filter = document.getElementById("evo-proposals-filter").value;
  try {
    const url = filter ? `/api/evolution/proposals?status=${encodeURIComponent(filter)}` : "/api/evolution/proposals";
    const res = await fetch(url);
    const d = await res.json();
    if (!d.ok) throw new Error(d.error || "error desconocido");
    const proposals = d.proposals || [];
    if (!proposals.length) {
      tbody.innerHTML = `<tr><td colspan="7">Sin propuestas${filter ? " con este estado" : ""}.</td></tr>`;
      return;
    }
    tbody.innerHTML = proposals.map((p) => {
      const isPending = p.status === "pending";
      return `
      <tr>
        <td>#${_evoEsc(p.id)}</td>
        <td>${_evoEsc(p.proposal_type)}</td>
        <td>${_evoEsc(p.component)}</td>
        <td>${_evoEsc(_evoShort(p.description, 60))}</td>
        <td>${_evoEsc(p.priority_label)}</td>
        <td>${_evoStatusPill(p.status)}</td>
        <td>
          <div class="evo-btn-row">
            <button class="tbl-action-btn" data-evo-detail="${p.id}">Ver</button>
            ${isPending ? `<button class="tbl-action-btn primary" data-evo-approve="${p.id}">Aprobar</button>` : ""}
            ${isPending ? `<button class="tbl-action-btn destructive" data-evo-reject="${p.id}">Rechazar</button>` : ""}
          </div>
        </td>
      </tr>`;
    }).join("");

    tbody.querySelectorAll("[data-evo-detail]").forEach((btn) =>
      btn.addEventListener("click", () => evoShowProposalDetail(parseInt(btn.dataset.evoDetail, 10)))
    );
    tbody.querySelectorAll("[data-evo-approve]").forEach((btn) =>
      btn.addEventListener("click", () => evoApproveProposal(parseInt(btn.dataset.evoApprove, 10)))
    );
    tbody.querySelectorAll("[data-evo-reject]").forEach((btn) =>
      btn.addEventListener("click", () => evoRejectProposal(parseInt(btn.dataset.evoReject, 10)))
    );
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="7">Error: ${_evoEsc(e.message)}</td></tr>`;
  }
}

async function evoShowProposalDetail(id) {
  const box = document.getElementById("evo-proposal-detail");
  box.style.display = "block";
  box.innerHTML = `<div class="train-stage-label">Cargando detalle de #${id}...</div>`;
  try {
    const res = await fetch(`/api/evolution/proposals/${id}`);
    const d = await res.json();
    if (!d.ok) throw new Error(d.error || "error desconocido");
    const p = d.proposal;
    const v = d.validation;
    box.innerHTML = `
      <h3>Propuesta #${_evoEsc(p.id)} — ${_evoEsc(p.proposal_type)} → ${_evoEsc(p.component)} ${_evoStatusPill(p.status)}</h3>
      <p>${_evoEsc(p.description)}</p>
      <p class="train-stage-label">Razón: ${_evoEsc(p.rationale)}</p>
      <p class="train-stage-label">Creada: ${_evoEsc(p.created_at)} ${p.applied_at ? "· Aplicada: " + _evoEsc(p.applied_at) : ""}</p>
      ${p.result ? `<p class="train-stage-label">Resultado: ${_evoEsc(p.result)}</p>` : ""}
      <h4>Validación constitucional (preview en vivo)</h4>
      <p>${v.is_valid ? "✅ VÁLIDA" : "🚫 BLOQUEADA"} — reglas verificadas: ${_evoEsc(v.checked_rules.join(", "))}</p>
      ${v.violations.length ? `<div class="evo-violation">${v.violations.map((x) => "! " + _evoEsc(x)).join("<br>")}</div>` : ""}
      ${v.warnings.length ? `<div class="evo-warning">${v.warnings.map((x) => "* " + _evoEsc(x)).join("<br>")}</div>` : ""}
      ${d.rollback_points.length ? `
        <h4>Rollback points asociados</h4>
        ${d.rollback_points.map((rp) => `<div class="cog-event-detail">#${_evoEsc(rp.point_id)} — ${_evoEsc(rp.description)} (${_evoEsc(rp.created_at)})</div>`).join("")}
      ` : ""}
      <div class="evo-btn-row" style="margin-top:0.6rem;">
        ${p.status === "pending" ? `<button class="tbl-action-btn primary" data-evo-approve="${p.id}">Aprobar</button>` : ""}
        ${p.status === "pending" ? `<button class="tbl-action-btn destructive" data-evo-reject="${p.id}">Rechazar</button>` : ""}
        <button class="tbl-action-btn" id="evo-detail-close">Cerrar</button>
      </div>
    `;
    const approveBtn = box.querySelector("[data-evo-approve]");
    if (approveBtn) approveBtn.addEventListener("click", () => evoApproveProposal(p.id));
    const rejectBtn = box.querySelector("[data-evo-reject]");
    if (rejectBtn) rejectBtn.addEventListener("click", () => evoRejectProposal(p.id));
    document.getElementById("evo-detail-close").addEventListener("click", () => { box.style.display = "none"; });
  } catch (e) {
    box.innerHTML = `<div class="train-stage-label">Error: ${_evoEsc(e.message)}</div>`;
  }
}

async function evoApproveProposal(id) {
  try {
    const res = await fetch(`/api/evolution/proposals/${id}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ justification: "Aprobado desde el Workspace" }),
    });
    const d = await res.json();
    if (!d.ok) throw new Error(d.error || "error desconocido");
    document.getElementById("evo-proposal-detail").style.display = "none";
    await Promise.all([evoLoadProposals(), evoLoadOverview(), evoLoadRollbackPoints(), evoLoadAudit()]);
  } catch (e) {
    alert("Error aprobando propuesta: " + e.message);
  }
}

async function evoRejectProposal(id) {
  try {
    const res = await fetch(`/api/evolution/proposals/${id}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: "Rechazado desde el Workspace" }),
    });
    const d = await res.json();
    if (!d.ok) throw new Error(d.error || "error desconocido");
    document.getElementById("evo-proposal-detail").style.display = "none";
    await Promise.all([evoLoadProposals(), evoLoadOverview(), evoLoadAudit()]);
  } catch (e) {
    alert("Error rechazando propuesta: " + e.message);
  }
}

// ── Reglas constitucionales ───────────────────────────────────────
async function evoLoadRules() {
  const tbody = document.querySelector("#evo-rules-table tbody");
  try {
    const res = await fetch("/api/evolution/rules");
    const d = await res.json();
    if (!d.ok) throw new Error(d.error || "error desconocido");
    const rules = d.rules || [];
    tbody.innerHTML = rules.map((r) => `
      <tr>
        <td>${_evoEsc(r.name)}</td>
        <td>${_evoEsc(r.rule_type)}</td>
        <td>${_evoEsc(JSON.stringify(r.constraint))}</td>
        <td>${r.enabled ? "✅ activa" : "⛔ inactiva"}</td>
      </tr>`).join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="4">Error: ${_evoEsc(e.message)}</td></tr>`;
  }
}

// ── Rollback points ────────────────────────────────────────────────
async function evoLoadRollbackPoints() {
  const tbody = document.querySelector("#evo-rollback-table tbody");
  try {
    const res = await fetch("/api/evolution/rollback_points?limit=20");
    const d = await res.json();
    if (!d.ok) throw new Error(d.error || "error desconocido");
    const points = d.points || [];
    if (!points.length) {
      tbody.innerHTML = `<tr><td colspan="5">Sin rollback points todavía.</td></tr>`;
      return;
    }
    tbody.innerHTML = points.map((p) => `
      <tr>
        <td>#${_evoEsc(p.point_id)}</td>
        <td>${_evoEsc(p.component)}</td>
        <td>${_evoEsc(_evoShort(p.description, 50))}</td>
        <td>${_evoEsc((p.created_at || "").slice(0, 19))}</td>
        <td><button class="tbl-action-btn destructive" data-evo-rollback="${p.point_id}">Revertir</button></td>
      </tr>`).join("");
    tbody.querySelectorAll("[data-evo-rollback]").forEach((btn) =>
      btn.addEventListener("click", () => evoApplyRollback(parseInt(btn.dataset.evoRollback, 10)))
    );
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="5">Error: ${_evoEsc(e.message)}</td></tr>`;
  }
}

async function evoApplyRollback(pointId) {
  if (!confirm(`¿Revertir al rollback point #${pointId}? Esta acción restaura el estado guardado.`)) return;
  try {
    const res = await fetch(`/api/evolution/rollback_points/${pointId}/apply`, { method: "POST" });
    const d = await res.json();
    if (!d.ok) throw new Error(d.error || "error desconocido");
    alert(d.message);
    await Promise.all([evoLoadAudit(), evoLoadOverview()]);
  } catch (e) {
    alert("Error aplicando rollback: " + e.message);
  }
}

// ── Audit log ───────────────────────────────────────────────────────
async function evoLoadAudit() {
  const tbody = document.querySelector("#evo-audit-table tbody");
  try {
    const res = await fetch("/api/evolution/audit?limit=40");
    const d = await res.json();
    if (!d.ok) throw new Error(d.error || "error desconocido");
    const entries = d.entries || [];
    if (!entries.length) {
      tbody.innerHTML = `<tr><td colspan="5">Sin entradas en el audit log todavía.</td></tr>`;
      return;
    }
    tbody.innerHTML = entries.map((e) => `
      <tr>
        <td>${_evoEsc((e.timestamp || "").slice(0, 19))}</td>
        <td>${_evoEsc(e.action)}</td>
        <td>${_evoEsc(e.actor)}</td>
        <td>${_evoEsc(e.target)}</td>
        <td>${_evoStatusPill(e.outcome)}</td>
      </tr>`).join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="5">Error: ${_evoEsc(e.message)}</td></tr>`;
  }
}

// ── Inicialización de la sección ─────────────────────────────────
async function evolutionCenterInit() {
  document.getElementById("evo-run-cycle-btn").addEventListener("click", evoRunCycle);
  document.getElementById("evo-proposals-filter").addEventListener("change", evoLoadProposals);
  await Promise.all([
    evoLoadOverview(),
    evoLoadTimeline(),
    evoLoadPerformanceHistory(),
    evoLoadProposals(),
    evoLoadRules(),
    evoLoadRollbackPoints(),
    evoLoadAudit(),
  ]);
}

document.addEventListener("DOMContentLoaded", () => {
  const evoNav = document.querySelector('.nav-item[data-section="evolution"]');
  if (evoNav) {
    let initialized = false;
    evoNav.addEventListener("click", () => {
      if (!initialized) { initialized = true; evolutionCenterInit(); }
    });
  }
});
