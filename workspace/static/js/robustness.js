// ── Robustness Center ─────────────────────────────────────────────────
(async function() {
  'use strict';

  async function api(path) {
    try {
      const r = await fetch(path);
      if (!r.ok) return null;
      return await r.json();
    } catch { return null; }
  }

  function statusIcon(s) {
    return s === 'pass' || s === 'ok' ? '\u2713' : s === 'fail' || s === 'error' || s === 'blocked' ? '\u2717' : '\u26a0';
  }

  function statusColor(s) {
    return s === 'pass' || s === 'ok' ? '#4caf50' : s === 'fail' || s === 'error' || s === 'blocked' ? '#f44336' : '#ff9800';
  }

  async function loadDependency() {
    const data = await api('/api/robustness/dependency-check');
    if (!data) return;
    const tbody = document.querySelector('#robust-dep-table tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    (data.checks || []).forEach(c => {
      tbody.innerHTML += '<tr><td>' + c.category + '</td><td>' + c.name + '</td>' +
        '<td style="color:' + statusColor(c.status) + ';font-weight:bold;">' + statusIcon(c.status) + ' ' + c.status + '</td>' +
        '<td style="font-size:0.85em;">' + c.detail + (c.recommendation ? '<br><small>\u2192 ' + c.recommendation + '</small>' : '') + '</td></tr>';
    });
  }

  async function loadData() {
    const data = await api('/api/robustness/data-integrity');
    if (!data) return;
    const tbody = document.querySelector('#robust-data-table tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    (data.results || []).forEach(r => {
      const issues = (r.issues || []).map(i => i.severity + ': ' + i.detail).join('; ');
      tbody.innerHTML += '<tr><td>' + r.pair + '</td><td>' + r.timeframe + '</td><td>' + r.rows + '</td>' +
        '<td style="color:' + statusColor(r.status) + ';">' + statusIcon(r.status) + ' ' + r.status + '</td>' +
        '<td style="font-size:0.85em;">' + (issues || '\u2014') + '</td></tr>';
    });
  }

  async function loadModels() {
    const data = await api('/api/robustness/model-integrity');
    if (!data) return;
    const tbody = document.querySelector('#robust-models-table tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    (data.checks || []).forEach(c => {
      tbody.innerHTML += '<tr><td>' + c.symbol + '</td>' +
        '<td style="color:' + statusColor(c.status) + ';font-weight:bold;">' + statusIcon(c.status) + ' ' + c.status + '</td>' +
        '<td style="font-size:0.85em;">' + ((c.issues || []).join('; ') || '\u2014') + '</td>' +
        '<td style="font-size:0.85em;">' + (c.recovery_action || '\u2014') + '</td></tr>';
    });
  }

  async function loadRecovery() {
    const data = await api('/api/robustness/recovery-history?limit=20');
    if (!data) return;
    const tbody = document.querySelector('#robust-recovery-table tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    (data.events || []).forEach(e => {
      tbody.innerHTML += '<tr><td style="font-size:0.8em;">' + e.timestamp + '</td>' +
        '<td>' + e.component + '</td><td>' + e.incident_type + '</td>' +
        '<td style="color:' + statusColor(e.recovery_status === 'success' ? 'ok' : 'warn') + ';">' + e.recovery_status + '</td></tr>';
    });
  }

  async function loadBenchmark() {
    const data = await api('/api/robustness/benchmark?limit=50');
    if (!data) return;
    const tbody = document.querySelector('#robust-benchmark-table tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    Object.entries(data.stats || {}).forEach(([stage, s]) => {
      tbody.innerHTML += '<tr><td>' + stage + '</td>' +
        '<td>' + (s.avg || 0).toFixed(3) + '</td>' +
        '<td>' + (s.max || 0).toFixed(3) + '</td>' +
        '<td>' + (s.count || 0) + '</td></tr>';
    });
  }

  async function loadSummary() {
    const data = await api('/api/robustness/all');
    if (!data) return;
    const cards = document.getElementById('robust-summary-cards');
    if (!cards) return;
    const dep = data.dependency || {};
    const di = data.data_integrity || {};
    const mi = data.model_integrity || {};
    const pv = data.provider || {};
    cards.innerHTML =
      '<div class="stat-card"><div class="stat-label">Dependencies</div>' +
      '<div class="stat-value" style="color:' + (dep.ready ? '#4caf50' : '#f44336') + '">' + (dep.ready ? 'READY' : 'BLOCKED') + '</div>' +
      '<div class="stat-sub">' + (dep.blocking_count || 0) + ' blocking, ' + (dep.warning_count || 0) + ' warnings</div></div>' +
      '<div class="stat-card"><div class="stat-label">Data Integrity</div>' +
      '<div class="stat-value" style="color:' + ((di.err || 0) === 0 ? '#4caf50' : '#f44336') + '">' + (di.ok || 0) + '/' + (di.total || 0) + '</div>' +
      '<div class="stat-sub">' + (di.warn || 0) + ' warnings, ' + (di.err || 0) + ' errors</div></div>' +
      '<div class="stat-card"><div class="stat-label">Models</div>' +
      '<div class="stat-value" style="color:' + ((mi.blocked || 0) === 0 ? '#4caf50' : '#f44336') + '">' + (mi.ok || 0) + '/' + (mi.total || 0) + '</div>' +
      '<div class="stat-sub">' + (mi.blocked || 0) + ' blocked</div></div>' +
      '<div class="stat-card"><div class="stat-label">Provider</div>' +
      '<div class="stat-value">' + (pv.name || '\u2014') + '</div>' +
      '<div class="stat-sub">' + (pv.status || '\u2014') + '</div></div>';
  }

  async function loadAll() {
    await Promise.all([loadSummary(), loadDependency(), loadData(), loadModels(), loadRecovery(), loadBenchmark()]);
  }

  var runBtn = document.getElementById('robust-run-all');
  if (runBtn) {
    runBtn.addEventListener('click', async () => {
      var status = document.getElementById('robust-run-status');
      if (status) status.textContent = 'Running...';
      try {
        await fetch('/api/robustness/all');
        await loadAll();
        if (status) status.textContent = 'Done \u2713';
      } catch (e) {
        if (status) status.textContent = 'Error';
      }
    });
  }

  var refreshBtn = document.getElementById('robust-refresh-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', loadAll);
  }

  var navItems = document.querySelectorAll('.nav-item[data-section="robustness"]');
  navItems.forEach(item => { item.addEventListener('click', loadAll); });

  loadAll();
})();
