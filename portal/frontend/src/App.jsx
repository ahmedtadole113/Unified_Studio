import React, { useEffect, useState } from 'react';
import { apiFetch, API_V1, getStoredAuth, setStoredAuth } from './api/client';
import Navbar from './components/Navbar';
import SettingsModal from './components/SettingsModal';
import PlatformOverview from './views/PlatformOverview';
import DataEngineeringView from './views/DataEngineeringView';
import StreamingMessagingView from './views/StreamingMessagingView';
import InfrastructureView from './views/InfrastructureView';
import ObservabilityView from './views/ObservabilityView';
import SreOperationsView from './views/SreOperationsView';
import FinOpsView from './views/FinOpsView';
import AiOpsView from './views/AiOpsView';

export default function App() {
  const [auth, setAuth] = useState(() => getStoredAuth());
  const [activeDomain, setActiveDomain] = useState('overview');
  const [healthCounts, setHealthCounts] = useState({ healthy: 0, total: 0 });
  const [showSettings, setShowSettings] = useState(false);
  const [geminiKey, setGeminiKey] = useState(() => localStorage.getItem('gemini_api_key') || '');

  const [loginUsername, setLoginUsername] = useState('aariz');
  const [loginPassword, setLoginPassword] = useState('aariz');
  const [loginError, setLoginError] = useState(null);

  useEffect(() => {
    const onUnauthorized = () => setAuth(null);
    window.addEventListener('ues:unauthorized', onUnauthorized);
    return () => window.removeEventListener('ues:unauthorized', onUnauthorized);
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginError(null);
    try {
      const data = await apiFetch(`${API_V1}/auth/login`, {
        method: 'POST',
        body: JSON.stringify({ username: loginUsername, password: loginPassword }),
      });
      const session = {
        username: data.username,
        role: data.role,
        access_token: data.access_token,
      };
      setStoredAuth(session);
      setAuth(session);
      setActiveDomain('overview');
    } catch (err) {
      setLoginError(err.message);
    }
  };

  const handleLogout = () => {
    setStoredAuth(null);
    setAuth(null);
  };

  if (!auth?.access_token) {
    return (
      <div className="apple-login-overlay">
        <form className="apple-login-card" onSubmit={handleLogin}>
          <div style={{ textAlign: 'center' }}>
            <div className="apple-logo-badge" style={{ width: '46px', height: '46px', margin: '0 auto 1rem auto', fontSize: '1.4rem' }}>
              ⚡
            </div>
            <h2 className="apple-gradient-text" style={{ fontSize: '1.35rem', marginBottom: '4px' }}>
              Unified Engineering Studio
            </h2>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
              Data Engineering · SRE · Kubernetes · FinOps · AIOps
            </p>
          </div>

          {loginError && <div className="ues-alert-banner danger">{loginError}</div>}

          <div className="apple-input-group">
            <label className="apple-input-label">Username</label>
            <input
              type="text"
              className="apple-input"
              value={loginUsername}
              onChange={(e) => setLoginUsername(e.target.value)}
              required
            />
          </div>

          <div className="apple-input-group">
            <label className="apple-input-label">Password</label>
            <input
              type="password"
              className="apple-input"
              value={loginPassword}
              onChange={(e) => setLoginPassword(e.target.value)}
              required
            />
          </div>

          <button type="submit" className="apple-btn apple-btn-primary" style={{ padding: '0.7rem', width: '100%', marginTop: '0.5rem', borderRadius: '12px' }}>
            Sign In to Unified Studio
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="app-container">
      <Navbar
        user={auth}
        activeDomain={activeDomain}
        setActiveDomain={setActiveDomain}
        healthCounts={healthCounts}
        onOpenSettings={() => setShowSettings(true)}
        onLogout={handleLogout}
      />

      <main className="content-area">
        {activeDomain === 'overview' && (
          <PlatformOverview user={auth} onNavigate={setActiveDomain} onHealthUpdate={setHealthCounts} />
        )}
        {activeDomain === 'data_engineering' && <DataEngineeringView user={auth} />}
        {activeDomain === 'streaming' && <StreamingMessagingView user={auth} />}
        {activeDomain === 'infrastructure' && <InfrastructureView user={auth} />}
        {activeDomain === 'observability' && <ObservabilityView user={auth} />}
        {activeDomain === 'sre' && <SreOperationsView user={auth} />}
        {activeDomain === 'finops' && <FinOpsView user={auth} />}
        {activeDomain === 'aiops' && <AiOpsView user={auth} geminiKey={geminiKey} />}
      </main>

      <SettingsModal
        user={auth}
        open={showSettings}
        onClose={() => setShowSettings(false)}
        geminiKey={geminiKey}
        setGeminiKey={setGeminiKey}
      />
    </div>
  );
}
