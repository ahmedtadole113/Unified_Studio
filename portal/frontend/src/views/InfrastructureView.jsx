import React, { useEffect, useState } from 'react';
import { Play, RefreshCw, RotateCw, Server, Square, Terminal } from 'lucide-react';
import { apiFetch, API_V1 } from '../api/client';

export default function InfrastructureView({ user }) {
  const [subTab, setSubTab] = useState('docker');
  const [infra, setInfra] = useState(null);
  const [k8sWorkloads, setK8sWorkloads] = useState(null);
  const [selectedNs, setSelectedNs] = useState('all');
  const [logsTarget, setLogsTarget] = useState('');
  const [logLines, setLogLines] = useState([]);
  const [error, setError] = useState(null);

  const isAdmin = user?.role === 'admin';

  const loadInfra = async () => {
    try {
      const res = await apiFetch(`${API_V1}/infrastructure/summary`);
      setInfra(res);
      if (res.kubernetes?.connected) {
        const wl = await apiFetch(`${API_V1}/kubernetes/workloads?namespace=${encodeURIComponent(selectedNs)}`);
        setK8sWorkloads(wl);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    loadInfra();
  }, [selectedNs]);

  const containerAction = async (name, action) => {
    setError(null);
    try {
      await apiFetch(`${API_V1}/docker/containers/${name}/${action}`, { method: 'POST' });
      loadInfra();
    } catch (err) {
      setError(err.message);
    }
  };

  const viewDockerLogs = async (name) => {
    setLogsTarget(`docker:${name}`);
    const res = await apiFetch(`${API_V1}/docker/containers/${name}/logs?tail=100`);
    setLogLines(res.lines || []);
  };

  const viewPodLogs = async (ns, pod) => {
    setLogsTarget(`k8s:${ns}/${pod}`);
    const res = await apiFetch(`${API_V1}/kubernetes/pods/${ns}/${pod}/logs?tail=100`);
    setLogLines(res.lines || []);
  };

  const docker = infra?.docker || {};
  const k8s = infra?.kubernetes || {};

  return (
    <div className="view-container">
      <div className="section-header">
        <div>
          <h2 className="section-title"><Server size={18} style={{ color: 'var(--apple-cyan)' }} /> Infrastructure Management</h2>
          <p className="section-subtitle">Docker Containers, Networks & Volumes + Local Kubernetes Cluster, Workloads, Requests/Limits & Events</p>
        </div>
        <button className="apple-btn apple-btn-secondary" onClick={loadInfra}><RefreshCw size={12} /> Refresh</button>
      </div>

      {error && <div className="ues-alert-banner danger" style={{ marginBottom: '0.75rem' }}>{error}</div>}

      <div className="ues-subtabs">
        <button className={`ues-subtab ${subTab === 'docker' ? 'active' : ''}`} onClick={() => setSubTab('docker')}>
          Docker Engine ({docker.running || 0}/{docker.total || 0})
        </button>
        <button className={`ues-subtab ${subTab === 'kubernetes' ? 'active' : ''}`} onClick={() => setSubTab('kubernetes')}>
          Kubernetes ({k8s.connected ? `${k8s.summary?.pods_total || 0} Pods` : k8s.status || 'disabled'})
        </button>
      </div>

      {subTab === 'docker' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="studio-section-card" style={{ overflowX: 'auto' }}>
            <table className="apple-table">
              <thead>
                <tr>
                  <th>Container</th>
                  <th>Image</th>
                  <th>State</th>
                  <th>CPU</th>
                  <th>Memory</th>
                  <th>Net I/O</th>
                  <th>Restarts</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {(docker.containers || []).map((c) => (
                  <tr key={c.id}>
                    <td>
                      <div style={{ fontWeight: 600 }}>{c.name}</div>
                      <div style={{ fontSize: '0.68rem', color: 'var(--text-secondary)' }}>{c.id} · {c.networks.join(', ')}</div>
                    </td>
                    <td style={{ fontSize: '0.72rem' }}><code>{c.image}</code></td>
                    <td>
                      <span className={`apple-status-badge ${c.running ? 'online' : 'offline'}`}>
                        {c.status} {c.oom_killed ? '(OOMKilled)' : ''}
                      </span>
                    </td>
                    <td>{c.cpu_percent}%</td>
                    <td>{c.memory_mb} / {c.memory_limit_mb} MB ({c.memory_percent}%)</td>
                    <td style={{ fontSize: '0.72rem' }}>RX {c.rx_mb} / TX {c.tx_mb} MB</td>
                    <td style={{ color: c.restart_count > 0 ? 'var(--apple-amber)' : 'var(--text-secondary)' }}>{c.restart_count}</td>
                    <td>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        <button className="apple-btn apple-btn-secondary" style={{ padding: '3px 7px' }} onClick={() => viewDockerLogs(c.name)} title="Logs">
                          <Terminal size={11} />
                        </button>
                        {isAdmin && c.name !== 'portal-backend' && c.name !== 'portal-frontend' && (
                          c.running ? (
                            <>
                              <button className="apple-btn apple-btn-secondary" style={{ padding: '3px 7px' }} onClick={() => containerAction(c.name, 'restart')} title="Restart"><RotateCw size={11} /></button>
                              <button className="apple-btn apple-btn-danger" style={{ padding: '3px 7px' }} onClick={() => containerAction(c.name, 'stop')} title="Stop"><Square size={11} /></button>
                            </>
                          ) : (
                            <button className="apple-btn apple-btn-primary" style={{ padding: '3px 7px' }} onClick={() => containerAction(c.name, 'start')} title="Start"><Play size={11} /></button>
                          )
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="ues-grid-2">
            <div className="studio-section-card">
              <span className="studio-section-title">Docker Networks ({docker.networks?.length || 0})</span>
              {(docker.networks || []).map((n) => (
                <div key={n.id} className="reference-card-item" style={{ marginBottom: '0.4rem' }}>
                  <strong>{n.name}</strong> · {n.driver} ({n.scope}) · {n.containers} attached
                </div>
              ))}
            </div>
            <div className="studio-section-card">
              <span className="studio-section-title">Docker Volumes ({docker.volumes?.length || 0})</span>
              {(docker.volumes || []).slice(0, 12).map((v) => (
                <div key={v.name} className="reference-card-item" style={{ marginBottom: '0.4rem' }}>
                  <code>{v.name}</code> ({v.driver})
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {subTab === 'kubernetes' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {!k8s.connected ? (
            <div className="studio-section-card">
              <h3>Kubernetes Cluster Status: {k8s.status}</h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', marginTop: '0.4rem' }}>
                {k8s.reason || 'Enable OrbStack Kubernetes, k3d, or kind to inspect nodes, pods, deployments, events, and CrashLoopBackOff chaos scenarios.'}
              </p>
            </div>
          ) : (
            <>
              <div className="studio-section-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
                  <span className="studio-section-title">Cluster Nodes ({k8s.git_version})</span>
                  <select className="apple-input" value={selectedNs} onChange={(e) => setSelectedNs(e.target.value)} style={{ width: '200px' }}>
                    <option value="all">All Namespaces</option>
                    {(k8s.namespaces || []).map((ns) => <option key={ns} value={ns}>{ns}</option>)}
                  </select>
                </div>
                <table className="apple-table">
                  <thead><tr><th>Node</th><th>Ready</th><th>Kubelet</th><th>CPU Cap</th><th>Mem Cap</th><th>Pressure</th></tr></thead>
                  <tbody>
                    {(k8s.nodes || []).map((n) => (
                      <tr key={n.name}>
                        <td style={{ fontWeight: 600 }}>{n.name}</td>
                        <td style={{ color: n.ready ? 'var(--apple-mint)' : 'var(--apple-coral)' }}>{n.ready ? 'Ready' : 'NotReady'}</td>
                        <td style={{ fontSize: '0.72rem' }}>{n.kubelet_version} ({n.arch})</td>
                        <td>{n.cpu_capacity}</td>
                        <td>{n.memory_capacity}</td>
                        <td>{n.pressure?.length ? n.pressure.join(', ') : 'None'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="studio-section-card" style={{ overflowX: 'auto' }}>
                <span className="studio-section-title">Pods ({k8sWorkloads?.pods?.length || 0})</span>
                <table className="apple-table">
                  <thead><tr><th>Namespace/Pod</th><th>Phase</th><th>Restarts</th><th>Reasons</th><th>Requests / Limits</th><th>Logs</th></tr></thead>
                  <tbody>
                    {(k8sWorkloads?.pods || []).map((p) => (
                      <tr key={`${p.namespace}/${p.name}`}>
                        <td><code>{p.namespace}/{p.name}</code></td>
                        <td style={{ color: p.phase === 'Running' ? 'var(--apple-mint)' : 'var(--apple-coral)' }}>{p.phase}</td>
                        <td style={{ color: p.restarts > 0 ? 'var(--apple-amber)' : 'var(--text-secondary)' }}>{p.restarts}</td>
                        <td style={{ fontSize: '0.72rem', color: 'var(--apple-coral)' }}>{p.reasons?.join(', ') || '-'}</td>
                        <td style={{ fontSize: '0.7rem' }}>Req: {p.requests.cpu}/{p.requests.memory} · Lim: {p.limits.cpu}/{p.limits.memory}</td>
                        <td><button className="apple-btn apple-btn-secondary" style={{ padding: '2px 7px' }} onClick={() => viewPodLogs(p.namespace, p.name)}><Terminal size={11} /></button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="ues-grid-2">
                <div className="studio-section-card">
                  <span className="studio-section-title">Deployments, StatefulSets, Services, Ingress, ConfigMaps & Secrets</span>
                  <div style={{ fontSize: '0.78rem', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <div>Deployments: <strong>{k8sWorkloads?.deployments?.length || 0}</strong></div>
                    <div>StatefulSets: <strong>{k8sWorkloads?.statefulsets?.length || 0}</strong></div>
                    <div>Services: <strong>{k8sWorkloads?.services?.length || 0}</strong></div>
                    <div>Ingresses: <strong>{k8sWorkloads?.ingresses?.length || 0}</strong></div>
                    <div>ConfigMaps: <strong>{k8sWorkloads?.configmaps?.length || 0}</strong></div>
                    <div>Secrets (metadata only): <strong>{k8sWorkloads?.secrets?.length || 0}</strong></div>
                  </div>
                </div>
                <div className="studio-section-card" style={{ maxHeight: '260px', overflowY: 'auto' }}>
                  <span className="studio-section-title">Cluster Events ({k8sWorkloads?.events?.length || 0})</span>
                  {(k8sWorkloads?.events || []).slice(0, 15).map((e, i) => (
                    <div key={i} className="reference-card-item" style={{ marginBottom: '4px' }}>
                      <strong style={{ color: e.type === 'Warning' ? 'var(--apple-amber)' : 'var(--apple-mint)' }}>{e.reason}</strong> · <code>{e.object}</code>
                      <div className="reference-card-desc">{e.message}</div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {logsTarget && (
        <div className="studio-section-card" style={{ marginTop: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span className="studio-section-title">Live Logs: {logsTarget}</span>
            <button className="apple-btn apple-btn-secondary" style={{ padding: '2px 8px' }} onClick={() => setLogsTarget('')}>Close</button>
          </div>
          <pre className="ues-terminal-out">{logLines.join('\n') || 'No log lines.'}</pre>
        </div>
      )}
    </div>
  );
}

