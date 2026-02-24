import React, { useState, useMemo } from 'react';
import { PieChart, Pie, Cell, Tooltip as RechartsTooltip, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts';
import { Terminal, LayoutDashboard, Ticket as TicketIcon, LogOut, Clock, AlertCircle, CheckCircle, X, RefreshCw } from 'lucide-react';
import { COLORS } from '../data/mockData';
import { updateAdminTicket } from '../api/admin';

export default function AdminDashboard({ tickets, setTickets, onLogout, analytics, loading, error, onRefresh, token }) {
  const [currentView, setCurrentView] = useState('dashboard');
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [editForm, setEditForm] = useState({ status: '', resolution: '' });
  const [saveError, setSaveError] = useState('');
  const [saving, setSaving] = useState(false);
  const [filters, setFilters] = useState({ status: 'All', category: 'All', priority: 'All', q: '' });

  const pendingCount = analytics?.pending_tickets ?? tickets.filter((t) => t.status !== 'Resolved').length;
  const resolvedCount = analytics?.resolved_tickets ?? tickets.filter((t) => t.status === 'Resolved').length;
  const avgResolutionHours = analytics?.avg_resolution_hours ?? 2.4;
  const priorityData = useMemo(
    () => Object.entries(analytics?.priority_distribution || {}).map(([name, value]) => ({ name, value })),
    [analytics]
  );
  const dailyVolume = analytics?.daily_volume || [];
  const categoryRates = analytics?.category_resolution_rates || [];
  const topResolutions = analytics?.top_resolutions || [];
  const tooltipStyle = {
    backgroundColor: '#f8fafc',
    border: '1px solid #94a3b8',
    color: '#0f172a',
    borderRadius: '8px',
    fontSize: '12px',
  };
  const filteredTickets = useMemo(() => {
    return tickets.filter((t) => {
      const idText = `${t.id || ''} ${t.ticket_id || ''}`.toLowerCase();
      const textBlob = `${t.issue} ${t.description}`.toLowerCase();
      if (filters.status !== 'All' && t.status !== filters.status) return false;
      if (filters.category !== 'All' && t.category !== filters.category) return false;
      if (filters.priority !== 'All' && t.priority !== filters.priority) return false;
      if (filters.q) {
        const q = filters.q.toLowerCase().trim();
        if (!idText.includes(q) && !textBlob.includes(q)) return false;
      }
      return true;
    });
  }, [tickets, filters]);

  const categoryData = useMemo(() => {
    if (analytics?.category_distribution) return analytics.category_distribution;
    const counts = {};
    tickets.forEach((t) => {
      counts[t.category] = (counts[t.category] || 0) + 1;
    });
    return Object.keys(counts).map((key) => ({ name: key, value: counts[key] }));
  }, [tickets]);

  const handleRowClick = (ticket) => {
    setSelectedTicket(ticket);
    setEditForm({ status: ticket.status, resolution: ticket.resolution });
  };

  const handleSave = async () => {
    if (!selectedTicket?.ticket_id) {
      setSaveError('Missing ticket id');
      return;
    }
    setSaveError('');
    setSaving(true);
    try {
      await updateAdminTicket(token, selectedTicket.ticket_id, editForm.status, editForm.resolution);
      await onRefresh();
      setSelectedTicket(null);
    } catch (err) {
      setSaveError(err.message || 'Failed to save ticket');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex h-screen w-full bg-[#0B0B0F] text-zinc-100 font-sans">
      <div className="w-64 bg-[#0B0B0F] border-r border-zinc-800/60 text-zinc-300 flex flex-col h-full shrink-0">
        <div className="p-6 border-b border-zinc-800/60 flex items-center gap-3">
          <div className="w-8 h-8 bg-white rounded-md flex items-center justify-center"><Terminal size={18} className="text-black" /></div>
          <div><h2 className="text-sm font-bold text-white tracking-tight">SupportEngine</h2><p className="font-mono text-[10px] text-zinc-500 uppercase tracking-widest mt-0.5">Admin Portal</p></div>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          <button onClick={() => setCurrentView('dashboard')} className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md transition-all text-sm font-medium ${currentView === 'dashboard' ? 'bg-zinc-800/50 text-white' : 'text-zinc-400 hover:bg-zinc-800/30'}`}><LayoutDashboard size={18} /><span>Overview</span></button>
          <button onClick={() => setCurrentView('tickets')} className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md transition-all text-sm font-medium ${currentView === 'tickets' ? 'bg-zinc-800/50 text-white' : 'text-zinc-400 hover:bg-zinc-800/30'}`}><TicketIcon size={18} /><span>Tickets</span></button>
        </nav>
        <div className="p-4 border-t border-zinc-800/60">
          <button onClick={onLogout} className="flex items-center gap-3 w-full px-3 py-2.5 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/30 rounded-md transition-colors text-sm font-medium"><LogOut size={18} /><span>Logout</span></button>
        </div>
      </div>

      <main className="flex-1 h-full overflow-y-auto relative p-8">
        {currentView === 'dashboard' ? (
          <div className="animate-in fade-in duration-500">
            <div className="flex items-center justify-between mb-8">
              <h1 className="text-2xl font-bold text-white">Analytics Overview</h1>
              <button onClick={onRefresh} className="px-3 py-2 text-xs rounded-md border border-zinc-700 hover:bg-zinc-800 flex items-center gap-2">
                <RefreshCw size={14} /> Refresh
              </button>
            </div>
            {loading ? <p className="text-sm text-zinc-400 mb-4">Loading analytics from DB...</p> : null}
            {error ? <p className="text-sm text-red-400 mb-4">{error}</p> : null}
            <div className="grid grid-cols-3 gap-4 mb-8">
              <div className="bg-[#111115] p-5 rounded-lg border border-zinc-800 flex justify-between"><div className="text-zinc-400 text-xs">Pending Tickets<h3 className="text-2xl font-bold text-white mt-1">{pendingCount}</h3></div><AlertCircle className="text-amber-400" /></div>
              <div className="bg-[#111115] p-5 rounded-lg border border-zinc-800 flex justify-between"><div className="text-zinc-400 text-xs">Avg Resolution Time<h3 className="text-2xl font-bold text-white mt-1">{avgResolutionHours}h</h3></div><Clock className="text-indigo-400" /></div>
              <div className="bg-[#111115] p-5 rounded-lg border border-zinc-800 flex justify-between"><div className="text-zinc-400 text-xs">Total Resolved<h3 className="text-2xl font-bold text-white mt-1">{resolvedCount}</h3></div><CheckCircle className="text-emerald-400" /></div>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="bg-[#111115] p-6 rounded-lg border border-zinc-800 h-72">
                <h2 className="text-sm font-semibold mb-4">Category Distribution</h2>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={categoryData} dataKey="value" cx="50%" cy="50%" innerRadius={70} outerRadius={90}>
                      {categoryData.map((entry, i) => <Cell key={entry.name} fill={COLORS[i % COLORS.length]} />)}
                    </Pie>
                    <RechartsTooltip contentStyle={tooltipStyle} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="bg-[#111115] p-6 rounded-lg border border-zinc-800 h-72">
                <h2 className="text-sm font-semibold mb-4">Priority Distribution</h2>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={priorityData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis dataKey="name" stroke="#a1a1aa" />
                    <YAxis stroke="#a1a1aa" />
                    <RechartsTooltip contentStyle={tooltipStyle} />
                    <Bar dataKey="value" fill="#818cf8" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-[#111115] p-6 rounded-lg border border-zinc-800">
                <h2 className="text-sm font-semibold mb-4">Daily Ticket Volume (14 days)</h2>
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={dailyVolume}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis dataKey="date" stroke="#a1a1aa" hide />
                    <YAxis stroke="#a1a1aa" />
                    <RechartsTooltip contentStyle={tooltipStyle} />
                    <Bar dataKey="count" fill="#34d399" />
                  </BarChart>
                </ResponsiveContainer>
                <div className="mt-3 text-xs text-zinc-400">Latest day count: {dailyVolume.length ? dailyVolume[dailyVolume.length - 1].count : 0}</div>
              </div>
              <div className="bg-[#111115] p-6 rounded-lg border border-zinc-800">
                <h2 className="text-sm font-semibold mb-4">Category Resolution Rates</h2>
                <div className="space-y-2 text-xs">
                  {categoryRates.map((r) => (
                    <div key={r.name} className="flex items-center justify-between bg-zinc-900/50 px-3 py-2 rounded">
                      <span>{r.name}</span>
                      <span className="text-zinc-400">{r.resolved} resolved / {r.open} open</span>
                      <span className="text-emerald-400 font-semibold">{r.rate}%</span>
                    </div>
                  ))}
                </div>
                <h3 className="text-sm font-semibold mt-5 mb-2">Top Helpful Resolutions</h3>
                <div className="space-y-2 text-xs max-h-24 overflow-auto">
                  {topResolutions.map((r) => (
                    <div key={r.resolution_id} className="bg-zinc-900/50 px-3 py-2 rounded">
                      <div className="text-zinc-400 mb-1">Ticket #{r.ticket_id} · Helpful {r.helpful_count}</div>
                      <div className="text-zinc-200">{r.resolution_text}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="h-full flex flex-col animate-in fade-in duration-500">
            <div className="flex items-center justify-between mb-6">
              <h1 className="text-2xl font-bold text-white">Ticket Management</h1>
              <button onClick={onRefresh} className="px-3 py-2 text-xs rounded-md border border-zinc-700 hover:bg-zinc-800 flex items-center gap-2">
                <RefreshCw size={14} /> Refresh
              </button>
            </div>
            <div className="grid grid-cols-4 gap-3 mb-4">
              <select value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })} className="bg-[#111115] border border-zinc-800 rounded px-3 py-2 text-xs">
                <option>All</option><option>Open</option><option>In Progress</option><option>Resolved</option>
              </select>
              <select value={filters.category} onChange={(e) => setFilters({ ...filters, category: e.target.value })} className="bg-[#111115] border border-zinc-800 rounded px-3 py-2 text-xs">
                <option>All</option><option>Software</option><option>Access</option><option>Hardware</option><option>Network</option>
              </select>
              <select value={filters.priority} onChange={(e) => setFilters({ ...filters, priority: e.target.value })} className="bg-[#111115] border border-zinc-800 rounded px-3 py-2 text-xs">
                <option>All</option><option>low</option><option>med</option><option>high</option>
              </select>
              <input value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} placeholder="Search by ticket ID or text (e.g. T-120)" className="bg-[#111115] border border-zinc-800 rounded px-3 py-2 text-xs" />
            </div>
            <div className="bg-[#111115] rounded-lg border border-zinc-800 flex-1 overflow-auto">
              <table className="w-full text-left">
                <thead className="bg-[#0B0B0F] border-b border-zinc-800"><tr><th className="p-4 text-xs text-zinc-500">ID</th><th className="p-4 text-xs text-zinc-500">Issue</th><th className="p-4 text-xs text-zinc-500">Category</th><th className="p-4 text-xs text-zinc-500">Priority</th><th className="p-4 text-xs text-zinc-500">Status</th></tr></thead>
                <tbody className="divide-y divide-zinc-800/60">
                  {filteredTickets.map((t) => (
                    <tr key={t.id} onClick={() => handleRowClick(t)} className="cursor-pointer transition-colors hover:bg-sky-500/15 hover:ring-1 hover:ring-sky-400/30">
                      <td className="p-4 font-mono text-xs text-zinc-400">{t.id}</td><td className="p-4 text-sm">{t.issue}</td><td className="p-4 text-xs text-zinc-300">{t.category}</td><td className="p-4 text-xs text-zinc-300 uppercase">{t.priority}</td>
                      <td className="p-4"><span className="px-2 py-1 text-xs border border-zinc-700 bg-zinc-800 rounded">{t.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {selectedTicket && (
              <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex justify-end">
                <div className="w-full max-w-lg bg-[#0B0B0F] border-l border-zinc-800 h-full shadow-2xl flex flex-col p-6">
                  <div className="flex justify-between items-center mb-6"><h2 className="text-lg font-bold text-white">{selectedTicket.issue}</h2><button onClick={() => setSelectedTicket(null)}><X size={18} /></button></div>
                  <div className="flex-1 overflow-y-auto space-y-6">
                    <div><label className="text-xs text-zinc-500 block mb-2">Description</label><div className="bg-[#111115] p-3 rounded border border-zinc-800 text-sm">{selectedTicket.description}</div></div>
                    <div><label className="text-xs text-zinc-500 block mb-2 flex items-center gap-2"><Terminal size={14} className="text-indigo-400" /> NLP Suggestion</label><div className="bg-indigo-500/10 p-4 border border-indigo-500/20 rounded font-mono text-sm text-indigo-300">{`> ${selectedTicket.ai_suggestion}`}</div></div>
                    <div><label className="text-xs text-zinc-500 block mb-2">Status</label><div className="flex gap-2">{['Open', 'In Progress', 'Resolved'].map((s) => <button key={s} onClick={() => setEditForm({ ...editForm, status: s })} className={`flex-1 py-2 rounded text-sm border ${editForm.status === s ? 'bg-white text-black' : 'border-zinc-800 text-zinc-400'}`}>{s}</button>)}</div></div>
                    <div><label className="text-xs text-zinc-500 block mb-2">Resolution Note</label><textarea value={editForm.resolution} onChange={(e) => setEditForm({ ...editForm, resolution: e.target.value })} className="w-full p-3 bg-[#111115] border border-zinc-800 rounded text-sm text-white resize-none h-24" /></div>
                  </div>
                  {saveError ? <p className="text-xs text-red-400 mt-2">{saveError}</p> : null}
                  <button onClick={handleSave} disabled={saving} className="w-full mt-4 py-3 bg-white text-black font-semibold rounded hover:bg-zinc-200 disabled:opacity-70">{saving ? 'Saving...' : 'Save Changes'}</button>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
