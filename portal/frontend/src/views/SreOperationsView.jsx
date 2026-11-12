import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Flame,
  Play,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';
import { apiFetch, API_V1 } from '../api/client';
import { SreRoadmapBrowser } from './RoadmapsView';

export default function SreOperationsView({ user }) {
  const [subTab, setSubTab] = useState('slo');
  const [windowMode, setWindowMode] = useState('1h');
  const [calendarMode, setCalendarMode] = useState(false);
  const [sloData, setSloData] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [chaosList, setChaosList] = useState([]);
  const [experiments, setExperiments] = useState([]);
  const [confirmInputs, setConfirmInputs] = useState({});
  const [runbooks, setRunbooks] = useState([]);
  const [postmortems, setPostmortems] = useState([]);
  const [readiness, setReadiness] = useState(null);
  const [roadmap, setRoadmap] = useState(null);
  const [pmForm, setPmForm] = useState({ title: '', severity: 'SEV-2', slo_impact: '', summary: '', root_cause: '' });
  const [statusMsg, setStatusMsg] = useState(null);

  const isAdmin = user?.role === 'admin';

  const loadSre = async () => {
    try {
      const [s, inc, ch, rb, pm, rd] = await Promise.all([
        apiFetch(`${API_V1}/slo?window=${windowMode}&calendar=${calendarMode}`),
        apiFetch(`${API_V1}/incidents?limit=40`),
        apiFetch(`${API_V1}/incidents/chaos/scenarios`),
        apiFetch(`${API_V1}/incidents/runbooks/all`),
        apiFetch(`${API_V1}/incidents/postmortems/all`),
        apiFetch(`${API_V1}/platform/readiness`),
      ]);
      setSloData(s);
      setIncidents(inc.incidents || []);
      if (!selectedIncident && inc.incidents?.length) setSelectedIncident(inc.incidents[0]);
      setChaosList(ch.scenarios || []);
      setExperiments(ch.experiments || []);
      setRunbooks(rb.runbooks || []);
      setPostmortems(pm.postmortems || []);
      setReadiness(rd);
    } catch (err) {
      setStatusMsg(err.message);
    }
  };

  useEffect(() => {
    loadSre();
  }, [windowMode, calendarMode]);

  const loadRoadmap = async () => {
    if (roadmap) return;
    const rm = await apiFetch(`${API_V1}/aiops/roadmap`);
    setRoadmap(rm);
  };

  const runCorrelate = async () => {
    setStatusMsg(null);
    try {
      const res = await apiFetch(`${API_V1}/incidents/correlate`, { method: 'POST' });
      setStatusMsg(`Correlation pass complete: ${res.correlated_incidents?.length || 0} correlated incident(s).`);
      loadSre();
    } catch (err) {
      setStatusMsg(err.message);
    }
  };

  const setIncidentStatus = async (id, status) => {
    await apiFetch(`${API_V1}/incidents/${id}/status`, {
      method: 'PUT',
      body: JSON.stringify({ status, note: `Updated via SRE Console` }),
    });
    loadSre();
  };

  const executeChaos = async (sc) => {
    const phrase = confirmInputs[sc.id] || '';
    setStatusMsg(null);
    try {
      const res = await apiFetch(`${API_V1}/incidents/chaos/execute`, {
        method: 'POST',
        body: JSON.stringify({ scenario_id: sc.id, confirm: true, confirmation_phrase: phrase }),
      });
      setStatusMsg(`Executed '${sc.title}': ${res.observed}`);
      loadSre();
    } catch (err) {
      setStatusMsg(err.message);
    }
  };

  const recoverChaos = async (sc) => {
    setStatusMsg(null);
    try {
      const res = await apiFetch(`${API_V1}/incidents/chaos/recover`, {
        method: 'POST',
        body: JSON.stringify({ scenario_id: sc.id }),
      });
      setStatusMsg(`Recovered '${sc.title}': ${res.detail}`);
      loadSre();
    } catch (err) {
      setStatusMsg(err.message);
    }
  };

  const submitPostmortem = async (e) => {
    e.preventDefault();
    try {
      await apiFetch(`${API_V1}/incidents/postmortems`, {
        method: 'POST',
        body: JSON.stringify(pmForm),
      });
      setPmForm({ title: '', severity: 'SEV-2', slo_impact: '', summary: '', root_cause: '' });
      loadSre();
    } catch (err) {
      setStatusMsg(err.message);
    }
  };

  return (
    <div className="view-container">
      <div className="section-header">
        <div>
          <h2 className="section-title"><ShieldAlert size={18} style={{ color: 'var(--apple-rose)' }} /> SRE Operations & Reliability Engineering</h2>
          <p className="section-subtitle">9 Measured SLOs & Error Budgets · DE ↔ SRE Incident Correlation · 10 Controlled Chaos Drills · Runbooks & Postmortems</p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="apple-btn apple-btn-primary" onClick={runCorrelate}>Correlate DE + SRE</button>
          <button className="apple-btn apple-btn-secondary" onClick={loadSre}><RefreshCw size={12} /> Refresh</button>
        </div>
      </div>

      {statusMsg && <div className="ues-alert-banner info" style={{ marginBottom: '0.75rem' }}>{statusMsg}</div>}

      <div className="ues-subtabs">
        {[
          { id: 'slo', label: `SLOs & Error Budgets (${sloData?.counts?.total || 9})` },
          { id: 'incidents', label: `Incidents & Correlation (${incidents.length})` },
          { id: 'chaos', label: 'Chaos Lab (10 Scenarios)' },
          { id: 'runbooks', label: `Runbooks (${runbooks.length})` },
          { id: 'postmortems', label: `Postmortems (${postmortems.length})` },
          { id: 'readiness', label: `Readiness Gate (${readiness?.gate_status || '—'})` },
          { id: 'roadmap', label: '45-Day SRE Roadmap' },
        ].map((t) => (
          <button
            key={t.id}
            className={`ues-subtab ${subTab === t.id ? 'active' : ''}`}
            onClick={() => {
              setSubTab(t.id);
              if (t.id === 'roadmap') loadRoadmap();
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {subTab === 'slo' && (
        <div className="studio-section-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '8px' }}>
            <div>
              <span className="studio-section-title">Live SLO / SLA / Error-Budget Engine</span>
              <div style={{ fontSize: '0.74rem', color: sloData?.release_freeze ? 'var(--apple-coral)' : 'var(--apple-mint)' }}>
                {sloData?.release_freeze ? 'RELEASE FREEZE: Critical error budget exhausted or burn > 14.4x' : `Compliance: ${sloData?.overall_compliance_pct ?? 100}%`}
              </div>
            </div>
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
              {['5m', '1h', '24h', '7d', '30d'].map((w) => (
                <button key={w} className={`copilot-chip ${!calendarMode && windowMode === w ? 'active-chip' : ''}`} onClick={() => { setCalendarMode(false); setWindowMode(w); }}>{w}</button>
              ))}
              <button className={`copilot-chip ${calendarMode ? 'active-chip' : ''}`} onClick={() => setCalendarMode(!calendarMode)}>Month-to-Date</button>
            </div>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table className="apple-table">
              <thead>
                <tr><th>SLO Name</th><th>Domain</th><th>Target (SLA)</th><th>Actual SLI</th><th>Budget Remaining</th><th>Burn (5m / 1h)</th><th>Status & Policy</th></tr>
              </thead>
              <tbody>
                {(sloData?.slos || []).map((s) => (
                  <tr key={s.id}>
                    <td>
                      <div style={{ fontWeight: 600 }}>{s.name}</div>
                      <div style={{ fontSize: '0.68rem', color: 'var(--text-secondary)' }}>{s.service} · {s.measurement_window}</div>
                    </td>
                    <td><span className="hero-pill-badge secondary">{s.domain}</span></td>
                    <td>{s.comparison === 'lte' ? '≤' : '≥'} {s.target} {s.unit} <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>({s.sla_tier})</span></td>
                    <td style={{ fontWeight: 600 }}>{s.actual_sli !== null && s.actual_sli !== undefined ? `${s.actual_sli} ${s.unit}` : 'Profile offline'}</td>
                    <td>
                      <div style={{ width: '110px' }}>
                        <div style={{ fontSize: '0.72rem' }}>{s.error_budget_remaining_pct}% left</div>
                        <div className="meter-track"><div className="meter-fill" style={{ width: `${s.error_budget_remaining_pct}%`, background: s.status === 'breach' ? 'var(--apple-coral)' : s.status === 'warning' ? 'var(--apple-amber)' : 'var(--apple-mint)' }} /></div>
                      </div>
                    </td>
                    <td style={{ fontSize: '0.74rem' }}>{s.burn_rate_5m}x / {s.burn_rate_1h}x</td>
                    <td>
                      <span className={`hero-pill-badge ${s.status === 'healthy' ? 'primary' : 'secondary'}`}>{s.status}</span>
                      <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '2px' }}>{s.policy}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {subTab === 'incidents' && (
        <div className="ues-grid-2" style={{ gridTemplateColumns: '380px 1fr' }}>
          <div className="studio-section-card" style={{ maxHeight: '600px', overflowY: 'auto' }}>
            <span className="studio-section-title">Incidents ({incidents.length})</span>
            {incidents.map((inc) => (
              <div
                key={inc.id}
                className="reference-card-item"
                style={{ marginBottom: '0.5rem', borderColor: selectedIncident?.id === inc.id ? 'var(--apple-blue)' : undefined }}
                onClick={() => setSelectedIncident(inc)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <strong style={{ fontSize: '0.8rem', color: inc.severity === 'SEV-1' ? 'var(--apple-coral)' : 'var(--apple-amber)' }}>{inc.severity} · {inc.status.toUpperCase()}</strong>
                  <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>{inc.source}</span>
                </div>
                <div style={{ fontWeight: 600, fontSize: '0.82rem', marginTop: '3px' }}>{inc.title}</div>
                <div className="reference-card-desc">{inc.summary?.slice(0, 100)}</div>
              </div>
            ))}
            {incidents.length === 0 && <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>No incidents recorded. Click "Correlate DE + SRE" or run a Chaos drill.</div>}
          </div>

          <div className="studio-section-card">
            {selectedIncident ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
                  <div>
                    <h3 style={{ fontSize: '1.05rem' }}>{selectedIncident.title}</h3>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                      ID: <code>{selectedIncident.id}</code> · Trace: <code>{selectedIncident.trace_id || 'n/a'}</code> · SLO Impact: {selectedIncident.slo_impact_pct}%
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button className="apple-btn apple-btn-secondary" onClick={() => setIncidentStatus(selectedIncident.id, 'investigating')}>Investigate</button>
                    <button className="apple-btn apple-btn-primary" onClick={() => setIncidentStatus(selectedIncident.id, 'resolved')}>Resolve</button>
                  </div>
                </div>

                <div className="ues-grid-2">
                  <div className="reference-card-item">
                    <span className="studio-section-title" style={{ color: 'var(--apple-coral)' }}>Data Engineer Perspective</span>
                    <p style={{ fontSize: '0.78rem', marginTop: '4px' }}>{selectedIncident.de_perspective || 'No DE pipeline impact reported.'}</p>
                    {selectedIncident.pipeline_id && <div style={{ fontSize: '0.72rem', marginTop: '4px' }}>DAG: <code>{selectedIncident.pipeline_id}</code></div>}
                    {selectedIncident.job_id && <div style={{ fontSize: '0.72rem' }}>Spark Job: <code>{selectedIncident.job_id}</code></div>}
                  </div>
                  <div className="reference-card-item">
                    <span className="studio-section-title" style={{ color: 'var(--apple-cyan)' }}>SRE Perspective</span>
                    <p style={{ fontSize: '0.78rem', marginTop: '4px' }}>{selectedIncident.sre_perspective || selectedIncident.summary}</p>
                    {selectedIncident.k8s_pod && <div style={{ fontSize: '0.72rem', marginTop: '4px' }}>K8s Pod: <code>{selectedIncident.k8s_namespace}/{selectedIncident.k8s_pod}</code></div>}
                  </div>
                </div>

                <div className="reference-card-item">
                  <span className="studio-section-title" style={{ color: 'var(--apple-purple)' }}>AIOps Root Cause Analysis & Remediation</span>
                  <p style={{ fontSize: '0.8rem', marginTop: '4px' }}>{selectedIncident.ai_rca}</p>
                  <p style={{ fontSize: '0.78rem', color: 'var(--apple-mint)', marginTop: '4px' }}>Recommended Action: {selectedIncident.remediation}</p>
                </div>

                <div className="reference-card-item">
                  <span className="studio-section-title">Incident Timeline</span>
                  {(selectedIncident.timeline || []).map((ev, idx) => (
                    <div key={idx} style={{ fontSize: '0.74rem', padding: '3px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                      <code>{new Date(ev.ts * 1000).toLocaleTimeString()}</code> [{ev.actor}] — {ev.event}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div style={{ color: 'var(--text-muted)' }}>Select an incident to inspect correlated DE & SRE evidence.</div>
            )}
          </div>
        </div>
      )}

      {subTab === 'chaos' && (
        <div className="labs-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(310px, 1fr))' }}>
          {chaosList.map((sc) => (
            <div key={sc.id} className="apple-lab-card">
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span className="lab-tag" style={{ color: sc.severity === 'SEV-1' ? 'var(--apple-coral)' : 'var(--apple-amber)' }}>
                    {sc.category} · {sc.severity}
                  </span>
                  <code style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>{sc.target_default}</code>
                </div>
                <h3 className="lab-title" style={{ marginTop: '0.45rem' }}>{sc.title}</h3>
                <p className="lab-desc" style={{ marginTop: '0.3rem' }}>{sc.description}</p>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '0.4rem' }}>
                  Type <code>{sc.confirmation_phrase}</code> to confirm:
                </div>
              </div>
              {isAdmin && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '0.6rem' }}>
                  <input
                    className="apple-input"
                    placeholder={sc.confirmation_phrase}
                    value={confirmInputs[sc.id] || ''}
                    onChange={(e) => setConfirmInputs((p) => ({ ...p, [sc.id]: e.target.value }))}
                  />
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button className="apple-btn apple-btn-danger" style={{ flex: 1 }} onClick={() => executeChaos(sc)}>
                      <Flame size={12} /> Execute
                    </button>
                    <button className="apple-btn apple-btn-primary" style={{ flex: 1 }} onClick={() => recoverChaos(sc)}>
                      <RotateCcw size={12} /> Recover
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {subTab === 'runbooks' && (
        <div className="ues-grid-2">
          {runbooks.map((rb) => (
            <div key={rb.slug} className="studio-section-card">
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <strong>{rb.title}</strong>
                <span className="hero-pill-badge secondary">{rb.severity} · {rb.domain}</span>
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--apple-amber)', margin: '4px 0' }}>Trigger: <code>{rb.trigger_alert}</code></div>
              <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.76rem', color: 'var(--text-secondary)', fontFamily: 'inherit' }}>{rb.steps_md}</pre>
            </div>
          ))}
        </div>
      )}

      {subTab === 'postmortems' && (
        <div className="ues-grid-2">
          <form className="studio-section-card" onSubmit={submitPostmortem} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <span className="studio-section-title">Author Blameless Post-Incident Review</span>
            <input className="apple-input" placeholder="Incident Title" value={pmForm.title} onChange={(e) => setPmForm({ ...pmForm, title: e.target.value })} required />
            <input className="apple-input" placeholder="SLO Impact (e.g. 0.4% error budget consumed)" value={pmForm.slo_impact} onChange={(e) => setPmForm({ ...pmForm, slo_impact: e.target.value })} required />
            <textarea className="copilot-textarea" rows={3} placeholder="Executive Summary" value={pmForm.summary} onChange={(e) => setPmForm({ ...pmForm, summary: e.target.value })} required />
            <textarea className="copilot-textarea" rows={3} placeholder="Root Cause & Contributing Factors" value={pmForm.root_cause} onChange={(e) => setPmForm({ ...pmForm, root_cause: e.target.value })} required />
            <button type="submit" className="apple-btn apple-btn-primary">Publish Postmortem</button>
          </form>

          <div className="studio-section-card">
            <span className="studio-section-title">Published Postmortems ({postmortems.length})</span>
            {postmortems.map((pm) => (
              <div key={pm.id} className="reference-card-item" style={{ marginBottom: '0.6rem' }}>
                <strong>{pm.title}</strong> <span className="hero-pill-badge secondary">{pm.severity}</span>
                <div className="reference-card-desc" style={{ marginTop: '4px' }}><strong>SLO Impact:</strong> {pm.slo_impact}</div>
                <div className="reference-card-desc"><strong>Root Cause:</strong> {pm.root_cause}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {subTab === 'readiness' && readiness && (
        <div className="studio-section-card">
          <span className="studio-section-title">Production Readiness & Admission Gate: {readiness.gate_status} ({readiness.passed_count}/{readiness.total_checks})</span>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '0.5rem' }}>
            {readiness.checks.map((c) => (
              <div key={c.id} className="reference-card-item" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <strong>{c.name}</strong>
                  <div className="reference-card-desc">{c.detail}</div>
                </div>
                <span style={{ color: c.passed ? 'var(--apple-mint)' : 'var(--apple-coral)', fontWeight: 600 }}>
                  {c.passed ? 'PASS' : 'FAIL'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {subTab === 'roadmap' && <SreRoadmapBrowser />}
    </div>
  );
}

