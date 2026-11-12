import React, { useEffect, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  Cpu,
  Database,
  DollarSign,
  ExternalLink,
  Layers,
  Play,
  RefreshCw,
  RotateCw,
  Server,
  ShieldCheck,
  Square,
} from 'lucide-react';
import { apiFetch, API_V1 } from '../api/client';

export default function PlatformOverview({ user, onNavigate, onOpenWorkspace, onHealthUpdate }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [msg, setMsg] = useState(null);

  const isAdmin = user?.role === 'admin';

  const loadOverview = async () => {
    try {
      const res = await apiFetch(`${API_V1}/platform/overview`);
      setData(res);
      onHealthUpdate?.({ healthy: res.services.healthy, total: res.services.total });
    } catch (err) {
      setMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOverview();
    const timer = setInterval(loadOverview, 5000);
    return () => clearInterval(timer);
  }, []);

  const handleServiceAction = async (serviceId, action) => {
    setBusyId(serviceId);
    setMsg(null);
    try {
      await apiFetch(`${API_V1}/services/${serviceId}/${action}`, { method: 'POST' });
      await loadOverview();
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusyId(null);
    }
  };

  const handleProfileAction = async (profileId, action) => {
    setBusyId(profileId);
    setMsg(null);
    try {
      await apiFetch(`${API_V1}/platform/profiles/action`, {
        method: 'POST',
        body: JSON.stringify({ profile: profileId, action }),
      });
      await loadOverview();
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusyId(null);
    }
  };

  if (loading && !data) {
    return <div className="view-container"><div className="apple-hero">Loading Unified Platform Telemetry...</div></div>;
  }

  const svcs = data?.services || { total: 0, healthy: 0, degraded: 0, unavailable: 0, items: [] };
  const k8s = data?.kubernetes || {};
  const slo = data?.slo || {};
  const finops = data?.finops || {};
  const docker = data?.docker || {};
  const incidents = data?.incidents || { open_count: 0, items: [] };

  const statusColor = (st) => (st === 'healthy' ? 'var(--apple-mint)' : st === 'degraded' ? 'var(--apple-amber)' : 'var(--apple-coral)');

  return (
    <div className="view-container">
      {/* Hero Summary */}
      <div className="apple-hero">
        <div className="hero-glow-accent" />
        <div className="hero-tag-strip">
          <span className="hero-pill-badge primary">Unified Engineering Studio v{data?.version || '5.0'}</span>
          <span className="hero-pill-badge secondary">Data Engineering + SRE + Kubernetes + AIOps</span>
          <span className="hero-pill-badge accent">Apple Silicon M4 8GB Profiled</span>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
          <div>
            <h1 className="hero-title apple-gradient-text" style={{ fontSize: '1.85rem' }}>
              Platform Control Plane Overview
            </h1>
            <p className="hero-subtitle">
              Real-time service registry, container & Kubernetes health, running data pipelines, SLO error budgets, and FinOps cost posture.
            </p>
          </div>
          <button className="apple-btn apple-btn-secondary" onClick={loadOverview}>
            <RefreshCw size={13} /> Refresh
          </button>
        </div>

        {msg && <div className="ues-alert-banner danger" style={{ marginTop: '0.75rem' }}>{msg}</div>}

        <div className="hero-stats-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(175px, 1fr))' }}>
          <div className="stat-capsule" onClick={() => onNavigate('infrastructure')} style={{ cursor: 'pointer' }}>
            <span className="stat-label">Platform Health</span>
            <span className="stat-value" style={{ color: statusColor(data?.overall_health), textTransform: 'capitalize' }}>
              {data?.overall_health || 'unknown'}
            </span>
            <span className="stat-desc">{svcs.healthy} healthy · {svcs.degraded} degraded · {svcs.unavailable} down</span>
          </div>

          <div className="stat-capsule" onClick={() => onNavigate('infrastructure')} style={{ cursor: 'pointer' }}>
            <span className="stat-label">Docker Containers</span>
            <span className="stat-value" style={{ color: 'var(--apple-cyan)' }}>
              {docker.running_containers}/{docker.total_containers}
            </span>
            <span className="stat-desc">CPU {docker.total_cpu_percent}% · RAM {docker.total_memory_mb} MB</span>
          </div>

          <div className="stat-capsule" onClick={() => onNavigate('infrastructure')} style={{ cursor: 'pointer' }}>
            <span className="stat-label">Kubernetes Cluster</span>
            <span className="stat-value" style={{ color: k8s.connected ? 'var(--apple-mint)' : 'var(--text-secondary)' }}>
              {k8s.connected ? `${k8s.summary?.pods_running || 0} Pods` : k8s.status}
            </span>
            <span className="stat-desc">
              {k8s.connected ? `${k8s.summary?.nodes_ready}/${k8s.summary?.nodes} nodes · ${k8s.summary?.pods_failing || 0} failing` : 'Optional local cluster'}
            </span>
          </div>

          <div className="stat-capsule" onClick={() => onNavigate('data_engineering')} style={{ cursor: 'pointer' }}>
            <span className="stat-label">Data Pipelines</span>
            <span className="stat-value" style={{ color: 'var(--apple-coral)' }}>
              {data?.pipelines?.running || 0} Running
            </span>
            <span className="stat-desc">
              {data?.pipelines?.airflow_dags_count || 0} DAGs · {data?.pipelines?.spark_apps_count || 0} Spark apps
            </span>
          </div>

          <div className="stat-capsule" onClick={() => onNavigate('sre')} style={{ cursor: 'pointer' }}>
            <span className="stat-label">Active Incidents</span>
            <span className="stat-value" style={{ color: incidents.open_count > 0 ? 'var(--apple-coral)' : 'var(--apple-mint)' }}>
              {incidents.open_count} Open
            </span>
            <span className="stat-desc">DE ↔ SRE Correlation Active</span>
          </div>

          <div className="stat-capsule" onClick={() => onNavigate('sre')} style={{ cursor: 'pointer' }}>
            <span className="stat-label">SLO Compliance</span>
            <span className="stat-value" style={{ color: slo.release_freeze ? 'var(--apple-coral)' : 'var(--apple-mint)' }}>
              {slo.overall_compliance_pct ?? 100}%
            </span>
            <span className="stat-desc">{slo.release_freeze ? 'Release Freeze Active' : `${slo.counts?.healthy || 0}/${slo.counts?.total || 9} SLOs Healthy`}</span>
          </div>

          <div className="stat-capsule" onClick={() => onNavigate('finops')} style={{ cursor: 'pointer' }}>
            <span className="stat-label">FinOps & 8GB Budget</span>
            <span className="stat-value" style={{ color: 'var(--apple-gold)' }}>
              ${finops.estimated_monthly_usd || 0}/mo
            </span>
            <span className="stat-desc">{finops.ram_budget_used_pct || 0}% of 5.1 GB M4 cap</span>
          </div>
        </div>
      </div>

      {/* Unified Stack (Single Profile) with Separated DE & SRE Stacks */}
      <div className="section-header">
        <div>
          <h2 className="section-title"><Cpu size={17} style={{ color: 'var(--apple-blue)' }} /> Unified Stack Architecture (Separated DE & SRE Stacks)</h2>
          <p className="section-subtitle">All services share one unified default profile while keeping Data Engineering and SRE stacks cleanly separated</p>
        </div>
        {isAdmin && (
          <button
            className="apple-btn apple-btn-primary"
            disabled={busyId === 'stack-all'}
            onClick={() => handleProfileAction('stack-all', 'up')}
          >
            <Play size={12} /> Start Full Unified Stack
          </button>
        )}
      </div>
      <div className="labs-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))', marginBottom: '1.5rem' }}>
        {(finops.profiles || []).map((prof) => (
          <div key={prof.id} className="apple-lab-card">
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="lab-tag" style={{ color: prof.state === 'active' ? 'var(--apple-mint)' : 'var(--apple-amber)' }}>
                  {prof.state.toUpperCase()} · {prof.active_count}/{prof.total_count}
                </span>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>Cap ~{prof.estimated_limit_mb} MB</span>
              </div>
              <h3 className="lab-title" style={{ marginTop: '0.5rem' }}>{prof.name}</h3>
              <p className="lab-desc" style={{ marginTop: '0.3rem' }}>{prof.description}</p>
            </div>
            {isAdmin && (
              <div style={{ display: 'flex', gap: '8px', marginTop: '0.75rem' }}>
                <button
                  className="apple-btn apple-btn-primary"
                  disabled={busyId === prof.id}
                  onClick={() => handleProfileAction(prof.id, 'up')}
                  style={{ flex: 1 }}
                >
                  <Play size={12} /> Start Stack
                </button>
                {prof.id !== 'stack-core' && (
                  <button
                    className="apple-btn apple-btn-danger"
                    disabled={busyId === prof.id}
                    onClick={() => handleProfileAction(prof.id, 'stop')}
                  >
                    <Square size={12} /> Stop
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Shared Service Registry Table */}
      <div className="section-header">
        <div>
          <h2 className="section-title"><Layers size={17} style={{ color: 'var(--apple-mint)' }} /> Shared Service Registry</h2>
          <p className="section-subtitle">Live health checks, lifecycle stage (DISCOVER → REGISTER → HEALTH CHECK → MONITOR → ALERT → RECOVER), and dependencies</p>
        </div>
      </div>

      <div className="studio-section-card" style={{ overflowX: 'auto' }}>
        <table className="apple-table">
          <thead>
            <tr>
              <th>Service</th>
              <th>Category</th>
              <th>Profile</th>
              <th>Status</th>
              <th>Lifecycle</th>
              <th>CPU / RAM</th>
              <th>Restarts</th>
              <th>Associated SLO</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {svcs.items.map((s) => (
              <tr key={s.service_id}>
                <td>
                  <div style={{ fontWeight: 600 }}>{s.service_name}</div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
                    {s.service_id} · {s.internal_endpoint}
                  </div>
                </td>
                <td><span className="hero-pill-badge secondary">{s.category}</span></td>
                <td style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>{s.profile}</td>
                <td>
                  <span className={`apple-status-badge ${s.status === 'healthy' ? 'online' : 'offline'}`}>
                    <span className={`pulse-dot ${s.status === 'healthy' ? 'online' : 'offline'}`} />
                    {s.status}
                  </span>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '2px' }}>{s.probe_detail}</div>
                </td>
                <td style={{ fontSize: '0.72rem' }}><code>{s.lifecycle_state}</code></td>
                <td style={{ fontSize: '0.74rem' }}>
                  {s.cpu_utilization_pct}% · {s.memory_utilization_mb} MB
                </td>
                <td style={{ color: s.restart_count > 0 ? 'var(--apple-amber)' : 'var(--text-secondary)' }}>{s.restart_count}</td>
                <td style={{ fontSize: '0.72rem' }}><code>{s.associated_slo}</code></td>
                <td>
                  <div style={{ display: 'flex', gap: '4px' }}>
                    {isAdmin && s.service_id !== 'portal-backend' && s.service_id !== 'portal-frontend' && (
                      s.status === 'healthy' ? (
                        <>
                          <button className="apple-btn apple-btn-secondary" title="Restart" disabled={busyId === s.service_id} onClick={() => handleServiceAction(s.service_id, 'restart')} style={{ padding: '3px 7px' }}>
                            <RotateCw size={11} />
                          </button>
                          <button className="apple-btn apple-btn-danger" title="Stop" disabled={busyId === s.service_id} onClick={() => handleServiceAction(s.service_id, 'stop')} style={{ padding: '3px 7px' }}>
                            <Square size={11} />
                          </button>
                        </>
                      ) : (
                        <button className="apple-btn apple-btn-primary" title="Start" disabled={busyId === s.service_id} onClick={() => handleServiceAction(s.service_id, 'start')} style={{ padding: '3px 7px' }}>
                          <Play size={11} />
                        </button>
                      )
                    )}
                    {s.ui_url && (
                      <button
                        className="apple-btn apple-btn-secondary"
                        style={{ padding: '3px 7px' }}
                        title="Open UI in Same Window"
                        onClick={() => onOpenWorkspace?.(s.ui_url, s.service_name)}
                      >
                        <ExternalLink size={11} />
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

