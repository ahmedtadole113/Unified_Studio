import React from 'react';
import {
  LayoutDashboard,
  Database,
  Radio,
  Server,
  Activity,
  ShieldAlert,
  DollarSign,
  Sparkles,
  Sliders,
  LogOut,
} from 'lucide-react';

export const NAV_DOMAINS = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard, color: '#2997ff' },
  { id: 'data_engineering', label: 'Data Engineering', icon: Database, color: '#ff453a' },
  { id: 'streaming', label: 'Streaming', icon: Radio, color: '#ff9f0a' },
  { id: 'infrastructure', label: 'Infrastructure', icon: Server, color: '#64d2ff' },
  { id: 'observability', label: 'Observability', icon: Activity, color: '#30d158' },
  { id: 'sre', label: 'SRE Ops', icon: ShieldAlert, color: '#ff375f' },
  { id: 'finops', label: 'FinOps', icon: DollarSign, color: '#ffd60a' },
  { id: 'aiops', label: 'AIOps', icon: Sparkles, color: '#af52de' },
];

export default function Navbar({
  user,
  activeDomain,
  setActiveDomain,
  healthCounts,
  onOpenSettings,
  onLogout,
}) {
  const healthy = healthCounts?.healthy ?? 0;
  const total = healthCounts?.total ?? 0;

  return (
    <header className="apple-navbar">
      <div className="nav-left" onClick={() => setActiveDomain('overview')} style={{ cursor: 'pointer' }}>
        <div className="apple-logo-badge">⚡</div>
        <div className="brand-info">
          <div className="brand-title">
            Unified Studio
            <span className="brand-badge">DE + SRE</span>
          </div>
        </div>
      </div>

      <nav className="nav-center">
        <div className="apple-pill-nav ues-nav-scroll">
          {NAV_DOMAINS.map((d) => {
            const Icon = d.icon;
            const isActive = activeDomain === d.id;
            return (
              <button
                key={d.id}
                className={`pill-item ${isActive ? 'active' : ''}`}
                onClick={() => setActiveDomain(d.id)}
              >
                <Icon size={13} style={{ color: isActive ? '#ffffff' : d.color }} />
                {d.label}
              </button>
            );
          })}
        </div>
      </nav>

      <div className="nav-right">
        <div className="system-pulse-pill" title="Live Service Registry Health">
          <div className={`pulse-dot ${healthy > 0 ? 'online' : 'offline'}`} />
          <span>{healthy}/{total || '—'} Healthy</span>
        </div>

        <div className="user-profile-pill" onClick={onOpenSettings} title="Settings, RBAC & Audit Logs">
          <div className="user-avatar-pip">{user.username.charAt(0).toUpperCase()}</div>
          <span>{user.username}</span>
          <Sliders size={12} style={{ opacity: 0.6 }} />
        </div>

        <button
          className="apple-btn apple-btn-secondary"
          onClick={onLogout}
          style={{ padding: '4px 10px', fontSize: '0.72rem' }}
          title="Sign Out"
        >
          <LogOut size={12} />
        </button>
      </div>
    </header>
  );
}

