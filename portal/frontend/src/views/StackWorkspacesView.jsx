import React, { useState } from 'react';
import { Layers, RefreshCw } from 'lucide-react';

export const WORKSPACE_APPS = [
  { id: 'jupyter', label: 'JupyterLab Notebooks', stack: 'DE', url: '/services/databricks/' },
  { id: 'spark', label: 'Spark Master UI', stack: 'DE', url: '/services/spark/' },
  { id: 'airflow', label: 'Airflow DAGs', stack: 'DE', url: '/services/airflow/' },
  { id: 'pgadmin', label: 'pgAdmin 4 (SQL DW)', stack: 'DE', url: '/services/synapse/' },
  { id: 'minio', label: 'MinIO Data Lake', stack: 'DE', url: '/services/datalake/' },
  { id: 'redpanda', label: 'Redpanda Console', stack: 'DE', url: '/services/eventhub/' },
  { id: 'rabbitmq', label: 'RabbitMQ', stack: 'DE', url: '/services/servicebus/' },
  { id: 'grafana', label: 'Grafana Dashboards', stack: 'SRE', url: '/services/monitoring/' },
  { id: 'prometheus', label: 'Prometheus', stack: 'SRE', url: '/services/prometheus/graph' },
];

export function resolveWorkspacePath(rawUrl) {
  if (!rawUrl) return '/services/databricks/';
  try {
    if (rawUrl.startsWith('http://localhost:5173/')) {
      return rawUrl.replace('http://localhost:5173', '');
    }
    if (rawUrl.startsWith('http://localhost:8080')) return '/services/spark/';
    if (rawUrl.startsWith('http://localhost:9090')) return '/services/prometheus/graph';
    if (rawUrl.startsWith('http://localhost:8888')) return '/services/databricks/';
    if (rawUrl.startsWith('http://localhost:8085')) return '/services/airflow/';
    if (rawUrl.startsWith('http://localhost:5050')) return '/services/synapse/';
    if (rawUrl.startsWith('http://localhost:9001')) return '/services/datalake/';
    if (rawUrl.startsWith('http://localhost:3010')) return '/services/monitoring/';
    if (rawUrl.startsWith('http://localhost:8081')) return '/services/eventhub/';
    if (rawUrl.startsWith('http://localhost:15672')) return '/services/servicebus/';
  } catch {
    return rawUrl;
  }
  return rawUrl;
}

export default function StackWorkspacesView({ activeWorkspace, onSelectWorkspace }) {
  const [reloadNonce, setReloadNonce] = useState(0);
  const currentUrl = resolveWorkspacePath(activeWorkspace?.url || '/services/databricks/');
  const currentTitle = activeWorkspace?.title || 'JupyterLab Notebooks';

  return (
    <div className="view-container" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      <div className="section-header" style={{ marginBottom: 0 }}>
        <div>
          <h2 className="section-title">
            <Layers size={18} style={{ color: 'var(--apple-blue)' }} /> Unified Stack Workspace (Same Window)
          </h2>
          <p className="section-subtitle">
            Switch across every Data Engineering &amp; SRE web UI inside this same window — zero extra tabs
          </p>
        </div>
        <button
          className="apple-btn apple-btn-secondary"
          onClick={() => setReloadNonce((n) => n + 1)}
        >
          <RefreshCw size={12} /> Reload Active App
        </button>
      </div>

      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
        {WORKSPACE_APPS.map((app) => {
          const isActive = currentUrl === app.url || currentUrl.startsWith(app.url);
          return (
            <button
              key={app.id}
              className={`copilot-chip ${isActive ? 'active-chip' : ''}`}
              onClick={() => onSelectWorkspace({ title: app.label, url: app.url })}
            >
              <span style={{ opacity: 0.7, marginRight: '4px' }}>[{app.stack}]</span>
              {app.label}
            </button>
          );
        })}
      </div>

      <div className="studio-section-card" style={{ padding: 0, overflow: 'hidden', minHeight: '720px' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '0.5rem 0.85rem',
            borderBottom: '1px solid var(--border-subtle)',
            fontSize: '0.75rem',
            color: 'var(--text-secondary)',
          }}
        >
          <span>Active App: <strong style={{ color: '#fff' }}>{currentTitle}</strong></span>
          <span style={{ fontFamily: 'monospace' }}>{currentUrl}</span>
        </div>
        <iframe
          key={`${currentUrl}-${reloadNonce}`}
          src={currentUrl}
          title={currentTitle}
          style={{ width: '100%', height: '720px', border: 'none', background: '#0e1116' }}
        />
      </div>
    </div>
  );
}

