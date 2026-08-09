/**
 * deployment_reports.js — Panel de Deployment Reports del Workspace
 * Permite ver historial, descargar y ejecutar validaciones del First Deployment Experience.
 */

(function() {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const apiBase = '';

  // ── Utilidades ──────────────────────────────────────────────
  function statusBadge(status) {
    const colors = {
      'pass': 'color:#27ae60;font-weight:bold',
      'PASS': 'color:#27ae60;font-weight:bold',
      'fail': 'color:#e74c3c;font-weight:bold',
      'FAIL': 'color:#e74c3c;font-weight:bold',
      'warn': 'color:#f39c12;font-weight:bold',
      'WARN': 'color:#f39c12;font-weight:bold',
      'partial': 'color:#f39c12;font-weight:bold',
      'PARTIAL': 'color:#f39c12;font-weight:bold',
      'SUCCESS': 'color:#27ae60;font-weight:bold',
      'FAILED': 'color:#e74c3c;font-weight:bold',
      'READY FOR PRODUCTION': 'color:#27ae60;font-weight:bold',
      'READY WITH WARNINGS': 'color:#f39c12;font-weight:bold',
      'NOT READY': 'color:#e74c3c;font-weight:bold',
      'skip': 'color:#95a5a6',
      'SKIP': 'color:#95a5a6',
    };
    const style = colors[status] || 'color:inherit';
    return `<span style="${style}">${status}</span>`;
  }

  async function fetchJSON(url, options) {
    const r = await fetch(url, options);
    return { ok: r.ok, status: r.status, data: await r.json() };
  }

  // ── Cargar resumen ───────────────────────────────────────────
  async function loadSummary() {
    try {
      const { data } = await fetchJSON(`${apiBase}/api/deployment/summary`);
      const cards = $('deploy-global-status');
      if (!cards) return;

      const depStatus = data.latest_deployment?.summary || 'Sin informes';
      const readyStatus = data.latest_readiness?.summary || 'Sin informes';

      cards.innerHTML = `
        <div class="lab-card" style="text-align:center;">
          <div style="font-size:0.78rem;color:#888;">Deployment</div>
          <div style="font-size:1.2rem;margin-top:0.3rem;">${statusBadge(data.latest_deployment?.global_status || 'N/A')}</div>
        </div>
        <div class="lab-card" style="text-align:center;">
          <div style="font-size:0.78rem;color:#888;">Readiness</div>
          <div style="font-size:1.2rem;margin-top:0.3rem;">${statusBadge(data.latest_readiness?.global_status || 'N/A')}</div>
        </div>
        <div class="lab-card" style="text-align:center;">
          <div style="font-size:0.78rem;color:#888;">Pipeline Reports</div>
          <div style="font-size:1.5rem;margin-top:0.3rem;">${data.pipeline_reports}</div>
        </div>
        <div class="lab-card" style="text-align:center;">
          <div style="font-size:0.78rem;color:#888;">Total Informes</div>
          <div style="font-size:1.5rem;margin-top:0.3rem;">${data.all_reports?.length || 0}</div>
        </div>
      `;

      // Tabla de informes
      const tbody = $('deploy-reports-table')?.querySelector('tbody');
      if (tbody && data.all_reports) {
        tbody.innerHTML = data.all_reports.slice(0, 20).map(r => {
          const date = r.created_at ? new Date(r.created_at).toLocaleString() : 'N/A';
          const sym = r.symbol || '-';
          const summary = r.summary || '-';
          return `<tr>
            <td>${r.type || '-'}</td>
            <td>${sym}</td>
            <td>${statusBadge(r.summary?.split(':')[0] || '-')}</td>
            <td>${summary}</td>
            <td style="font-size:0.78rem;">${date}</td>
            <td><button class="train-btn" style="padding:0.2rem 0.6rem;font-size:0.75rem;" onclick="window.DeploymentReports.showReport('${r.filename}')">Ver</button></td>
          </tr>`;
        }).join('') || '<tr><td colspan="6">No hay informes disponibles</td></tr>';
      }
    } catch (e) {
      console.error('Error loading deployment summary:', e);
    }
  }

  // ── Ver contenido de un informe ──────────────────────────────
  async function showReport(filename) {
    try {
      const { data } = await fetchJSON(`${apiBase}/api/deployment/reports/${filename}`);
      const contentDiv = $('deploy-report-content');
      const titleEl = $('deploy-report-title');
      if (contentDiv) {
        contentDiv.textContent = data.content || 'No se pudo cargar el contenido';
        titleEl.textContent = `Informe: ${filename}`;
      }
    } catch (e) {
      console.error('Error showing report:', e);
    }
  }

  // ── Ver informe mas reciente por tipo ────────────────────────
  async function showLatest(reportType) {
    try {
      const { data } = await fetchJSON(`${apiBase}/api/deployment/latest/${reportType}`);
      const contentDiv = $('deploy-report-content');
      const titleEl = $('deploy-report-title');
      if (contentDiv) {
        contentDiv.textContent = data.content || 'No hay informes de este tipo';
        titleEl.textContent = `Informe mas reciente (${reportType})`;
      }
    } catch (e) {
      console.error('Error showing latest report:', e);
    }
  }

  // ── Ejecutar validacion completa ──────────────────────────────
  async function runFull() {
    const btn = $('deploy-run-full');
    const status = $('deploy-run-status');
    if (btn) btn.disabled = true;
    if (status) status.textContent = 'Ejecutando... (esto puede tardar varios minutos)';

    try {
      const { data } = await fetchJSON(`${apiBase}/api/deployment/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ timeframe: 'H4' }),
      });

      if (data.error) {
        if (status) status.textContent = `Error: ${data.error}`;
      } else {
        if (status) status.innerHTML = `Completo: Deployment ${statusBadge(data.deployment_status)} | Readiness ${statusBadge(data.readiness_status)}`;
        loadSummary();
      }
    } catch (e) {
      if (status) status.textContent = `Error: ${e}`;
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  // ── Ejecutar solo readiness ───────────────────────────────────
  async function runReadiness() {
    const btn = $('deploy-run-readiness');
    const status = $('deploy-run-status');
    if (btn) btn.disabled = true;
    if (status) status.textContent = 'Ejecutando readiness check...';

    try {
      const { data } = await fetchJSON(`${apiBase}/api/deployment/run-readiness`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      if (data.error) {
        if (status) status.textContent = `Error: ${data.error}`;
      } else {
        if (status) status.innerHTML = `Readiness: ${statusBadge(data.status)}`;
        loadSummary();
      }
    } catch (e) {
      if (status) status.textContent = `Error: ${e}`;
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  // ── Exponer API publica ───────────────────────────────────────
  window.DeploymentReports = {
    showReport,
    showLatest,
    loadSummary,
    runFull,
    runReadiness,
  };

  // ── Inicializar cuando el DOM este listo ─────────────────────
  function init() {
    const refreshBtn = $('deploy-refresh-btn');
    if (refreshBtn) refreshBtn.addEventListener('click', loadSummary);

    const runFullBtn = $('deploy-run-full');
    if (runFullBtn) runFullBtn.addEventListener('click', runFull);

    const runReadyBtn = $('deploy-run-readiness');
    if (runReadyBtn) runReadyBtn.addEventListener('click', runReadiness);

    const showDepBtn = $('deploy-show-deployment');
    if (showDepBtn) showDepBtn.addEventListener('click', () => showLatest('deployment'));

    const showReadyBtn = $('deploy-show-readiness');
    if (showReadyBtn) showReadyBtn.addEventListener('click', () => showLatest('readiness'));

    // Cargar datos iniciales
    loadSummary();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
