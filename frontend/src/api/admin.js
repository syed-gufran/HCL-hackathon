const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

export async function getAnalytics(token) {
  const res = await fetch(`${API_BASE}/api/analytics/overview`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Failed to fetch analytics');
  return res.json();
}

export async function getAdminTickets(token) {
  const res = await fetch(`${API_BASE}/api/tickets`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Failed to fetch tickets');
  return res.json();
}
