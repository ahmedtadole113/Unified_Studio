import React, { useEffect, useState } from 'react';
import { Activity, ExternalLink, Play, RefreshCw, Search } from 'lucide-react';
import { apiFetch, API_V1 } from '../api/client';

export default function ObservabilityView() {
  const [subTab, setSubTab] = useState('metrics');
  const [obs, setObs] = useState(null);
  const [promql, setPromql] = useState('sum(ues_container_memory_mb)');
  const [promqlResult, setPromqlResult] = useState(null);
  const [logContainer, setLogContainer] = useState('all');
  const [logSearch, setLogSearch] = useState('');
  const [logs, setLogs] = useState([]);
  const [logSource, setLogSource] = useState('');
  const [splQuery, setSplQuery] = useState('index=app_logs | stats count by service');
  const [splResult, setSplResult] = useState(null);
  const [traces, setTraces] = useState({ otel_spans: [], tempo_traces: [] });

  const loadMetrics = async () => {
    try {
      const res = await apiFetch(`${API_V1}/metrics/overview`);
      setObs(res);
    } catch (err) {
      console.error(err);
    }
  };

  const loadLogs = async () => {
    const res = await apiFetch(`${API_V1}/logs/search?container=${encodeURIComponent(logContainer)}&search=${encodeURIComponent(logSearch)}`);
    setLogs(res.logs || []);
    setLogSource(res.source || '');
  };

  const loadTraces = async () => {
    const res = await apiFetch(`${API_V1}/traces?limit=40`);
    setTraces(res);
  };

  useEffect(() => {
    loadMetrics();
    loadLogs();
    loadTraces();
  }, []);

  const runPromQL = async () => {
    const res = await apiFetch(`${API_V1}/metrics/promql?expr=${encodeURIComponent(promql)}`);
    setPromqlResult(res);
  };

  const runSPL = async () => {
    const res = await apiFetch(`${API_V1}/logs/spl?q=${encodeURIComponent(splQuery)}`);
    setSplResult(res);
  };

  return (
    <div className="view-container">
      <div className="section-header">
        <div>
          <h2 className="section-title"><Activity size={18} style={{ color: 'var(--apple-mint)' }} /> Centralized Observability</h2>
          <p className="section-subtitle">Prometheus Metrics & PromQL · Grafana Dashboards · Loki Centralized Logs & SPL · OpenTelemetry & Tempo Tracing · Alertmanager</p>
        </div>
        <button className="apple-btn apple-btn-secondary" onClick={() => { loadMetrics(); loadLogs(); loadTraces(); }}>
          <RefreshCw size={12} /> Refresh All
        </button>
      </div>

      <div className="ues-subtabs">
        {[
          { id: 'metrics', label: 'Prometheus & PromQL' },
          { id: 'grafana', label: 'Grafana Dashboards' },
          { id: 'logs', label: 'Loki Logs & SPL' },
          { id: 'traces', label: 'OpenTelemetry & Tempo Traces' },
          { id: 'alerts', label: `Alerts & Targets (${obs?.alerts?.length || 0})` },
        ].map((t) => (
          <button key={t.id} className={`ues-subtab ${subTab === t.id ? 'active' : ''}`} onClick={() => setSubTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      {subTab === 'metrics' && (
        <div className="studio-section-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <span className="studio-section-title">PromQL Interactive Explorer ({obs?.prometheus_reachable ? 'Prometheus Connected' : 'Prometheus Unreachable'})</span>
            <a href="http://localhost:9090" target="_blank" rel="noreferrer" className="apple-btn apple-btn-secondary" style={{ fontSize: '0.72rem' }}>
              <ExternalLink size={11} /> Prometheus UI
            </a>
          </div>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '0.6rem' }}>
            <input className="apple-input" value={promql} onChange={(e) => setPromql(e.target.value)} style={{ flex: 1, fontFamily: 'monospace' }} />
            <button className="apple-btn apple-btn-primary" onClick={runPromQL}><Play size={12} /> Execute</button>
          </div>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
            {['ues_service_up', 'ues_container_memory_mb', 'ues_container_cpu_percent', 'ues_error_budget_remaining_pct', 'app_cpu_usage_percent'].map((q) => (
              <button key={q} className="copilot-chip" onClick={() => setPromql(q)}>{q}</button>
            ))}
          </div>
          {promqlResult && <pre className="ues-terminal-out">{JSON.stringify(promqlResult, null, 2)}</pre>}
        </div>
      )}

      {subTab === 'grafana' && (
        <div className="studio-section-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <span className="studio-section-title">Provisioned Grafana Dashboards (Auth Protected — No Anonymous Admin)</span>
            <a href="/services/monitoring/" target="_blank" rel="noreferrer" className="apple-btn apple-btn-primary" style={{ fontSize: '0.74rem' }}>
              <ExternalLink size={12} /> Open Grafana
            </a>
          </div>
          <div className="labs-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))' }}>
            {(obs?.grafana_dashboards || []).map((d) => (
              <a key={d.id} href={d.url} target="_blank" rel="noreferrer" className="apple-lab-card" style={{ textDecoration: 'none' }}>
                <div>
                  <span className="lab-tag" style={{ color: 'var(--apple-cyan)' }}>Provisioned</span>
                  <h4 className="lab-title" style={{ marginTop: '0.4rem' }}>{d.title}</h4>
                </div>
                <span style={{ fontSize: '0.72rem', color: 'var(--apple-blue)' }}>Open in Grafana →</span>
              </a>
            ))}
          </div>
        </div>
      )}

      {subTab === 'logs' && (
        <div className="ues-grid-2">
          <div className="studio-section-card">
            <span className="studio-section-title">Centralized Log Search (Source: {logSource || 'auto'})</span>
            <div style={{ display: 'flex', gap: '8px', marginBottom: '0.6rem' }}>
              <input className="apple-input" placeholder="Container (all or name)" value={logContainer} onChange={(e) => setLogContainer(e.target.value)} style={{ width: '160px' }} />
              <input className="apple-input" placeholder="Filter text (ERROR, timeout...)" value={logSearch} onChange={(e) => setLogSearch(e.target.value)} style={{ flex: 1 }} />
              <button className="apple-btn apple-btn-primary" onClick={loadLogs}><Search size={12} /> Search</button>
            </div>
            <div style={{ maxHeight: '420px', overflowY: 'auto' }}>
              {logs.map((l, i) => (
                <div key={i} style={{ padding: '4px 6px', borderBottom: '1px solid var(--border-subtle)', fontFamily: 'monospace', fontSize: '0.72rem' }}>
                  <span style={{ color: l.level === 'ERROR' ? 'var(--apple-coral)' : l.level === 'WARN' ? 'var(--apple-amber)' : 'var(--apple-mint)' }}>[{l.level}]</span>{' '}
                  <span style={{ color: 'var(--apple-cyan)' }}>{l.container}</span>: {l.message}
                </div>
              ))}
            </div>
          </div>

          <div className="studio-section-card">
            <span className="studio-section-title">Splunk SPL Log Analytics Engine</span>
            <div style={{ display: 'flex', gap: '8px', marginBottom: '0.6rem' }}>
              <input className="apple-input" value={splQuery} onChange={(e) => setSplQuery(e.target.value)} style={{ flex: 1, fontFamily: 'monospace' }} />
              <button className="apple-btn apple-btn-primary" onClick={runSPL}>Run SPL</button>
            </div>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '0.6rem' }}>
              <button className="copilot-chip" onClick={() => setSplQuery('index=app_logs | stats count by service')}>Count by service</button>
              <button className="copilot-chip" onClick={() => setSplQuery('index=anomalies | head 20')}>Recent anomalies</button>
              <button className="copilot-chip" onClick={() => setSplQuery('index=app_logs status=ERROR | head 20')}>Errors only</button>
            </div>
            {splResult && (
              <pre className="ues-terminal-out">{JSON.stringify(splResult.rows, null, 2)}</pre>
            )}
          </div>
        </div>
      )}

      {subTab === 'traces' && (
        <div className="studio-section-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.6rem' }}>
            <span className="studio-section-title">OpenTelemetry Spans & Grafana Tempo ({traces.tempo_reachable ? 'Tempo Connected' : 'Local OTel Ring Buffer Active'})</span>
          </div>
          <table className="apple-table">
            <thead><tr><th>Trace ID</th><th>Span Name</th><th>Domain</th><th>Duration</th><th>Status</th></tr></thead>
            <tbody>
              {(traces.otel_spans || []).map((sp, i) => (
                <tr key={i}>
                  <td><code style={{ fontSize: '0.7rem' }}>{sp.trace_id}</code></td>
                  <td style={{ fontWeight: 600 }}>{sp.name}</td>
                  <td><span className="hero-pill-badge secondary">{sp.domain}</span></td>
                  <td>{sp.duration_ms} ms</td>
                  <td style={{ color: sp.status === 'ERROR' ? 'var(--apple-coral)' : 'var(--apple-mint)' }}>{sp.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {subTab === 'alerts' && (
        <div className="ues-grid-2">
          <div className="studio-section-card">
            <span className="studio-section-title">Firing Prometheus Alerts ({obs?.alerts?.length || 0})</span>
            {(obs?.alerts || []).map((a, i) => (
              <div key={i} className="reference-card-item" style={{ marginBottom: '6px' }}>
                <strong style={{ color: 'var(--apple-coral)' }}>{a.name}</strong> ({a.severity})
                <div className="reference-card-desc">{a.summary || a.description}</div>
              </div>
            ))}
            {(!obs?.alerts || obs.alerts.length === 0) && <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>No alerts currently firing.</div>}
          </div>
          <div className="studio-section-card">
            <span className="studio-section-title">Prometheus Scrape Targets ({obs?.targets?.length || 0})</span>
            <table className="apple-table">
              <thead><tr><th>Job</th><th>Instance</th><th>Health</th></tr></thead>
              <tbody>
                {(obs?.targets || []).map((t, i) => (
                  <tr key={i}>
                    <td>{t.job}</td>
                    <td><code>{t.instance}</code></td>
                    <td style={{ color: t.health === 'up' ? 'var(--apple-mint)' : 'var(--apple-coral)' }}>{t.health}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

