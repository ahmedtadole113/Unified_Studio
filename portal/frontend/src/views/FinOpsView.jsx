import React, { useEffect, useState } from 'react';
import { Cpu, DollarSign, HardDrive, RefreshCw, TrendingUp } from 'lucide-react';
import { apiFetch, API_V1 } from '../api/client';

export default function FinOpsView() {
  const [data, setData] = useState(null);

  const loadFinOps = async () => {
    try {
      const res = await apiFetch(`${API_V1}/finops/overview`);
      setData(res);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadFinOps();
    const t = setInterval(loadFinOps, 8000);
    return () => clearInterval(t);
  }, []);

  if (!data) return <div className="view-container"><div className="apple-hero">Measuring live container & storage utilization...</div></div>;

  const alloc = data.allocation || {};
  const cost = data.cost_model || {};
  const forecast = data.forecast || {};

  return (
    <div className="view-container">
      <div className="section-header">
        <div>
          <h2 className="section-title"><DollarSign size={18} style={{ color: 'var(--apple-gold)' }} /> FinOps & Capacity Management</h2>
          <p className="section-subtitle">{data.hardware_target} · Live Measured RAM/CPU/Network/Storage Utilization & Cost Estimation</p>
        </div>
        <button className="apple-btn apple-btn-secondary" onClick={loadFinOps}><RefreshCw size={12} /> Refresh</button>
      </div>

      <div className="hero-stats-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(185px, 1fr))', marginBottom: '1.25rem' }}>
        <div className="stat-capsule">
          <span className="stat-label">Measured RAM Usage</span>
          <span className="stat-value" style={{ color: 'var(--apple-blue)' }}>{alloc.total_memory_mb} MB</span>
          <span className="stat-desc">{forecast.ram_budget_used_pct}% of {forecast.safe_ram_ceiling_mb} MB ceiling</span>
        </div>
        <div className="stat-capsule">
          <span className="stat-label">M4 RAM Headroom</span>
          <span className="stat-value" style={{ color: 'var(--apple-mint)' }}>{forecast.ram_headroom_mb} MB</span>
          <span className="stat-desc">{alloc.running_containers} running containers</span>
        </div>
        <div className="stat-capsule">
          <span className="stat-label">Aggregate CPU Load</span>
          <span className="stat-value" style={{ color: 'var(--apple-cyan)' }}>{alloc.total_cpu_percent}%</span>
          <span className="stat-desc">Net RX {alloc.network_rx_mb} / TX {alloc.network_tx_mb} MB</span>
        </div>
        <div className="stat-capsule">
          <span className="stat-label">Data Lake + DW Storage</span>
          <span className="stat-value" style={{ color: 'var(--apple-amber)' }}>{alloc.storage_mb} MB</span>
          <span className="stat-desc">30d forecast: {forecast.projected_30d_storage_mb} MB</span>
        </div>
        <div className="stat-capsule">
          <span className="stat-label">Estimated Cloud Run Rate</span>
          <span className="stat-value" style={{ color: 'var(--apple-gold)' }}>${cost.estimated_monthly_usd}/mo</span>
          <span className="stat-desc">${cost.estimated_hourly_usd}/hr compute + storage</span>
        </div>
      </div>

      <div className="ues-grid-2">
        <div className="studio-section-card">
          <span className="studio-section-title">Service-Wise Cost & Resource Breakdown</span>
          <table className="apple-table">
            <thead><tr><th>Service</th><th>CPU</th><th>Memory</th><th>Net I/O</th><th>Est. $/mo</th></tr></thead>
            <tbody>
              {(cost.service_breakdown || []).map((s) => (
                <tr key={s.service}>
                  <td style={{ fontWeight: 600 }}>{s.service}</td>
                  <td>{s.cpu_percent}%</td>
                  <td>{s.memory_mb} / {s.memory_limit_mb} MB</td>
                  <td style={{ fontSize: '0.72rem' }}>{s.network_rx_mb}/{s.network_tx_mb} MB</td>
                  <td style={{ color: 'var(--apple-gold)', fontWeight: 600 }}>${s.estimated_monthly_usd}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="studio-section-card">
          <span className="studio-section-title">Idle Resource Identification & Capacity Advice</span>
          <div className="reference-card-item" style={{ marginBottom: '0.6rem' }}>
            <strong style={{ color: 'var(--apple-mint)' }}><TrendingUp size={13} /> Capacity Forecast ({forecast.status?.toUpperCase()})</strong>
            <div className="reference-card-desc" style={{ marginTop: '4px' }}>{forecast.recommendation}</div>
          </div>
          {(data.idle_resources || []).map((r, i) => (
            <div key={i} className="reference-card-item" style={{ marginBottom: '0.5rem' }}>
              <strong style={{ color: 'var(--apple-amber)' }}>Idle Container: {r.container}</strong> ({r.memory_mb} MB · {r.cpu_percent}% CPU)
              <div className="reference-card-desc">{r.recommendation}</div>
            </div>
          ))}
          {(!data.idle_resources || data.idle_resources.length === 0) && (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>No idle heavy containers detected right now.</div>
          )}
        </div>
      </div>
    </div>
  );
}

