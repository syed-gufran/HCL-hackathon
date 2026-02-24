import React, { useState, useEffect } from 'react';
import { Terminal, Sparkles, ShieldCheck, Zap, ArrowRight, Mail, Lock, User, Shield } from 'lucide-react';
import { loginRequest } from '../api/auth';

export default function Login({ onLoginSuccess }) {
  const [role, setRole] = useState('user');
  const [isLoading, setIsLoading] = useState(false);
  const [loginSuccess, setLoginSuccess] = useState(false);
  const [error, setError] = useState('');
  const [email, setEmail] = useState('admin@company.com');
  const [password, setPassword] = useState('admin123');
  const [session, setSession] = useState(null);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    try {
      const data = await loginRequest(email, password);
      setSession(data);
      setRole(data.user.role);
      setLoginSuccess(true);
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (loginSuccess) {
      const timer = setTimeout(() => {
        onLoginSuccess(session);
      }, 2500);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [loginSuccess, onLoginSuccess, role, session]);

  if (loginSuccess) {
    return (
      <div className="flex h-screen w-full bg-[#0B0B0F] text-zinc-100 items-center justify-center font-sans relative overflow-hidden">
        <div className="text-center animate-in fade-in zoom-in duration-500 z-10 relative bg-[#0B0B0F]/50 p-12 rounded-2xl backdrop-blur-sm border border-white/5 shadow-2xl">
          <div className="w-16 h-16 bg-indigo-500/20 text-indigo-400 rounded-xl flex items-center justify-center mx-auto mb-6 border border-indigo-500/30 shadow-[0_0_30px_rgba(99,102,241,0.3)]">
            <Sparkles size={32} />
          </div>
          <h2 className="text-2xl font-bold text-white mb-2 tracking-tight">Authentication Successful</h2>
          <p className="text-zinc-300 text-sm mb-6 font-mono">Redirecting to {role === 'admin' ? 'Admin Dashboard' : 'User Portal'}...</p>
          <div className="w-48 h-1 bg-zinc-800 rounded-full mx-auto overflow-hidden">
            <div className="h-full bg-indigo-500 animate-[pulse_1s_ease-in-out_infinite] w-1/2 rounded-full shadow-[0_0_10px_rgba(99,102,241,0.8)]" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-full bg-[#0B0B0F] text-zinc-100 overflow-hidden font-sans selection:bg-indigo-500/30">
      <div className="hidden lg:flex flex-col justify-between w-[50%] bg-[#0B0B0F] border-r border-zinc-800/60 p-12 relative overflow-hidden">
        <div className="relative z-10 bg-gradient-to-r from-[#0B0B0F] via-[#0B0B0F]/80 to-transparent p-4 -m-4 rounded-xl">
          <div className="flex items-center gap-3 mb-16">
            <div className="w-10 h-10 bg-white rounded-lg flex items-center justify-center shadow-[0_0_15px_rgba(255,255,255,0.2)]">
              <Terminal size={22} className="text-black" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white tracking-tight leading-none drop-shadow-md">SupportEngine</h2>
              <p className="font-mono text-[10px] text-indigo-300 uppercase tracking-widest mt-1 font-bold">v2.0 Beta</p>
            </div>
          </div>

          <h1 className="text-5xl font-bold text-white tracking-tight leading-tight mb-6 drop-shadow-xl">
            Next-generation IT <br />
            <span className="text-indigo-400 drop-shadow-[0_0_20px_rgba(99,102,241,0.4)]">resolution engine.</span>
          </h1>

          <p className="text-zinc-300 text-sm leading-relaxed mb-12 max-w-md font-medium">
            Our NLP-powered platform dramatically reduces IT support workload by analyzing historical data to instantly recommend solutions for common user issues.
          </p>

          <div className="space-y-6">
            <div className="flex gap-4 items-start bg-[#0B0B0F]/40 p-3 rounded-lg backdrop-blur-sm border border-white/5 w-fit">
              <div className="mt-1 p-2 bg-indigo-500/20 border border-indigo-500/30 rounded-md text-indigo-400 shadow-[0_0_10px_rgba(99,102,241,0.2)]"><Zap size={18} /></div>
              <div>
                <h3 className="text-sm font-bold text-white mb-1">Instant NLP Resolutions</h3>
                <p className="text-xs text-zinc-400 leading-relaxed max-w-sm">TF-IDF engine matches new tickets with historical fixes.</p>
              </div>
            </div>

            <div className="flex gap-4 items-start bg-[#0B0B0F]/40 p-3 rounded-lg backdrop-blur-sm border border-white/5 w-fit">
              <div className="mt-1 p-2 bg-emerald-500/20 border border-emerald-500/30 rounded-md text-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.2)]"><ShieldCheck size={18} /></div>
              <div>
                <h3 className="text-sm font-bold text-white mb-1">Reduced IT Workload</h3>
                <p className="text-xs text-zinc-400 leading-relaxed max-w-sm">Empowers users to self-resolve tier-1 issues instantly.</p>
              </div>
            </div>
          </div>
        </div>

        <div className="relative z-10 text-xs font-mono text-zinc-500 bg-[#0B0B0F]/50 w-fit p-2 rounded backdrop-blur-sm">
          <p>© 2026 SupportEngine Platform. Demo Environment.</p>
        </div>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center p-8 relative bg-[#0B0B0F]">
        <div className="w-full max-w-sm animate-in fade-in slide-in-from-bottom-4 duration-700 relative z-10">
          <div className="mb-8 text-center">
            <h2 className="text-3xl font-bold text-white tracking-tight mb-2">Welcome back</h2>
            <p className="text-sm text-zinc-400">Enter your credentials to access the portal.</p>
          </div>

          <div className="flex p-1 bg-[#111115] border border-zinc-800/80 rounded-lg mb-8 shadow-inner">
            <button onClick={() => setRole('user')} className={`flex-1 flex items-center justify-center gap-2 py-2.5 text-xs font-semibold rounded-md transition-all ${role === 'user' ? 'bg-zinc-800 text-white shadow-md' : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50'}`}><User size={14} />Employee</button>
            <button onClick={() => setRole('admin')} className={`flex-1 flex items-center justify-center gap-2 py-2.5 text-xs font-semibold rounded-md transition-all ${role === 'admin' ? 'bg-zinc-800 text-white shadow-md' : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50'}`}><Shield size={14} />IT Admin</button>
          </div>

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label className="text-xs font-semibold text-zinc-400 mb-2 block uppercase tracking-wider">Corporate Email</label>
              <div className="relative group">
                <Mail className="absolute left-3 top-2.5 text-zinc-500 group-focus-within:text-indigo-400 transition-colors" size={16} />
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className="w-full pl-10 pr-4 py-2.5 bg-[#111115] border border-zinc-800/80 rounded-md text-sm text-white focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 transition-all shadow-inner" />
              </div>
            </div>
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Password</label>
                <a href="#" className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">Forgot?</a>
              </div>
              <div className="relative group">
                <Lock className="absolute left-3 top-2.5 text-zinc-500 group-focus-within:text-indigo-400 transition-colors" size={16} />
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required className="w-full pl-10 pr-4 py-2.5 bg-[#111115] border border-zinc-800/80 rounded-md text-sm text-white focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 transition-all shadow-inner" />
              </div>
            </div>
            {error ? <p className="text-xs text-red-400">{error}</p> : null}
            <button type="submit" disabled={isLoading} className="w-full py-3 mt-4 bg-white text-black font-bold rounded-md hover:bg-zinc-200 transition-all text-sm flex items-center justify-center gap-2 disabled:opacity-70 group shadow-[0_0_15px_rgba(255,255,255,0.1)] hover:shadow-[0_0_20px_rgba(255,255,255,0.3)]">
              {isLoading ? <div className="w-5 h-5 border-2 border-black border-t-transparent rounded-full animate-spin" /> : <>Sign In to {role === 'admin' ? 'Admin Portal' : 'User Portal'} <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" /></>}
            </button>
          </form>

          <div className="mt-8 p-4 bg-indigo-500/5 border border-indigo-500/10 rounded-md text-center backdrop-blur-sm">
            <p className="text-xs font-mono text-indigo-400/80">
              {role === 'admin' ? 'Admin: Access analytics & NLP knowledge base.' : 'User: Raise tickets & get instant NLP resolutions.'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
