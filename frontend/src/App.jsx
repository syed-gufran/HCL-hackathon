import React, { useState } from 'react';
import Login from './pages/Login';
import AdminDashboard from './pages/AdminDashboard';
import UserDashboard from './pages/UserDashboard';
import { globalInitialTickets } from './data/mockData';
import { getAnalytics, getAdminTickets } from './api/admin';
import { logoutRequest } from './api/auth';
import { getUserTickets } from './api/user';

export default function App() {
  const [authState, setAuthState] = useState({ isAuthenticated: false, role: null, token: null, user: null });
  const [tickets, setTickets] = useState(globalInitialTickets);
  const [analytics, setAnalytics] = useState(null);
  const [adminLoading, setAdminLoading] = useState(false);
  const [adminError, setAdminError] = useState('');
  const [userLoading, setUserLoading] = useState(false);
  const [userError, setUserError] = useState('');

  const mapApiTicket = (t) => ({
    ticket_id: t.ticket_id,
    id: `T-${t.ticket_id}`,
    issue: t.title,
    description: t.description,
    category: t.category,
    status: t.status,
    priority: t.priority,
    date: t.created_date?.split?.('T')?.[0] || '',
    ai_suggestion: t.ai_suggestion || t.resolution_text || 'Use guided troubleshooting for this category.',
    resolution: t.resolution_text || '',
    author: 'other',
  });

  const loadAdminData = async (token) => {
    setAdminLoading(true);
    setAdminError('');
    try {
      const [analyticsData, ticketsData] = await Promise.all([
        getAnalytics(token),
        getAdminTickets(token),
      ]);
      setAnalytics(analyticsData);
      setTickets(ticketsData.map(mapApiTicket));
    } catch (err) {
      setAdminError(err.message || 'Failed to load admin data');
    } finally {
      setAdminLoading(false);
    }
  };

  const loadUserData = async (token) => {
    setUserLoading(true);
    setUserError('');
    try {
      const rows = await getUserTickets(token);
      const mapped = rows.map((t) => ({
        ticket_id: t.ticket_id,
        id: `T-${t.ticket_id}`,
        issue: t.title,
        description: t.description,
        category: t.category,
        status: t.status,
        priority: t.priority,
        date: t.created_date?.split?.('T')?.[0] || '',
        ai_suggestion: t.ai_suggestion || t.resolution_text || 'Pending NLP recommendation.',
        resolution: t.resolution_text || '',
        author: 'me',
      }));
      setTickets(mapped);
    } catch (err) {
      setUserError(err.message || 'Failed to load user tickets');
    } finally {
      setUserLoading(false);
    }
  };

  const handleLoginSuccess = async (session) => {
    const next = { isAuthenticated: true, role: session.user.role, token: session.token, user: session.user };
    setAuthState(next);
    if (session.user.role === 'admin') {
      await loadAdminData(session.token);
    } else {
      await loadUserData(session.token);
    }
  };

  const handleLogout = async () => {
    if (authState.token) {
      try {
        await logoutRequest(authState.token);
      } catch {
        // no-op
      }
    }
    setAuthState({ isAuthenticated: false, role: null, token: null, user: null });
    setAnalytics(null);
    setUserError('');
    setAdminError('');
  };

  if (!authState.isAuthenticated) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

  if (authState.role === 'admin') {
    return (
      <AdminDashboard
        tickets={tickets}
        setTickets={setTickets}
        onLogout={handleLogout}
        analytics={analytics}
        loading={adminLoading}
        error={adminError}
        onRefresh={() => loadAdminData(authState.token)}
        token={authState.token}
      />
    );
  }

  return (
    <UserDashboard
      tickets={tickets}
      setTickets={setTickets}
      onLogout={handleLogout}
      token={authState.token}
      onRefresh={() => loadUserData(authState.token)}
      loading={userLoading}
      error={userError}
    />
  );
}
