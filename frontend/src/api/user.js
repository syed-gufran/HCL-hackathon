const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

export async function getUserTickets(token, status = null) {
  const url = new URL(`${API_BASE}/api/user/tickets`);
  if (status) url.searchParams.set('status', status);
  const res = await fetch(url.toString(), {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Failed to fetch user tickets');
  return res.json();
}

export async function createUserTicket(token, payload) {
  const res = await fetch(`${API_BASE}/api/user/tickets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to create ticket');
  return res.json();
}

export async function resolveUserTicket(token, ticketId, resolution) {
  const res = await fetch(`${API_BASE}/api/user/tickets/${ticketId}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ resolution }),
  });
  if (!res.ok) throw new Error('Failed to resolve ticket');
  return res.json();
}
