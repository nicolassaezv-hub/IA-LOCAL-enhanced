// ASTRA Workspace — Notification Center (Roadmap IV, Sección 10)
// Campana en la topbar (visible desde cualquier sección) con dropdown de
// notificaciones PERSISTIDAS (predicciones listas, entrenamientos
// completados, problemas detectados, análisis de Business Lab listos).
// Distinto del Activity Center: esto sobrevive a un reinicio del server.

function _notifEsc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

const _notifTypeIcons = {
  training_completed: "🏋️",
  prediction_ready: "🔮",
  problem_detected: "⚠️",
  business_analysis_ready: "📊",
  system_update: "🛰️",
};

let _notifPollTimer = null;
let _notifDropdownOpen = false;

async function notifRefreshBadge() {
  try {
    const res = await fetch("/api/notifications/stats");
    const d = await res.json();
    const badge = document.getElementById("notif-unread-badge");
    if (!d.ok) return;
    if (d.unread > 0) {
      badge.style.display = "inline-block";
      badge.textContent = d.unread > 99 ? "99+" : String(d.unread);
    } else {
      badge.style.display = "none";
    }
  } catch (e) {
    console.error("notifRefreshBadge", e);
  }
}

async function notifRenderList() {
  const list = document.getElementById("notif-dropdown-list");
  try {
    const res = await fetch("/api/notifications?limit=25");
    const d = await res.json();
    if (!d.ok) throw new Error(d.error || "error desconocido");
    if (!d.items.length) {
      list.innerHTML = `<div class="notif-empty">Sin notificaciones todavía.</div>`;
      return;
    }
    list.innerHTML = d.items.map((n) => `
      <div class="notif-item ${n.is_read ? "" : "unread"}" data-id="${n.id}">
        <div class="notif-item-title">
          <span class="notif-item-dot"></span>
          ${_notifTypeIcons[n.ntype] || "•"} ${_notifEsc(n.title)}
        </div>
        ${n.message ? `<div class="notif-item-msg">${_notifEsc(n.message)}</div>` : ""}
        <div class="notif-item-ts">${_notifEsc(n.created_at)}</div>
      </div>`).join("");
    list.querySelectorAll(".notif-item").forEach((el) => {
      el.addEventListener("click", async () => {
        const id = el.getAttribute("data-id");
        await fetch(`/api/notifications/${id}/read`, { method: "POST" });
        el.classList.remove("unread");
        notifRefreshBadge();
      });
    });
  } catch (e) {
    list.innerHTML = `<div class="notif-empty">Error cargando notificaciones: ${_notifEsc(e.message)}</div>`;
  }
}

function notifToggleDropdown() {
  const dd = document.getElementById("notif-dropdown");
  _notifDropdownOpen = !_notifDropdownOpen;
  dd.style.display = _notifDropdownOpen ? "block" : "none";
  if (_notifDropdownOpen) notifRenderList();
}

async function notifMarkAllRead() {
  await fetch("/api/notifications/read-all", { method: "POST" });
  await notifRenderList();
  await notifRefreshBadge();
}

function notificationCenterInit() {
  document.getElementById("notif-bell-btn").addEventListener("click", (e) => {
    e.stopPropagation();
    notifToggleDropdown();
  });
  document.getElementById("notif-markall-btn").addEventListener("click", (e) => {
    e.stopPropagation();
    notifMarkAllRead();
  });
  document.getElementById("notif-dropdown").addEventListener("click", (e) => e.stopPropagation());
  document.addEventListener("click", () => {
    if (_notifDropdownOpen) {
      _notifDropdownOpen = false;
      document.getElementById("notif-dropdown").style.display = "none";
    }
  });
  notifRefreshBadge();
  _notifPollTimer = setInterval(notifRefreshBadge, 8000);
}

document.addEventListener("DOMContentLoaded", notificationCenterInit);
