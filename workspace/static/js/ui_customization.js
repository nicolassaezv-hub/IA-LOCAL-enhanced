/* ═══════════════════════════════════════════════════════════
   VI.9 — ASTRA Workplace UI Customization
   Command Palette · Hacker Mode · Glow · RGB · Sounds · Fullscreen
   ═══════════════════════════════════════════════════════════ */
(function () {
  "use strict";
  const LS_KEY = "astra.ui.v1";
  const state = Object.assign({
    hacker: false, glow: false, accent: "#00d4ff", sounds: true,
  }, JSON.parse(localStorage.getItem(LS_KEY) || "{}"));

  const save = () => localStorage.setItem(LS_KEY, JSON.stringify(state));

  // ── Sound engine (no external files) ──
  const AC = window.AudioContext || window.webkitAudioContext;
  let actx = null;
  function beep(freq = 660, dur = 0.08, type = "sine", vol = 0.05) {
    if (!state.sounds) return;
    try {
      actx = actx || new AC();
      const o = actx.createOscillator(), g = actx.createGain();
      o.type = type; o.frequency.value = freq;
      g.gain.value = vol;
      o.connect(g); g.connect(actx.destination);
      o.start(); o.stop(actx.currentTime + dur);
    } catch (e) {}
  }
  const sfx = {
    click:   () => beep(880, .05, "square", .03),
    success: () => { beep(660,.08); setTimeout(()=>beep(990,.10),90); },
    error:   () => beep(180, .18, "sawtooth", .06),
    open:    () => beep(520, .06, "triangle", .04),
  };

  // ── Apply styles from state ──
  function apply() {
    document.body.classList.toggle("astra-hacker", state.hacker);
    document.body.classList.toggle("astra-glow",   state.glow);
    document.documentElement.style.setProperty("--astra-accent", state.accent);
    document.documentElement.style.setProperty(
      "--astra-glow",
      `0 0 10px ${state.accent}, 0 0 20px ${state.accent}`);
  }

  // ── Command palette ──
  const CMDS = [
    { id: "nav.dashboard",  name: "Ir a Dashboard",           run: () => go("dashboard") },
    { id: "nav.forex",      name: "Ir a Forex Lab",            run: () => go("forex") },
    { id: "nav.prediction", name: "Ir a Prediction Lab",       run: () => go("prediction") },
    { id: "nav.business",   name: "Ir a Business Lab",         run: () => go("business") },
    { id: "nav.cognitive",  name: "Ir a Cognitive Center",     run: () => go("cognitive") },
    { id: "nav.evolution",  name: "Ir a Evolution Center",     run: () => go("evolution") },
    { id: "nav.activity",   name: "Ir a Activity Center",      run: () => go("activity") },
    { id: "nav.notifs",     name: "Ir a Notification Center",  run: () => go("notifications") },
    { id: "nav.thinking",   name: "Ir a Live Thinking",        run: () => go("thinking") },
    { id: "sys.selftest",   name: "Ejecutar self_test",        run: () => runCmd("self_test") },
    { id: "sys.scan",       name: "Escanear oportunidades",    run: () => runCmd("scan_opportunities") },
    { id: "ui.hacker",      name: "Alternar Modo Hacker",      run: () => { state.hacker = !state.hacker; save(); apply(); } },
    { id: "ui.glow",        name: "Alternar Efecto Glow",      run: () => { state.glow = !state.glow; save(); apply(); } },
    { id: "ui.fullscreen",  name: "Pantalla completa",         run: () => toggleFullscreen() },
    { id: "ui.panel",       name: "Abrir panel personalización",run: () => togglePanel(true) },
  ];

  function go(section) {
    const el = document.querySelector(`[data-section="${section}"], #tab-${section}, [data-tab="${section}"]`);
    if (el && el.click) el.click();
    else window.dispatchEvent(new CustomEvent("astra:navigate", { detail: { section } }));
  }
  function runCmd(cmd) {
    fetch("/api/command", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command: cmd }),
    }).then(r => r.ok ? sfx.success() : sfx.error()).catch(() => sfx.error());
  }
  function toggleFullscreen() {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
    else document.exitFullscreen?.();
  }

  // ── Build palette DOM ──
  let paletteEl, inputEl, listEl, activeIdx = 0, filtered = CMDS;
  function buildPalette() {
    paletteEl = document.createElement("div");
    paletteEl.id = "astra-cmd-palette";
    paletteEl.innerHTML = `
      <div id="astra-cmd-panel">
        <input id="astra-cmd-input" placeholder="Escribe un comando…  (Ctrl+Shift+P)" />
        <div id="astra-cmd-list"></div>
      </div>`;
    document.body.appendChild(paletteEl);
    inputEl = paletteEl.querySelector("#astra-cmd-input");
    listEl  = paletteEl.querySelector("#astra-cmd-list");
    paletteEl.addEventListener("click", e => { if (e.target === paletteEl) closePalette(); });
    inputEl.addEventListener("input", renderList);
    inputEl.addEventListener("keydown", onKey);
  }
  function renderList() {
    const q = (inputEl.value || "").toLowerCase();
    filtered = CMDS.filter(c => c.name.toLowerCase().includes(q));
    activeIdx = 0;
    listEl.innerHTML = filtered.map((c, i) =>
      `<div class="astra-cmd-item ${i===activeIdx?'active':''}" data-i="${i}">
         <span>${c.name}</span><small>${c.id}</small></div>`
    ).join("") || `<div class="astra-cmd-item"><small>Sin resultados</small></div>`;
    listEl.querySelectorAll(".astra-cmd-item").forEach(el =>
      el.addEventListener("click", () => execIdx(parseInt(el.dataset.i))));
  }
  function onKey(e) {
    if (e.key === "Escape") return closePalette();
    if (e.key === "Enter")  { e.preventDefault(); return execIdx(activeIdx); }
    if (e.key === "ArrowDown") { e.preventDefault(); activeIdx = Math.min(activeIdx+1, filtered.length-1); return refreshActive(); }
    if (e.key === "ArrowUp")   { e.preventDefault(); activeIdx = Math.max(activeIdx-1, 0);                return refreshActive(); }
  }
  function refreshActive() {
    listEl.querySelectorAll(".astra-cmd-item").forEach((el,i) =>
      el.classList.toggle("active", i===activeIdx));
  }
  function execIdx(i) {
    const c = filtered[i]; if (!c) return;
    closePalette(); sfx.click();
    try { c.run(); } catch (e) { sfx.error(); }
  }
  function openPalette() {
    if (!paletteEl) buildPalette();
    paletteEl.classList.add("open");
    inputEl.value = ""; renderList(); inputEl.focus(); sfx.open();
  }
  function closePalette() { paletteEl?.classList.remove("open"); }

  // ── Customization panel ──
  const PALETTES = ["#00d4ff","#00ff66","#ff3860","#ffdd57","#b967ff","#ff9f43","#ffffff"];
  let panelEl;
  function buildPanel() {
    panelEl = document.createElement("div");
    panelEl.id = "astra-ui-panel";
    panelEl.innerHTML = `
      <h4>Personalización</h4>
      <label><input type="checkbox" id="ui-hacker" ${state.hacker?'checked':''}/> Modo Hacker (Ctrl+Shift+H)</label>
      <label><input type="checkbox" id="ui-glow"   ${state.glow?'checked':''}/> Efecto Glow</label>
      <label><input type="checkbox" id="ui-sounds" ${state.sounds?'checked':''}/> Sonidos</label>
      <label>Color acento</label>
      <div class="astra-palette-row" id="ui-palette"></div>
      <label>Color RGB: <input type="color" id="ui-color" value="${state.accent}"/></label>
      <label><button id="ui-fullscreen" style="width:100%;margin-top:6px">Pantalla completa (F11)</button></label>
      <label><small>Command Palette: Ctrl+Shift+P</small></label>`;
    document.body.appendChild(panelEl);

    const pal = panelEl.querySelector("#ui-palette");
    PALETTES.forEach(c => {
      const s = document.createElement("div");
      s.className = "astra-swatch" + (c === state.accent ? " selected" : "");
      s.style.background = c;
      s.addEventListener("click", () => {
        state.accent = c; save(); apply();
        pal.querySelectorAll(".astra-swatch").forEach(el => el.classList.remove("selected"));
        s.classList.add("selected");
        panelEl.querySelector("#ui-color").value = c;
        sfx.click();
      });
      pal.appendChild(s);
    });
    panelEl.querySelector("#ui-hacker").addEventListener("change", e => { state.hacker = e.target.checked; save(); apply(); });
    panelEl.querySelector("#ui-glow").addEventListener("change",   e => { state.glow   = e.target.checked; save(); apply(); });
    panelEl.querySelector("#ui-sounds").addEventListener("change", e => { state.sounds = e.target.checked; save(); });
    panelEl.querySelector("#ui-color").addEventListener("input",   e => { state.accent = e.target.value; save(); apply(); });
    panelEl.querySelector("#ui-fullscreen").addEventListener("click", toggleFullscreen);
  }
  function togglePanel(force) {
    if (!panelEl) buildPanel();
    const open = typeof force === "boolean" ? force : !panelEl.classList.contains("open");
    panelEl.classList.toggle("open", open);
  }

  // ── Floating toggle button ──
  function buildToggle() {
    const b = document.createElement("button");
    b.id = "astra-ui-toggle"; b.textContent = "⚙";
    b.title = "Personalización (Ctrl+Shift+P para comandos)";
    b.addEventListener("click", () => { sfx.click(); togglePanel(); });
    document.body.appendChild(b);
  }

  // ── Global hotkeys ──
  document.addEventListener("keydown", e => {
    if (e.ctrlKey && e.shiftKey && (e.key === "P" || e.key === "p")) { e.preventDefault(); openPalette(); }
    if (e.ctrlKey && e.shiftKey && (e.key === "H" || e.key === "h")) {
      e.preventDefault(); state.hacker = !state.hacker; save(); apply(); sfx.click();
    }
    if (e.key === "F11") { e.preventDefault(); toggleFullscreen(); }
  });

  // Expose small API
  window.AstraUI = {
    openPalette, closePalette, togglePanel,
    setHacker: v => { state.hacker = !!v; save(); apply(); },
    setGlow:   v => { state.glow   = !!v; save(); apply(); },
    setAccent: c => { state.accent = c;   save(); apply(); },
    sfx,
  };

  // Init
  document.addEventListener("DOMContentLoaded", () => {
    apply(); buildToggle();
  });
})();
