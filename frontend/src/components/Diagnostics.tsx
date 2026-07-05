'use client';

import React, { useState, useEffect } from 'react';
import { 
  CheckCircle, 
  AlertCircle, 
  Activity, 
  Database, 
  Cpu, 
  Clock, 
  Settings,
  Shield,
  RefreshCw
} from 'lucide-react';
import { api, getApiBaseUrl, setApiBaseUrl, getApiKey, setApiKey } from '../utils/api';
import { DiagnosticsResponse } from '../types';

interface DiagnosticsProps {
  onRefreshTrigger?: number;
  onConfigChange?: () => void;
}

export default function Diagnostics({ onRefreshTrigger = 0, onConfigChange }: DiagnosticsProps) {
  const [data, setData] = useState<DiagnosticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isEditingSettings, setIsEditingSettings] = useState(false);
  
  // Settings inputs
  const [apiUrl, setApiUrl] = useState('');
  const [apiKey, setApiKeyInput] = useState('');

  const fetchDiagnostics = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getDiagnostics();
      setData(res);
    } catch (err: any) {
      setError(err.message || 'Server connection failed');
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Sync settings inputs with localStorage
    setApiUrl(getApiBaseUrl());
    setApiKeyInput(getApiKey());
    fetchDiagnostics();
  }, [onRefreshTrigger]);

  const handleSaveSettings = (e: React.FormEvent) => {
    e.preventDefault();
    setApiBaseUrl(apiUrl);
    setApiKey(apiKey);
    setIsEditingSettings(false);
    fetchDiagnostics();
    if (onConfigChange) onConfigChange();
  };

  const formatUptime = (seconds: number) => {
    const d = Math.floor(seconds / (3600 * 24));
    const h = Math.floor((seconds % (3600 * 24)) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);

    const parts = [];
    if (d > 0) parts.push(`${d}d`);
    if (h > 0) parts.push(`${h}h`);
    if (m > 0) parts.push(`${m}m`);
    parts.push(`${s}s`);
    return parts.join(' ');
  };

  return (
    <div className="w-full">
      {/* Settings Panel Toggle */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold tracking-wide text-zinc-100 flex items-center gap-2">
          <Activity className="w-5 h-5 text-indigo-400" />
          Diagnostics & Engine Health
        </h2>
        <button
          onClick={() => setIsEditingSettings(!isEditingSettings)}
          className="text-xs text-zinc-400 hover:text-indigo-400 flex items-center gap-1 transition-colors px-2 py-1 rounded bg-zinc-800/50 hover:bg-zinc-800"
        >
          <Settings className="w-3.5 h-3.5" />
          {isEditingSettings ? 'Close Config' : 'Configure Server'}
        </button>
      </div>

      {isEditingSettings && (
        <form onSubmit={handleSaveSettings} className="glass-panel p-4 rounded-xl mb-4 border border-indigo-500/25 animate-slide-up">
          <h3 className="text-sm font-medium text-zinc-200 mb-3 flex items-center gap-1.5">
            <Shield className="w-4 h-4 text-indigo-400" /> API Configuration
          </h3>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-semibold text-zinc-400 mb-1">Backend Server URL</label>
              <input
                type="text"
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                placeholder="e.g. http://localhost:8000"
                className="w-full bg-zinc-900/60 border border-zinc-700/60 text-zinc-100 text-sm px-3 py-1.5 rounded-lg focus:outline-none focus:border-indigo-500"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-zinc-400 mb-1">X-API-Key Header (Optional)</label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKeyInput(e.target.value)}
                placeholder="Enter API Key if backend has AUTH enabled"
                className="w-full bg-zinc-900/60 border border-zinc-700/60 text-zinc-100 text-sm px-3 py-1.5 rounded-lg focus:outline-none focus:border-indigo-500"
              />
            </div>
            <button
              type="submit"
              className="w-full text-xs font-semibold text-slate-100 bg-indigo-600 hover:bg-indigo-500 cursor-pointer text-center py-2 rounded-lg transition-colors"
            >
              Save & Test Connection
            </button>
          </div>
        </form>
      )}

      {/* Main Status Indicators */}
      {loading && !data ? (
        <div className="glass-panel p-6 rounded-2xl flex flex-col items-center justify-center border border-zinc-800 text-zinc-400 gap-3">
          <RefreshCw className="w-6 h-6 animate-spin text-indigo-400" />
          <span className="text-xs">Querying RAG cluster...</span>
        </div>
      ) : error ? (
        <div className="glass-panel p-4 rounded-xl border border-red-500/20 text-red-400 flex flex-col gap-2">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <AlertCircle className="w-4 h-4" />
            CogniFlow Offline
          </div>
          <p className="text-xs text-zinc-400">
            Cannot reach FastAPI backend server. {error}. Ensure your backend server is active at {getApiBaseUrl()}.
          </p>
          <button
            onClick={fetchDiagnostics}
            className="text-xs text-zinc-300 hover:text-white bg-zinc-800/80 hover:bg-zinc-800 px-3 py-1 rounded-md self-start transition-colors mt-2"
          >
            Retry Connection
          </button>
        </div>
      ) : data ? (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Card 1: System Status */}
          <div className="glass-panel-interactive p-4 rounded-xl flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">System State</span>
              {data.status === 'healthy' ? (
                <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                  <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-ping" />
                  HEALTHY
                </span>
              ) : (
                <span className="flex items-center gap-1 text-[10px] font-bold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20">
                  DEGRADED
                </span>
              )}
            </div>
            <div className="mt-3">
              <div className="text-xl font-bold tracking-tight text-zinc-100 flex items-center gap-2">
                Active
              </div>
              <span className="text-[11px] text-zinc-500 font-mono">Build v{data.version} ({data.git_sha})</span>
            </div>
          </div>

          {/* Card 2: Database Indexes */}
          <div className="glass-panel-interactive p-4 rounded-xl flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Indexed Chunks</span>
              <Database className="w-4 h-4 text-cyan-400" />
            </div>
            <div className="mt-3">
              <div className="text-2xl font-bold tracking-tight text-zinc-100 font-mono">
                {data.public_count + data.papers_count}
              </div>
              <div className="flex gap-3 text-[10px] text-zinc-400 font-mono">
                <span>Public: {data.public_count}</span>
                <span>Papers: {data.papers_count}</span>
              </div>
            </div>
          </div>

          {/* Card 3: Ollama / LLM Link */}
          <div className="glass-panel-interactive p-4 rounded-xl flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Model Cluster</span>
              <Cpu className="w-4 h-4 text-indigo-400" />
            </div>
            <div className="mt-3">
              <div className="flex flex-col gap-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400">Ollama API</span>
                  <span className={`font-bold ${data.ollama_connected ? 'text-emerald-400' : 'text-amber-400'}`}>
                    {data.ollama_connected ? 'Connected' : 'Offline'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400">Relevance Cutoff</span>
                  <span className="font-bold font-mono text-zinc-300">{(data.threshold * 100).toFixed(0)}%</span>
                </div>
              </div>
            </div>
          </div>

          {/* Card 4: Uptime Tracker */}
          <div className="glass-panel-interactive p-4 rounded-xl flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Engine Uptime</span>
              <Clock className="w-4 h-4 text-indigo-300" />
            </div>
            <div className="mt-3">
              <div className="text-lg font-bold tracking-tight text-zinc-100 font-mono truncate">
                {formatUptime(data.uptime_seconds)}
              </div>
              <span className="text-[10px] text-zinc-500 font-mono">Running locally on port 8000</span>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
