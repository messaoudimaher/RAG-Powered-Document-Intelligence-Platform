'use client';

import React, { useState } from 'react';
import { 
  Sparkles, 
  Terminal, 
  Cpu, 
  Layers, 
  ShieldAlert,
  Heart
} from 'lucide-react';
import Diagnostics from '../components/Diagnostics';
import Sidebar from '../components/Sidebar';
import IngestPanel from '../components/IngestPanel';
import QueryWorkspace from '../components/QueryWorkspace';

export default function Home() {
  const [activeCollection, setActiveCollection] = useState<'public' | 'papers'>('public');
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const triggerRefresh = () => {
    setRefreshTrigger(prev => prev + 1);
  };

  return (
    <div className="min-h-screen bg-[#08090d] text-zinc-100 flex flex-col font-sans selection:bg-indigo-500 selection:text-white">
      {/* Premium Top Navigation Bar */}
      <header className="border-b border-zinc-900 bg-zinc-950/40 backdrop-blur-md sticky top-0 z-40 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3.5">
          <div className="relative">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-cyan-500 flex items-center justify-center shadow-[0_0_15px_rgba(99,102,241,0.3)]">
              <Cpu className="w-5 h-5 text-white animate-pulse" />
            </div>
            <Sparkles className="w-3.5 h-3.5 text-indigo-300 absolute -top-1 -right-1 animate-pulse" />
          </div>
          <div>
            <h1 className="text-base font-extrabold tracking-tight text-white flex items-center gap-1.5">
              CogniFlow
              <span className="text-xs font-semibold text-zinc-500 font-mono select-none">//</span>
              <span className="text-xs font-bold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">RAG Engine</span>
            </h1>
            <p className="text-[10px] text-zinc-500 font-medium tracking-wide uppercase mt-0.5">Local-First Document Intelligence</p>
          </div>
        </div>

        {/* Global indicator chips */}
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-2 text-zinc-400 bg-zinc-900/40 border border-zinc-800/80 px-3 py-1.5 rounded-full">
            <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-ping" />
            <span className="font-medium text-[11px] text-zinc-300">Cluster Status: Online</span>
          </div>
        </div>
      </header>

      {/* Main Operations Grid Layout */}
      <main className="flex-1 w-full max-w-7xl mx-auto p-4 md:p-6 grid grid-cols-1 lg:grid-cols-12 gap-5 md:gap-6">
        
        {/* Left Hand: Ingestion & File Library Sidebar (40% width / 5 Cols) */}
        <section className="lg:col-span-5 flex flex-col gap-5 md:gap-6 h-[calc(100vh-140px)] min-h-[500px] lg:sticky lg:top-24">
          <div className="flex-1">
            <Sidebar
              activeCollection={activeCollection}
              onCollectionChange={setActiveCollection}
              onRefreshTrigger={refreshTrigger}
              onDocumentDeleted={triggerRefresh}
            />
          </div>
          <div className="h-fit">
            <IngestPanel
              activeCollection={activeCollection}
              onIngestionSuccess={triggerRefresh}
            />
          </div>
        </section>

        {/* Right Hand: Server Health & Query Workspaces (60% width / 7 Cols) */}
        <section className="lg:col-span-7 flex flex-col gap-5 md:gap-6 h-[calc(100vh-140px)] min-h-[500px]">
          {/* Health Diagnostics Panel */}
          <div className="h-fit">
            <Diagnostics
              onRefreshTrigger={refreshTrigger}
              onConfigChange={triggerRefresh}
            />
          </div>
          
          {/* Main RAG Query workspace */}
          <div className="flex-1 min-h-[300px]">
            <QueryWorkspace
              activeCollection={activeCollection}
            />
          </div>
        </section>
      </main>

      {/* Footer Status Bar */}
      <footer className="border-t border-zinc-900 bg-zinc-950/20 py-3.5 px-6 flex items-center justify-between text-[11px] text-zinc-500 font-medium">
        <span>© 2026 CogniFlow Intelligent Systems. Offline Ollama Localhost.</span>
        <span className="flex items-center gap-1 text-[10px]">
          Built with <Heart className="w-3 h-3 text-red-500 fill-red-500" /> & Antigravity
        </span>
      </footer>
    </div>
  );
}
