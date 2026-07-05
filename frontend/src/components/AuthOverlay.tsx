import React, { useState } from 'react';
import { Cpu, Sparkles, Loader2, KeyRound, User, UserPlus } from 'lucide-react';
import { api, setToken, setUsername } from '../utils/api';

interface AuthOverlayProps {
  onAuthSuccess: () => void;
}

export default function AuthOverlay({ onAuthSuccess }: AuthOverlayProps) {
  const [isRegister, setIsRegister] = useState(false);
  const [usernameInput, setUsernameInput] = useState('');
  const [passwordInput, setPasswordInput] = useState('');
  
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const u = usernameInput.trim();
    const p = passwordInput.trim();
    
    if (!u || !p) return;
    
    setLoading(true);
    setErrorMsg('');
    setSuccessMsg('');

    try {
      if (isRegister) {
        await api.register(u, p);
        setSuccessMsg('Account registered successfully! You can now log in.');
        setIsRegister(false);
        setPasswordInput('');
      } else {
        const resp = await api.login(u, p);
        setToken(resp.access_token);
        setUsername(resp.username);
        onAuthSuccess();
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Authentication request failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-[#06070a] z-50 flex items-center justify-center p-4">
      {/* Background glowing circles */}
      <div className="absolute top-1/4 left-1/4 w-[400px] h-[400px] bg-indigo-600/10 rounded-full blur-[120px] pointer-events-none animate-pulse-glow" />
      <div className="absolute bottom-1/4 right-1/4 w-[350px] h-[350px] bg-cyan-500/10 rounded-full blur-[100px] pointer-events-none animate-pulse-glow" />

      {/* Main glass card */}
      <div className="glass-panel w-full max-w-[420px] rounded-3xl border border-zinc-800 bg-zinc-950/60 backdrop-blur-xl p-8 flex flex-col items-center shadow-2xl relative overflow-hidden">
        {/* Top Logo */}
        <div className="flex flex-col items-center gap-3.5 mb-8">
          <div className="relative">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-600 to-cyan-500 flex items-center justify-center shadow-[0_0_25px_rgba(99,102,241,0.4)]">
              <Cpu className="w-6 h-6 text-white" />
            </div>
            <Sparkles className="w-4 h-4 text-indigo-300 absolute -top-1 -right-1 animate-pulse" />
          </div>
          <div className="text-center">
            <h1 className="text-xl font-black text-white tracking-tight">CogniFlow</h1>
            <p className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider mt-0.5">
              Secure Document Intelligence
            </p>
          </div>
        </div>

        {/* Form Title */}
        <h2 className="text-base font-extrabold text-zinc-200 mb-6 flex items-center gap-2">
          {isRegister ? (
            <>
              <UserPlus className="w-4.5 h-4.5 text-indigo-400" />
              Create your account
            </>
          ) : (
            <>
              <KeyRound className="w-4.5 h-4.5 text-indigo-400" />
              Sign in to platform
            </>
          )}
        </h2>

        {/* Messages */}
        {errorMsg && (
          <div className="w-full p-3 mb-5 text-xs text-red-400 border border-red-500/20 bg-red-500/5 rounded-xl font-medium leading-normal animate-fade-in">
            {errorMsg}
          </div>
        )}
        {successMsg && (
          <div className="w-full p-3 mb-5 text-xs text-emerald-400 border border-emerald-500/20 bg-emerald-500/5 rounded-xl font-medium leading-normal animate-fade-in">
            {successMsg}
          </div>
        )}

        {/* Input Form */}
        <form onSubmit={handleSubmit} className="w-full flex flex-col gap-4">
          {/* Username */}
          <div className="relative">
            <User className="absolute left-3.5 top-3.5 w-4 h-4 text-zinc-500" />
            <input
              type="text"
              placeholder="Username"
              value={usernameInput}
              onChange={(e) => setUsernameInput(e.target.value)}
              required
              minLength={3}
              disabled={loading}
              className="w-full bg-zinc-900/60 border border-zinc-800 focus:border-indigo-500/70 text-zinc-200 text-xs pl-10 pr-4 py-3.5 rounded-xl focus:outline-none placeholder-zinc-600 transition-colors"
            />
          </div>

          {/* Password */}
          <div className="relative">
            <KeyRound className="absolute left-3.5 top-3.5 w-4 h-4 text-zinc-500" />
            <input
              type="password"
              placeholder="Password"
              value={passwordInput}
              onChange={(e) => setPasswordInput(e.target.value)}
              required
              minLength={4}
              disabled={loading}
              className="w-full bg-zinc-900/60 border border-zinc-800 focus:border-indigo-500/70 text-zinc-200 text-xs pl-10 pr-4 py-3.5 rounded-xl focus:outline-none placeholder-zinc-600 transition-colors"
            />
          </div>

          {/* Submit button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs py-3 rounded-xl transition-all cursor-pointer flex items-center justify-center gap-2 shadow-lg hover:shadow-indigo-500/20 mt-2"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : isRegister ? (
              'Create Account'
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        {/* Form switcher link */}
        <div className="mt-6 text-xs text-zinc-500">
          {isRegister ? (
            <span>
              Already have an account?{' '}
              <button
                onClick={() => {
                  setIsRegister(false);
                  setErrorMsg('');
                  setSuccessMsg('');
                }}
                className="text-indigo-400 hover:underline cursor-pointer font-semibold"
              >
                Sign In
              </button>
            </span>
          ) : (
            <span>
              New to CogniFlow?{' '}
              <button
                onClick={() => {
                  setIsRegister(true);
                  setErrorMsg('');
                  setSuccessMsg('');
                }}
                className="text-indigo-400 hover:underline cursor-pointer font-semibold"
              >
                Create Account
              </button>
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
