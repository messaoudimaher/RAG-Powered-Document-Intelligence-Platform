'use client';

import React, { useState } from 'react';
import { 
  Send, 
  Sparkles, 
  Layers, 
  ChevronRight, 
  Award, 
  BookOpen, 
  ExternalLink,
  Loader2,
  Info,
  Maximize2
} from 'lucide-react';
import { api } from '../utils/api';
import { SourceCitation } from '../types';

interface QueryWorkspaceProps {
  activeCollection: 'public' | 'papers';
}

export default function QueryWorkspace({ activeCollection }: QueryWorkspaceProps) {
  const [query, setQuery] = useState('');
  const [strategy, setStrategy] = useState<'baseline' | 'hyde' | 'multi_query' | 'flare'>('baseline');
  const [limit, setLimit] = useState(5);
  
  // Results states
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState<string>('');
  const [citations, setCitations] = useState<SourceCitation[]>([]);
  const [confidence, setConfidence] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  // Selected citation detail modal
  const [selectedCitation, setSelectedCitation] = useState<SourceCitation | null>(null);

  const handleQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanQuery = query.trim();
    if (!cleanQuery) return;

    setLoading(true);
    setError(null);
    setAnswer('');
    setCitations([]);
    setConfidence('');

    try {
      const res = await api.queryRag({
        collection_type: activeCollection,
        query: cleanQuery,
        strategy: strategy,
        limit: limit
      });

      setAnswer(res.answer);
      setCitations(res.citations);
      setConfidence(res.overall_confidence);
    } catch (err: any) {
      setError(err.message || 'Failed to synthesize response');
    } finally {
      setLoading(false);
    }
  };

  // Simple, ultra-fast Markdown-to-HTML parser function to style RAG output
  const renderFormattedAnswer = (text: string) => {
    if (!text) return null;
    
    // Split text into paragraphs/blocks
    const lines = text.split('\n');
    let formattedElements: React.ReactNode[] = [];
    let insideList = false;
    let listItems: string[] = [];

    const parseInline = (chunk: string, keyPrefix: string) => {
      // Bold formatter (**text**)
      const boldRegex = /\*\*(.*?)\*\*/g;
      const parts = [];
      let lastIndex = 0;
      let match;

      while ((match = boldRegex.exec(chunk)) !== null) {
        if (match.index > lastIndex) {
          parts.push(chunk.substring(lastIndex, match.index));
        }
        parts.push(<strong key={`${keyPrefix}-bold-${match.index}`} className="font-bold text-white text-glow-primary">{match[1]}</strong>);
        lastIndex = boldRegex.lastIndex;
      }
      if (lastIndex < chunk.length) {
        parts.push(chunk.substring(lastIndex));
      }

      // Inline code formatter (`code`)
      // Convert standard inline code blocks
      return parts.map((part, index) => {
        if (typeof part === 'string') {
          const codeRegex = /`(.*?)`/g;
          const codeParts = [];
          let codeLastIndex = 0;
          let codeMatch;

          while ((codeMatch = codeRegex.exec(part)) !== null) {
            if (codeMatch.index > codeLastIndex) {
              codeParts.push(part.substring(codeLastIndex, codeMatch.index));
            }
            codeParts.push(
              <code key={`${keyPrefix}-code-${index}-${codeMatch.index}`} className="prose-code">
                {codeMatch[1]}
              </code>
            );
            codeLastIndex = codeRegex.lastIndex;
          }
          if (codeLastIndex < part.length) {
            codeParts.push(part.substring(codeLastIndex));
          }
          return codeParts.length > 0 ? codeParts : part;
        }
        return part;
      });
    };

    lines.forEach((line, index) => {
      const trimmed = line.trim();
      
      // Handle code block block boundaries (```code```)
      // For simplicity, we filter out line tags or render them as monospace
      if (trimmed.startsWith('```')) {
        return; // skip delimiters
      }

      // Headers (e.g. ### Header)
      if (trimmed.startsWith('###')) {
        if (insideList) {
          formattedElements.push(
            <ul key={`list-${index}`} className="list-disc pl-5 mb-4 text-zinc-300 space-y-1">
              {listItems.map((item, idx) => <li key={`li-${idx}`}>{parseInline(item, `li-${idx}`)}</li>)}
            </ul>
          );
          insideList = false;
          listItems = [];
        }
        formattedElements.push(<h4 key={`h4-${index}`} className="text-sm font-bold text-zinc-100 mt-4 mb-2 tracking-wide uppercase">{parseInline(trimmed.replace('###', '').trim(), `h4-${index}`)}</h4>);
        return;
      }
      if (trimmed.startsWith('##')) {
        if (insideList) {
          formattedElements.push(
            <ul key={`list-${index}`} className="list-disc pl-5 mb-4 text-zinc-300 space-y-1">
              {listItems.map((item, idx) => <li key={`li-${idx}`}>{parseInline(item, `li-${idx}`)}</li>)}
            </ul>
          );
          insideList = false;
          listItems = [];
        }
        formattedElements.push(<h3 key={`h3-${index}`} className="text-base font-extrabold text-indigo-300 mt-5 mb-3 tracking-wide">{parseInline(trimmed.replace('##', '').trim(), `h3-${index}`)}</h3>);
        return;
      }

      // Bullet Lists (e.g. * Item or - Item)
      if (trimmed.startsWith('* ') || trimmed.startsWith('- ')) {
        insideList = true;
        listItems.push(trimmed.substring(2));
        return;
      }

      // Empty line closes bullet lists
      if (!trimmed) {
        if (insideList) {
          formattedElements.push(
            <ul key={`list-${index}`} className="list-disc pl-5 mb-4 text-zinc-300 space-y-1.5 animate-fade-in">
              {listItems.map((item, idx) => <li key={`li-${idx}`}>{parseInline(item, `li-${idx}`)}</li>)}
            </ul>
          );
          insideList = false;
          listItems = [];
        }
        return;
      }

      // Normal paragraphs
      if (insideList) {
        formattedElements.push(
          <ul key={`list-${index}`} className="list-disc pl-5 mb-4 text-zinc-300 space-y-1">
            {listItems.map((item, idx) => <li key={`li-${idx}`}>{parseInline(item, `li-${idx}`)}</li>)}
          </ul>
        );
        insideList = false;
        listItems = [];
      }
      
      formattedElements.push(
        <p key={`p-${index}`} className="mb-3.5 leading-relaxed text-zinc-300 text-sm">
          {parseInline(trimmed, `p-${index}`)}
        </p>
      );
    });

    // Final clean list closure if EOF reached
    if (insideList) {
      formattedElements.push(
        <ul key={`list-end`} className="list-disc pl-5 mb-4 text-zinc-300 space-y-1">
          {listItems.map((item, idx) => <li key={`li-${idx}`}>{parseInline(item, `li-${idx}`)}</li>)}
        </ul>
      );
    }

    return formattedElements;
  };

  const getConfidenceBadgeColor = (conf: string) => {
    const clean = conf?.toLowerCase() || '';
    if (clean.includes('high')) return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
    if (clean.includes('mid') || clean.includes('medium')) return 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20';
    return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
  };

  return (
    <div className="w-full flex flex-col gap-5 h-full">
      {/* Search Strategies Toggle Panel */}
      <div className="glass-panel p-4 rounded-2xl border border-zinc-800 flex flex-wrap gap-4 items-center justify-between">
        <div className="flex flex-wrap gap-2.5">
          <button
            onClick={() => setStrategy('baseline')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold tracking-wide border transition-all cursor-pointer ${
              strategy === 'baseline' 
                ? 'bg-zinc-800 border-indigo-500 text-indigo-400 shadow-[0_0_10px_var(--primary-glow)]' 
                : 'bg-zinc-900/40 border-zinc-800 text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Baseline Vector
          </button>
          <button
            onClick={() => setStrategy('hyde')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold tracking-wide border transition-all cursor-pointer ${
              strategy === 'hyde' 
                ? 'bg-zinc-800 border-indigo-500 text-indigo-400 shadow-[0_0_10px_var(--primary-glow)]' 
                : 'bg-zinc-900/40 border-zinc-800 text-zinc-400 hover:text-zinc-200'
            }`}
            title="Hypothetical Document Embeddings - expands query by simulating responses first"
          >
            HyDE Expander
          </button>
          <button
            onClick={() => setStrategy('multi_query')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold tracking-wide border transition-all cursor-pointer ${
              strategy === 'multi_query' 
                ? 'bg-zinc-800 border-indigo-500 text-indigo-400 shadow-[0_0_10px_var(--primary-glow)]' 
                : 'bg-zinc-900/40 border-zinc-800 text-zinc-400 hover:text-zinc-200'
            }`}
            title="Multi-Query + Reciprocal Rank Fusion - generates variations and merges vector matches"
          >
            Multi-Query + RRF
          </button>
          <button
            onClick={() => setStrategy('flare')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold tracking-wide border transition-all cursor-pointer ${
              strategy === 'flare' 
                ? 'bg-zinc-800 border-indigo-500 text-indigo-400 shadow-[0_0_10px_var(--primary-glow)]' 
                : 'bg-zinc-900/40 border-zinc-800 text-zinc-400 hover:text-zinc-200'
            }`}
            title="Forward-Looking Active Retrieval - checks sentence claims dynamically"
          >
            FLARE Active
          </button>
        </div>

        {/* Limit retrieval size */}
        <div className="flex items-center gap-2 text-xs">
          <span className="text-zinc-500 font-medium">Citations:</span>
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="bg-zinc-900 border border-zinc-800 text-zinc-300 px-2.5 py-1 rounded-lg focus:outline-none"
          >
            <option value={3}>3 chunks</option>
            <option value={5}>5 chunks</option>
            <option value={8}>8 chunks</option>
            <option value={12}>12 chunks</option>
          </select>
        </div>
      </div>

      {/* Answer Pane */}
      <div className="flex-1 glass-panel rounded-2xl border border-zinc-800 p-6 flex flex-col justify-between min-h-[350px] overflow-hidden relative">
        <div className="flex-1 overflow-y-auto pr-1">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-full gap-4 text-zinc-500 py-24">
              <div className="relative">
                <Loader2 className="w-10 h-10 animate-spin text-indigo-500" />
                <Sparkles className="w-4 h-4 text-indigo-300 absolute -top-1 -right-1 animate-pulse" />
              </div>
              <div className="flex flex-col items-center gap-1">
                <span className="text-sm font-semibold text-zinc-300">Orchestrating search path...</span>
                <span className="text-xs text-zinc-500 text-center font-mono">
                  {strategy === 'hyde' && 'Synthesizing hypothetical reference document...'}
                  {strategy === 'multi_query' && 'Generating alternative queries & computing RRF...'}
                  {strategy === 'flare' && 'Iterating over factual claims & expanding retrieval contexts...'}
                  {strategy === 'baseline' && 'Searching vector index structures...'}
                </span>
              </div>
            </div>
          ) : error ? (
            <div className="p-4 rounded-xl border border-red-500/20 bg-red-500/5 text-red-400 flex flex-col gap-2 max-w-lg mx-auto mt-12">
              <span className="text-sm font-bold flex items-center gap-1.5"><Info className="w-4 h-4" /> Synthesizer Error</span>
              <p className="text-xs text-zinc-400 leading-normal font-mono">{error}</p>
            </div>
          ) : answer ? (
            <div className="space-y-4 animate-fade-in">
              {/* Header Stats */}
              <div className="flex items-center gap-3 border-b border-zinc-800 pb-3">
                <span className="text-xs font-bold text-zinc-500 uppercase tracking-wider">CogniFlow Output</span>
                {confidence && (
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${getConfidenceBadgeColor(confidence)}`}>
                    Confidence: {confidence}
                  </span>
                )}
              </div>
              
              {/* Answer Content */}
              <div className="prose prose-invert max-w-none text-zinc-200">
                {renderFormattedAnswer(answer)}
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-zinc-600 gap-3 py-24">
              <Sparkles className="w-12 h-12 text-zinc-700/60" />
              <div className="text-center">
                <span className="text-sm font-semibold text-zinc-400">Ask your workspace questions</span>
                <p className="text-xs text-zinc-600 max-w-xs mt-1">
                  Answers will be grounded in files in the active collection ({activeCollection === 'public' ? 'Public DB' : 'Research Papers'}).
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Citations Tray */}
        {citations.length > 0 && !loading && (
          <div className="border-t border-zinc-800/80 pt-4 mt-6 animate-fade-in">
            <h5 className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest mb-3 flex items-center gap-1.5">
              <BookOpen className="w-3.5 h-3.5" /> Groudness Citations ({citations.length})
            </h5>
            <div className="flex flex-wrap gap-2">
              {citations.map((cite) => (
                <button
                  key={cite.id}
                  onClick={() => setSelectedCitation(cite)}
                  className="bg-zinc-900/80 hover:bg-zinc-800 border border-zinc-800 hover:border-zinc-700 rounded-lg px-2.5 py-1.5 text-xs text-zinc-300 hover:text-white transition-all flex items-center gap-2 cursor-pointer max-w-xs text-left"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 shrink-0" />
                  <span className="truncate flex-1 font-semibold">{cite.title}</span>
                  <span className="text-[10px] text-zinc-500 font-mono">[{cite.chunk_idx}]</span>
                  <Maximize2 className="w-3 h-3 text-zinc-500 shrink-0" />
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Query Input Box */}
      <form onSubmit={handleQuery} className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={`Query this RAG workspace (${activeCollection === 'public' ? 'Public Collection' : 'Research Library'})...`}
          className="flex-1 bg-zinc-900/60 border border-zinc-800 text-zinc-200 text-sm px-4 py-3 rounded-xl focus:outline-none focus:border-indigo-500 focus:shadow-[0_0_15px_rgba(99,102,241,0.08)] placeholder-zinc-500"
          required
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold text-sm px-5 rounded-xl transition-all cursor-pointer flex items-center justify-center gap-2 shadow-lg hover:shadow-indigo-500/20"
        >
          {loading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <>
              <Send className="w-4 h-4" />
              <span>Ask</span>
            </>
          )}
        </button>
      </form>

      {/* Citation Overlay Modal */}
      {selectedCitation && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fade-in">
          <div className="glass-panel max-w-2xl w-full rounded-2xl border border-zinc-800 shadow-2xl p-6 flex flex-col gap-4 max-h-[85vh] animate-slide-up">
            <div className="flex items-start justify-between border-b border-zinc-800 pb-3">
              <div>
                <h4 className="text-sm font-bold text-zinc-100 flex items-center gap-1.5">
                  <BookOpen className="w-4 h-4 text-indigo-400" />
                  {selectedCitation.title}
                </h4>
                <div className="flex items-center gap-3 text-[10px] text-zinc-500 font-mono mt-1">
                  <span>File: {selectedCitation.source}</span>
                  <span>Chunk: {selectedCitation.chunk_idx} of {selectedCitation.total_chunks}</span>
                  <span>Distance: {selectedCitation.distance.toFixed(4)}</span>
                </div>
              </div>
              <button
                onClick={() => setSelectedCitation(null)}
                className="text-zinc-500 hover:text-zinc-200 p-1.5 rounded-lg hover:bg-zinc-800/60 transition-all text-xs font-bold"
              >
                Close
              </button>
            </div>
            
            {/* Chunk contents */}
            <div className="flex-1 overflow-y-auto bg-zinc-950/80 rounded-xl p-4 border border-zinc-900 text-sm leading-relaxed text-zinc-300 font-mono whitespace-pre-wrap">
              {selectedCitation.text}
            </div>

            {/* Score chips */}
            <div className="flex items-center justify-between border-t border-zinc-800 pt-3 text-[10px] text-zinc-500">
              <span className="flex items-center gap-1.5">
                <Award className="w-3.5 h-3.5 text-emerald-400" />
                Cosine distance normalized relevance score
              </span>
              <span className="font-bold text-zinc-300 bg-zinc-900 border border-zinc-800 px-2 py-0.5 rounded-md">
                Confidence badge: {selectedCitation.confidence}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
