import React, { useEffect, useState } from 'react';
import { Key, Shield, Trash2, Users, FileText } from 'lucide-react';
import { apiFetch, API_V1 } from '../api/client';

export default function SettingsModal({ user, open, onClose, geminiKey, setGeminiKey }) {
  const [tab, setTab] = useState('security');
  const [users, setUsers] = useState([]);
  const [audits, setAudits] = useState([]);
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState('user');
  const [error, setError] = useState(null);

  const isAdmin = user?.role === 'admin';

  const loadData = async () => {
    try {
      const a = await apiFetch(`${API_V1}/platform/audit?limit=40`);
      setAudits(a.logs || []);
      if (isAdmin) {
        const u = await apiFetch(`${API_V1}/auth/users`);
        setUsers(u || []);
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    if (open) loadData();
  }, [open]);

  if (!open) return null;

  const handleCreateUser = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      await apiFetch(`${API_V1}/auth/users`, {
        method: 'POST',
        body: JSON.stringify({ username: newUsername, password: newPassword, role: newRole }),
      });
      setNewUsername('');
      setNewPassword('');
      setNewRole('user');
      loadData();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDeleteUser = async (uname) => {
    if (!confirm(`Delete user ${uname}?`)) return;
    try {
      await apiFetch(`${API_V1}/auth/users/${uname}`, { method: 'DELETE' });
      loadData();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="apple-modal-overlay" onClick={onClose}>
      <div className="apple-modal-sheet" style={{ maxWidth: '680px', width: '92vw' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="apple-gradient-text" style={{ fontSize: '1.2rem' }}>
            Studio Security, RBAC & Audit Trail
          </h2>
          <button className="apple-btn apple-btn-secondary" onClick={onClose} style={{ padding: '4px 10px', fontSize: '0.74rem' }}>
            Done
          </button>
        </div>

        <div className="studio-segmented-tabs" style={{ marginBottom: '1rem' }}>
          <button className={`studio-tab-btn ${tab === 'security' ? 'active' : ''}`} onClick={() => setTab('security')}>
            <Shield size={12} /> AI & Users
          </button>
          <button className={`studio-tab-btn ${tab === 'audit' ? 'active' : ''}`} onClick={() => setTab('audit')}>
            <FileText size={12} /> Audit Log ({audits.length})
          </button>
        </div>

        {tab === 'security' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div className="studio-section-card">
              <span className="studio-section-title">Google Gemini API Key (Optional)</span>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <Key size={15} style={{ color: geminiKey ? 'var(--apple-amber)' : 'var(--text-muted)' }} />
                <input
                  type="password"
                  className="apple-input"
                  placeholder="Enter Gemini API key..."
                  value={geminiKey}
                  onChange={(e) => {
                    setGeminiKey(e.target.value);
                    localStorage.setItem('gemini_api_key', e.target.value);
                  }}
                  style={{ flex: 1 }}
                />
              </div>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                Used for generative PySpark/SQL synthesis and AIOps RCA; FAISS playbooks work locally without a key.
              </span>
            </div>

            {isAdmin && (
              <div className="studio-section-card">
                <span className="studio-section-title">
                  <Users size={12} /> RBAC Accounts (PBKDF2-HMAC-SHA256 + Bearer JWT)
                </span>
                {error && <div className="ues-alert-banner danger">{error}</div>}
                <table className="apple-table" style={{ marginBottom: '0.75rem' }}>
                  <thead>
                    <tr>
                      <th>User</th>
                      <th>Role</th>
                      <th>Hashing</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr key={u.username}>
                        <td style={{ fontWeight: 600 }}>{u.username}</td>
                        <td>
                          <span className={`hero-pill-badge ${u.role === 'admin' ? 'primary' : 'secondary'}`}>{u.role}</span>
                        </td>
                        <td style={{ fontSize: '0.72rem', color: 'var(--apple-mint)' }}>{u.hashed ? 'PBKDF2' : 'Legacy'}</td>
                        <td>
                          {['aariz', 'ariz'].includes(u.username) ? (
                            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Bootstrap</span>
                          ) : (
                            <button onClick={() => handleDeleteUser(u.username)} style={{ background: 'none', border: 'none', color: 'var(--apple-coral)', cursor: 'pointer' }}>
                              <Trash2 size={14} />
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <form onSubmit={handleCreateUser} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <input className="apple-input" placeholder="Username" value={newUsername} onChange={(e) => setNewUsername(e.target.value)} required style={{ flex: 1 }} />
                  <input type="password" className="apple-input" placeholder="Password (min 4 chars)" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required style={{ flex: 1 }} />
                  <select className="apple-input" value={newRole} onChange={(e) => setNewRole(e.target.value)} style={{ width: '95px' }}>
                    <option value="user">user</option>
                    <option value="admin">admin</option>
                  </select>
                  <button type="submit" className="apple-btn apple-btn-primary">Add</button>
                </form>
              </div>
            )}
          </div>
        )}

        {tab === 'audit' && (
          <div className="studio-section-card" style={{ maxHeight: '380px', overflowY: 'auto' }}>
            <table className="apple-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Actor</th>
                  <th>Action</th>
                  <th>Resource</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {audits.map((a) => (
                  <tr key={a.id}>
                    <td style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{new Date(a.created_at * 1000).toLocaleTimeString()}</td>
                    <td style={{ fontWeight: 600 }}>{a.username} ({a.role})</td>
                    <td><code>{a.action}</code></td>
                    <td style={{ fontSize: '0.74rem' }}>{a.resource}</td>
                    <td style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>{a.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

