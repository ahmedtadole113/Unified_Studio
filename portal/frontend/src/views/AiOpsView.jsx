import React, { useEffect, useState } from 'react';
import { RefreshCw, Search, Sparkles, Zap } from 'lucide-react';
import { apiFetch, API_V1 } from '../api/client';

export default function AiOpsView({ geminiKey }) {
  const [insights, setInsights] = useState(null);
  const [pbQuery, setPbQuery] = useState('Airflow DAG failed and Spark executor OOMKilled');
  const [pbResult, setPbResult] = useState(null);
  const [copilotPrompt, setCopilotPrompt] = useState('');
  const [copilotMode, setCopilotMode] = useState('triage');
  const [copilotOutput, setCopilotOutput] = useState('');
  const [busy, setBusy] = useState(false);

  const loadAiOps = async () => {
    try {
      const res = await apiFetch(`${API_V1}/aiops/overview`);
      setInsights(res);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadAiOps();
  }, []);

  const searchPlaybook = async () => {
    const res = await apiFetch(`${API_V1}/aiops/playbooks/search`, {
      method: 'POST',
      body: JSON.stringify({ text: pbQuery }),
    });
    setPbResult(res);
  };

  const askCopilot = async (customPrompt = null) => {
    const text = customPrompt || copilotPrompt;
    if (!text.trim()) return;
    setBusy(true);
    try {
      const res = await apiFetch(`${API_V1}/aiops/copilot`, {
        method: 'POST',
        body: JSON.stringify({
          service: 'unified_studio',
          action: copilotMode,
          content: text,
          api_key: geminiKey || null,
        }),
      });
      setCopilotOutput(res.response || '');
    } catch (err) {
      setCopilotOutput(`Error: ${err.message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="view-container">
      <div className="section-header">
        <div>
          <h2 className="section-title"><Sparkles size={18} style={{ color: 'var(--apple-purple)' }} /> AIOps Intelligence & Root Cause Analysis</h2>
          <p className="section-subtitle">Anomaly Detection · Alert Correlation · FAISS Vector Playbooks ({insights?.playbooks_count || 12}) · Predictive Recommendations · Gemini Copilot</p>
        </div>
        <button className="apple-btn apple-btn-secondary" onClick={loadAiOps}><RefreshCw size={12} /> Refresh</button>
      </div>

      <div className="ues-grid-2" style={{ marginBottom: '1rem' }}>
        {/* Live Anomaly Stream */}
        <div className="studio-section-card">
          <span className="studio-section-title">Detected Anomalies & Suggested Remediation ({insights?.anomalies?.length || 0})</span>
          <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
            {(insights?.anomalies || []).map((a, i) => (
              <div key={i} className="reference-card-item" style={{ marginBottom: '0.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <strong style={{ color: a.severity === 'critical' ? 'var(--apple-coral)' : 'var(--apple-amber)' }}>{a.service}</strong>
                  <span style={{ fontSize: '0.68rem', color: 'var(--apple-purple)' }}>Runbook: {a.runbook_slug} ({a.similarity})</span>
                </div>
                <div style={{ fontSize: '0.78rem', marginTop: '3px' }}>{a.issue}</div>
                <div className="reference-card-desc" style={{ color: 'var(--apple-mint)', marginTop: '3px' }}>Fix: {a.ai_recommendation}</div>
              </div>
            ))}
            {(!insights?.anomalies || insights.anomalies.length === 0) && (
              <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>No live anomalies detected — platform operating nominally.</div>
            )}
          </div>
        </div>

        {/* Performance & Predictive Recommendations */}
        <div className="studio-section-card">
          <span className="studio-section-title">Performance & Predictive Capacity Recommendations</span>
          {(insights?.recommendations || []).map((r, i) => (
            <div key={i} className="reference-card-item" style={{ marginBottom: '0.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <strong>{r.title}</strong>
                <span className="hero-pill-badge secondary">{r.category}</span>
              </div>
              <div className="reference-card-desc">{r.detail}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="ues-grid-2">
        {/* FAISS Playbook Matcher */}
        <div className="studio-section-card">
          <span className="studio-section-title">FAISS Semantic Runbook & Incident Classifier</span>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '0.6rem' }}>
            <input className="apple-input" value={pbQuery} onChange={(e) => setPbQuery(e.target.value)} style={{ flex: 1 }} placeholder="Describe error log, K8s crash, or pipeline failure..." />
            <button className="apple-btn apple-btn-primary" onClick={searchPlaybook}><Search size={12} /> Match</button>
          </div>
          {pbResult && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {(pbResult.matches || []).map((m, i) => (
                <div key={i} className="reference-card-item">
                  <strong>{m.slug}</strong> ({m.domain}) · similarity <code>{m.similarity}</code>
                  <div className="reference-card-desc">{m.remediation}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* AI Copilot */}
        <div className="studio-section-card">
          <span className="studio-section-title"><Zap size={12} style={{ color: 'var(--apple-purple)' }} /> Unified DE + SRE AI Copilot</span>
          <div style={{ display: 'flex', gap: '6px', marginBottom: '0.5rem', flexWrap: 'wrap' }}>
            {['triage', 'general', 'validate_code', 'generate_code', 'postmortem'].map((m) => (
              <button key={m} className={`copilot-chip ${copilotMode === m ? 'active-chip' : ''}`} onClick={() => setCopilotMode(m)}>{m}</button>
            ))}
          </div>
          <textarea
            className="copilot-textarea"
            rows={4}
            placeholder="Paste stack trace, SQL/PySpark snippet, Prometheus alert, or ask for Root Cause Analysis..."
            value={copilotPrompt}
            onChange={(e) => setCopilotPrompt(e.target.value)}
          />
          <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }}>
            <button className="apple-btn apple-btn-accent" onClick={() => askCopilot()} disabled={busy}>
              {busy ? 'Analyzing...' : 'Run AI Analysis'}
            </button>
            <button className="apple-btn apple-btn-secondary" onClick={() => askCopilot('Summarize current DE pipeline and SRE reliability posture and top risks.')}>
              Quick Posture RCA
            </button>
          </div>
          {copilotOutput && (
            <pre className="ues-terminal-out" style={{ marginTop: '0.75rem', whiteSpace: 'pre-wrap' }}>{copilotOutput}</pre>
          )}
        </div>
      </div>
    </div>
  );
}

