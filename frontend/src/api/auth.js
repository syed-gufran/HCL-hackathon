const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

export async function loginRequest(email, password, expectedRole) {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, expected_role: expectedRole }),
  });
  if (!res.ok) throw new Error('Invalid credentials');
  return res.json();
}

export async function registerRequest(name, email, password, department = 'General') {
  const res = await fetch(`${API_BASE}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, email, password, department }),
  });
  if (!res.ok) {
    const msg = await res.text();
    throw new Error(msg || 'Registration failed');
  }
  return res.json();
}

export async function getMe(token) {
  const res = await fetch(`${API_BASE}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Unauthorized');
  return res.json();
}

export async function logoutRequest(token) {
  const res = await fetch(`${API_BASE}/api/auth/logout`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Logout failed');
  return res.json();
}
