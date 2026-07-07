// ASTRA Workspace — frontend (Roadmap IV, Secciones 1-3)

// ── 1.2 Navegación entre ramas ────────────────────────────────────
const navItems = document.querySelectorAll(".nav-item");
const panels = document.querySelectorAll(".panel");

navItems.forEach((btn) => {
  btn.addEventListener("click", () => {
    navItems.forEach((b) => b.classList.remove("active"));
    panels.forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`panel-${btn.dataset.section}`).classList.add("active");
  });
});

// ── 1.1 Barra de estado superior — polling real a /api/status ─────
async function refreshStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();

    const dot = document.getElementById("astra-status-dot");
    const label = document.getElementById("astra-status-label");
    dot.classList.remove("online", "offline");
    dot.classList.add(data.connected ? "online" : "offline");
    label.textContent = data.connected ? "en línea" : "sin API key";

    document.getElementById("chip-project").textContent =
      "Proyecto: " + (data.active_project || "ninguno");
    document.getElementById("chip-model").textContent = "Modelo: " + data.model;
    document.getElementById("chip-tools").textContent = "Tools: " + data.tools_loaded;
  } catch (e) {
    const dot = document.getElementById("astra-status-dot");
    dot.classList.remove("online");
    dot.classList.add("offline");
    document.getElementById("astra-status-label").textContent = "sin conexión al servidor";
  }
}

function tickClock() {
  const now = new Date();
  document.getElementById("chip-clock").textContent = now.toLocaleTimeString();
}

// ── 2.1 Barra de estado permanente — polling real a /api/telemetry ─
async function refreshTelemetry() {
  try {
    const res = await fetch("/api/telemetry");
    const d = await res.json();

    document.getElementById("stat-cpu").textContent =
      "CPU " + (d.cpu_percent != null ? d.cpu_percent.toFixed(1) + "%" : "n/d");
    document.getElementById("stat-ram").textContent =
      "RAM " + (d.ram_percent != null ? d.ram_percent.toFixed(1) + "%" : "n/d");
    document.getElementById("stat-gpu").textContent =
      "GPU " + (d.gpu_available ? d.gpu_percent.toFixed(1) + "%" : "no disponible");

    document.getElementById("stat-engine").textContent =
      `Active Engine: ${d.active_engine.watchers_activos} watchers / ${d.active_engine.jobs_programados} jobs`;
    document.getElementById("stat-cognitive").textContent =
      `Cognitive Core: ${d.cognitive_core.memoria_total} memorias`;
    document.getElementById("stat-evolution").textContent =
      `Evolution: ${d.evolution_engine.eventos_totales} eventos / ${d.evolution_engine.propuestas_pendientes} pendientes`;

    document.getElementById("stat-requests").textContent = `Peticiones: ${d.api_request_count}`;
    document.getElementById("stat-avgtime").textContent =
      "Prom.: " + (d.avg_response_time_ms != null ? d.avg_response_time_ms + " ms" : "—");
  } catch (e) {
    document.getElementById("stat-cpu").textContent = "sin conexión";
  }
}

refreshStatus();
refreshTelemetry();
setInterval(refreshStatus, 10000);
setInterval(refreshTelemetry, 5000);
tickClock();
setInterval(tickClock, 1000);

// ── 3.2 Historial y gestión de conversación ───────────────────────
const chatWindow = document.getElementById("chat-window");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");

function appendMsg(text, who, meta) {
  const wrap = document.createElement("div");
  wrap.className = `chat-msg-wrap ${who}`;

  const bubble = document.createElement("div");
  bubble.className = `chat-msg ${who}`;
  bubble.textContent = text;
  wrap.appendChild(bubble);

  // 3.3 — Metadatos de respuesta (módulo + tiempo de ejecución) + copiar (3.2)
  const metaRow = document.createElement("div");
  metaRow.className = "chat-meta";

  if (who === "astra" && meta) {
    const label = document.createElement("span");
    label.textContent = `${meta.module || "ASTRA"} · ${meta.elapsed_ms != null ? meta.elapsed_ms + " ms" : ""}`;
    metaRow.appendChild(label);
  }

  const copyBtn = document.createElement("button");
  copyBtn.textContent = "Copiar";
  copyBtn.addEventListener("click", () => {
    navigator.clipboard.writeText(text).then(() => {
      copyBtn.textContent = "¡Copiado!";
      setTimeout(() => (copyBtn.textContent = "Copiar"), 1500);
    });
  });
  metaRow.appendChild(copyBtn);
  wrap.appendChild(metaRow);

  chatWindow.appendChild(wrap);
  chatWindow.scrollTop = chatWindow.scrollHeight;
  return bubble;
}

async function loadHistory() {
  try {
    const res = await fetch("/api/chat/history?limit=20");
    const data = await res.json();
    (data.turns || []).forEach((t) => {
      appendMsg(t.content, t.role === "user" ? "user" : "astra", null);
    });
  } catch (e) {
    // sin historial disponible — no es crítico, se empieza con chat vacío
  }
}
loadHistory();

// ── 3.2 Exportar conversación ──────────────────────────────────────
document.getElementById("export-btn").addEventListener("click", () => {
  const lines = [];
  chatWindow.querySelectorAll(".chat-msg-wrap").forEach((wrap) => {
    const who = wrap.classList.contains("user") ? "Tú" : "ASTRA";
    const text = wrap.querySelector(".chat-msg").textContent;
    lines.push(`${who}: ${text}`);
  });
  const blob = new Blob([lines.join("\n\n")], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `astra_conversacion_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.txt`;
  a.click();
  URL.revokeObjectURL(url);
});

// ── 3.1 Entrada enriquecida: adjuntar archivo / carpeta / drag&drop ─
let pendingAttachment = null; // { filename, path }
const attachPreview = document.getElementById("attach-preview");
const fileInput = document.getElementById("file-input");
const folderInput = document.getElementById("folder-input");

function setAttachment(info) {
  pendingAttachment = info;
  if (info) {
    attachPreview.style.display = "block";
    attachPreview.textContent = `📎 Adjunto listo: ${info.path} (${info.size} bytes) — se referenciará en tu próximo mensaje`;
  } else {
    attachPreview.style.display = "none";
    attachPreview.textContent = "";
  }
}

async function uploadFile(file) {
  const formData = new FormData();
  formData.append("file", file);
  try {
    const res = await fetch("/api/upload", { method: "POST", body: formData });
    const data = await res.json();
    setAttachment(data);
  } catch (e) {
    appendMsg("No se pudo subir el archivo.", "astra", null);
  }
}

document.getElementById("attach-file-btn").addEventListener("click", () => fileInput.click());
document.getElementById("attach-folder-btn").addEventListener("click", () => folderInput.click());

fileInput.addEventListener("change", () => {
  if (fileInput.files.length) uploadFile(fileInput.files[0]);
  fileInput.value = "";
});

folderInput.addEventListener("change", () => {
  // El navegador entrega todos los archivos de la carpeta; subimos el primero
  // relevante (o todos secuencialmente) — mantenemos simple: subir todos.
  Array.from(folderInput.files).forEach((f) => uploadFile(f));
  folderInput.value = "";
});

// Drag & drop directo sobre la ventana de chat
["dragenter", "dragover"].forEach((evt) =>
  chatWindow.addEventListener(evt, (e) => {
    e.preventDefault();
    chatWindow.classList.add("drag-over");
  })
);
["dragleave", "drop"].forEach((evt) =>
  chatWindow.addEventListener(evt, (e) => {
    e.preventDefault();
    chatWindow.classList.remove("drag-over");
  })
);
chatWindow.addEventListener("drop", (e) => {
  const files = e.dataTransfer.files;
  if (files.length) uploadFile(files[0]);
});

// ── Envío de mensajes — puente real a /api/chat (dispatch_command) ─
chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  let msg = chatInput.value.trim();
  if (!msg && !pendingAttachment) return;

  if (pendingAttachment) {
    msg = msg ? `${msg} ${pendingAttachment.path}` : pendingAttachment.path;
  }

  appendMsg(msg, "user", null);
  chatInput.value = "";
  setAttachment(null);

  const pending = appendMsg("…", "astra", null);

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg }),
    });
    const data = await res.json();
    pending.textContent = data.response || "(sin respuesta)";
    const metaRow = pending.parentElement.querySelector(".chat-meta");
    const label = document.createElement("span");
    label.textContent = `${data.module || "ASTRA"} · ${data.elapsed_ms != null ? data.elapsed_ms + " ms" : ""}`;
    metaRow.prepend(label);
  } catch (err) {
    pending.textContent = "Error de conexión con el servidor ASTRA.";
  }
});
