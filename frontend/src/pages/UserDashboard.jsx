import React, { useState, useEffect } from 'react';
import { Terminal, PlusCircle, Ticket as TicketIcon, LogOut, Sparkles, ArrowRight, CheckCircle2, RefreshCw } from 'lucide-react';
import { fetchNlpSuggestions, sendNlpFeedback } from '../api/nlp';
import { createUserTicket, resolveUserTicket } from '../api/user';

export default function UserDashboard({ tickets, setTickets, onLogout, token, onRefresh, loading, error }) {
  const [currentView, setCurrentView] = useState('new-ticket');
  const [formData, setFormData] = useState({ issue: '', category: 'Software', priority: 'med', description: '' });
  const [nlpSuggestions, setNlpSuggestions] = useState([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [ticketSubmitted, setTicketSubmitted] = useState(false);

  const myTickets = tickets.filter((t) => t.author === 'me');

  useEffect(() => {
    if (formData.description.length <= 10) {
      setNlpSuggestions([]);
      setIsAnalyzing(false);
      return undefined;
    }

    setIsAnalyzing(true);
    const timer = setTimeout(async () => {
      try {
        const data = await fetchNlpSuggestions(`${formData.issue} ${formData.description}`, 3, 0.1);
        const mapped = (data.suggestions || []).map((s, i) => ({
          id: s.resolution_id,
          title: s.title,
          steps: [s.resolution_text],
          matchScore: Math.round((s.score || 0) * 100),
          ai_suggestion: s.resolution_text,
          rank: i + 1,
        }));
        setNlpSuggestions(mapped);
      } catch {
        setNlpSuggestions([]);
      } finally {
        setIsAnalyzing(false);
      }
    }, 700);

    return () => clearTimeout(timer);
  }, [formData.issue, formData.description]);

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!formData.issue || !formData.description) return;
    await createUserTicket(token, {
      issue: formData.issue,
      category: formData.category,
      description: formData.description,
      priority: formData.priority,
    });
    await onRefresh();
    setTicketSubmitted(true);
  };

  const handleUseSuggestion = async (suggestion) => {
    try {
      await sendNlpFeedback(suggestion.id, true);
    } catch {
      // ignore feedback errors in UI flow
    }
    const created = await createUserTicket(token, {
      issue: formData.issue,
      category: formData.category,
      description: formData.description,
      priority: formData.priority,
    });
    await resolveUserTicket(token, created.ticket_id, `Self-resolved via NLP: ${suggestion.ai_suggestion}`);
    await onRefresh();
    setTicketSubmitted(true);
  };

  return (
    <div className="flex h-screen w-full bg-[#0B0B0F] text-zinc-100 font-sans">
      <div className="w-64 bg-[#0B0B0F] border-r border-zinc-800/60 text-zinc-300 flex flex-col h-full shrink-0">
        <div className="p-6 border-b border-zinc-800/60 flex items-center gap-3">
          <div className="w-8 h-8 bg-zinc-800 rounded-md flex items-center justify-center border border-zinc-700"><Terminal size={18} className="text-zinc-300" /></div>
          <div><h2 className="text-sm font-bold text-white tracking-tight">SupportEngine</h2><p className="font-mono text-[10px] text-zinc-500 uppercase tracking-widest mt-0.5">User Portal</p></div>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          <button onClick={() => setCurrentView('new-ticket')} className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md transition-all text-sm font-medium ${currentView === 'new-ticket' ? 'bg-zinc-800/50 text-white' : 'text-zinc-400 hover:bg-zinc-800/30'}`}><PlusCircle size={18} /><span>Submit Issue</span></button>
          <button onClick={() => setCurrentView('my-tickets')} className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md transition-all text-sm font-medium ${currentView === 'my-tickets' ? 'bg-zinc-800/50 text-white' : 'text-zinc-400 hover:bg-zinc-800/30'}`}><TicketIcon size={18} /><span>My Tickets</span></button>
        </nav>
        <div className="p-4 border-t border-zinc-800/60">
          <button onClick={onLogout} className="flex items-center gap-3 w-full px-3 py-2 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/30 rounded-md transition-colors text-xs font-medium"><LogOut size={14} /><span>Sign Out</span></button>
        </div>
      </div>

      <main className="flex-1 h-full overflow-y-auto">
        {currentView === 'new-ticket' ? (
          ticketSubmitted ? (
            <div className="h-full flex items-center justify-center p-8 animate-in fade-in duration-500">
              <div className="max-w-md w-full bg-[#111115] p-8 rounded-lg border border-zinc-800/60 text-center">
                <div className="w-16 h-16 bg-emerald-500/10 text-emerald-400 rounded-full flex items-center justify-center mx-auto mb-4"><CheckCircle2 size={32} /></div>
                <h2 className="text-xl font-bold text-white mb-2">Ticket Processed</h2>
                <button onClick={() => { setTicketSubmitted(false); setFormData({ issue: '', category: 'Software', priority: 'med', description: '' }); }} className="px-6 py-2 mt-4 bg-white text-black font-semibold rounded-md hover:bg-zinc-200 text-sm">Submit Another</button>
              </div>
            </div>
          ) : (
            <div className="p-8 h-full flex flex-col animate-in fade-in duration-500">
              <h1 className="text-2xl font-bold text-white mb-6">Need IT Help?</h1>
              <div className="flex gap-8 flex-1 overflow-hidden">
                <form className="flex-1 bg-[#111115] p-6 rounded-lg border border-zinc-800 flex flex-col space-y-5" onSubmit={(e) => handleSubmit(e)}>
                  <div><label className="text-xs text-zinc-400 mb-2 block">Brief Title</label><input type="text" value={formData.issue} onChange={(e) => setFormData({ ...formData, issue: e.target.value })} required className="w-full px-4 py-2 bg-[#0B0B0F] border border-zinc-800 rounded-md text-sm text-white focus:border-indigo-500/50" /></div>
                  <div><label className="text-xs text-zinc-400 mb-2 block">Category</label><select value={formData.category} onChange={(e) => setFormData({ ...formData, category: e.target.value })} className="w-full px-4 py-2 bg-[#0B0B0F] border border-zinc-800 rounded-md text-sm text-white"><option>Software</option><option>Hardware</option><option>Network</option><option>Access</option></select></div>
                  <div><label className="text-xs text-zinc-400 mb-2 block">Priority</label><select value={formData.priority} onChange={(e) => setFormData({ ...formData, priority: e.target.value })} className="w-full px-4 py-2 bg-[#0B0B0F] border border-zinc-800 rounded-md text-sm text-white"><option value="low">Low</option><option value="med">Medium</option><option value="high">High</option></select></div>
                  <div className="flex-1 flex flex-col"><label className="text-xs text-zinc-400 mb-2 flex justify-between">Description {isAnalyzing && <span className="text-indigo-400 animate-pulse">Analyzing...</span>}</label><textarea value={formData.description} onChange={(e) => setFormData({ ...formData, description: e.target.value })} required className="w-full flex-1 p-4 bg-[#0B0B0F] border border-zinc-800 rounded-md text-xs font-mono text-white resize-none" /></div>
                  <div className="pt-4 flex justify-end"><button type="submit" className="px-6 py-2 bg-white text-black font-semibold rounded-md hover:bg-zinc-200 text-sm flex items-center gap-2">Submit to IT <ArrowRight size={16} /></button></div>
                </form>
                <div className="w-[400px] bg-[#111115] p-5 rounded-lg border border-indigo-500/30 flex flex-col">
                  <h3 className="text-sm font-bold text-white flex items-center gap-2 mb-4"><Sparkles size={16} className="text-indigo-400" /> NLP Recommendations</h3>
                  {nlpSuggestions.length > 0 ? (
                    <div className="space-y-4 overflow-auto">
                      {nlpSuggestions.map((sugg) => (
                        <div key={sugg.id} className="bg-[#0B0B0F] border border-zinc-800 rounded-md p-4">
                          <div className="flex justify-between mb-2"><h4 className="text-sm font-bold text-indigo-300">#{sugg.rank} {sugg.title}</h4><span className="text-[10px] text-indigo-400 bg-indigo-500/10 px-2 rounded">{sugg.matchScore}%</span></div>
                          <ul className="text-xs text-zinc-400 mb-4">{sugg.steps.map((s, i) => <li key={i}>{i + 1}. {s}</li>)}</ul>
                          <button onClick={(e) => { e.preventDefault(); handleUseSuggestion(sugg); }} className="w-full py-2 bg-indigo-500/10 text-indigo-300 rounded text-xs hover:bg-indigo-500/20 transition-colors">This Fixed My Issue</button>
                        </div>
                      ))}
                    </div>
                  ) : <p className="text-sm text-zinc-500 text-center mt-10">Start typing for instant AI resolutions.</p>}
                </div>
              </div>
            </div>
          )
        ) : (
          <div className="p-8 h-full flex flex-col animate-in fade-in duration-500">
            <div className="flex items-center justify-between mb-6">
              <h1 className="text-2xl font-bold text-white">My Tickets</h1>
              <button onClick={onRefresh} className="px-3 py-2 text-xs rounded-md border border-zinc-700 hover:bg-zinc-800 flex items-center gap-2"><RefreshCw size={14} /> Refresh</button>
            </div>
            {loading ? <p className="text-sm text-zinc-400 mb-3">Loading your tickets...</p> : null}
            {error ? <p className="text-sm text-red-400 mb-3">{error}</p> : null}
            <div className="bg-[#111115] rounded-lg border border-zinc-800 flex-1 overflow-auto">
              <table className="w-full text-left border-collapse">
                <thead className="bg-[#0B0B0F]"><tr><th className="p-4 text-xs text-zinc-500">ID</th><th className="p-4 text-xs text-zinc-500">Issue</th><th className="p-4 text-xs text-zinc-500">Status</th><th className="p-4 text-xs text-zinc-500">Resolution</th></tr></thead>
                <tbody className="divide-y divide-zinc-800">
                  {myTickets.map((t) => (
                    <tr key={t.id} className="hover:bg-zinc-800/30">
                      <td className="p-4 font-mono text-xs text-zinc-400">{t.id}</td><td className="p-4 text-sm text-zinc-200">{t.issue}</td>
                      <td className="p-4"><span className="px-2 py-1 text-xs border border-zinc-700 bg-zinc-800 rounded">{t.status}</span></td><td className="p-4 text-xs text-zinc-300">{t.resolution || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
