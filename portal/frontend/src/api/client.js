/**
 * Unified API Client with Bearer Token Auth & Error Normalization.
 */

export const API_V1 = '/api/v1';
export const API_LEGACY = '/api';

export function getStoredAuth() {
  try {
    const raw = localStorage.getItem('ues_auth');
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setStoredAuth(auth) {
  if (auth) {
    localStorage.setItem('ues_auth', JSON.stringify(auth));
  } else {
    localStorage.removeItem('ues_auth');
  }
}

export async function apiFetch(path, options = {}) {
  const auth = getStoredAuth();
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };
  if (auth?.access_token) {
    headers['Authorization'] = `Bearer ${auth.access_token}`;
  }

  const res = await fetch(path, { ...options, headers });
  if (res.status === 401) {
    setStoredAuth(null);
    window.dispatchEvent(new CustomEvent('ues:unauthorized'));
    throw new Error('Session expired. Please sign in again.');
  }
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { detail: text };
  }
  if (!res.ok) {
    throw new Error(data?.detail || data?.error || `HTTP ${res.status}`);
  }
  return data;
}

