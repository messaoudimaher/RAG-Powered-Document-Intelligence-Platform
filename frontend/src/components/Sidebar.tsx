'use client';

import React, { useState, useEffect } from 'react';
import { 
  FileText, 
  Trash2, 
  Search, 
  Database,
  RefreshCw,
  FolderOpen,
  Calendar,
  Layers,
  FileCode
} from 'lucide-react';
import { api } from '../utils/api';
import { DocumentInfo } from '../types';

interface SidebarProps {
  activeCollection: 'public' | 'papers';
  onCollectionChange: (collection: 'public' | 'papers') => void;
  onRefreshTrigger: number;
  onDocumentDeleted?: () => void;
}

export default function Sidebar({
  activeCollection,
  onCollectionChange,
  onRefreshTrigger,
  onDocumentDeleted
}: SidebarProps) {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [deletingSource, setDeletingSource] = useState<string | null>(null);

  const loadDocuments = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listDocuments(activeCollection);
      // Sort by added_at descending
      data.sort((a, b) => new Date(b.added_at).getTime() - new Date(a.added_at).getTime());
      setDocuments(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load document library');
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, [activeCollection, onRefreshTrigger]);

  const handleDelete = async (source: string) => {
    if (!confirm(`Are you sure you want to delete "${source}" from the database? This deletes all associated vectors.`)) {
      return;
    }
    setDeletingSource(source);
    try {
      await api.deleteDocument(activeCollection, source);
      await loadDocuments();
      if (onDocumentDeleted) {
        onDocumentDeleted();
      }
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    } finally {
      setDeletingSource(null);
    }
  };

  const getFileIcon = (fileType: string) => {
    const cleanType = fileType.toLowerCase();
    if (cleanType === 'pdf') {
      return <FileText className="w-4 h-4 text-red-400" />;
    } else if (cleanType === 'docx' || cleanType === 'doc') {
      return <FileText className="w-4 h-4 text-blue-400" />;
    } else if (cleanType === 'md' || cleanType === 'markdown') {
      return <FileCode className="w-4 h-4 text-emerald-400" />;
    }
    return <FileText className="w-4 h-4 text-zinc-400" />;
  };

  const filteredDocs = documents.filter(doc => 
    doc.title.toLowerCase().includes(searchQuery.toLowerCase()) || 
    doc.source.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const formatDate = (dateString: string) => {
    try {
      const d = new Date(dateString);
      return d.toLocaleDateString(undefined, { 
        month: 'short', 
        day: 'numeric', 
        hour: '2-digit', 
        minute: '2-digit' 
      });
    } catch (e) {
      return dateString;
    }
  };

  return (
    <div className="w-full flex flex-col h-full glass-panel border border-zinc-800 rounded-2xl overflow-hidden">
      {/* Header Tabs */}
      <div className="flex border-b border-zinc-800 bg-zinc-900/40">
        <button
          onClick={() => onCollectionChange('public')}
          className={`flex-1 py-3.5 text-xs font-semibold tracking-wider flex items-center justify-center gap-2 border-b-2 transition-all cursor-pointer ${
            activeCollection === 'public'
              ? 'border-indigo-500 text-indigo-400 bg-indigo-500/5'
              : 'border-transparent text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/20'
          }`}
        >
          <Database className="w-3.5 h-3.5" />
          PUBLIC DB
        </button>
        <button
          onClick={() => onCollectionChange('papers')}
          className={`flex-1 py-3.5 text-xs font-semibold tracking-wider flex items-center justify-center gap-2 border-b-2 transition-all cursor-pointer ${
            activeCollection === 'papers'
              ? 'border-cyan-500 text-cyan-400 bg-cyan-500/5'
              : 'border-transparent text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/20'
          }`}
        >
          <FolderOpen className="w-3.5 h-3.5" />
          RESEARCH PAPERS
        </button>
      </div>

      {/* Search Bar */}
      <div className="p-3 border-b border-zinc-800 bg-zinc-950/20">
        <div className="relative">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-zinc-500" />
          <input
            type="text"
            placeholder="Filter libraries..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-zinc-900/60 border border-zinc-800 text-zinc-200 text-xs pl-9 pr-3 py-2 rounded-lg focus:outline-none focus:border-zinc-700 placeholder-zinc-500"
          />
        </div>
      </div>

      {/* Library Documents List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        <div className="flex items-center justify-between text-[10px] font-bold text-zinc-500 uppercase tracking-widest px-1">
          <span>Active Files ({filteredDocs.length})</span>
          <button
            onClick={loadDocuments}
            disabled={loading}
            className="hover:text-zinc-300 flex items-center gap-1 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {loading && documents.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-zinc-500 gap-2">
            <RefreshCw className="w-5 h-5 animate-spin text-indigo-500" />
            <span className="text-xs">Scanning registry...</span>
          </div>
        ) : error ? (
          <div className="text-center py-8 px-2 text-xs text-zinc-500 border border-red-500/10 rounded-xl bg-red-500/5">
            Offline / Failed to load. Check server.
          </div>
        ) : filteredDocs.length === 0 ? (
          <div className="text-center py-16 text-zinc-500 text-xs border border-dashed border-zinc-800 rounded-xl mt-2">
            {searchQuery ? 'No matching documents' : 'Library is empty.'}
            <p className="text-[10px] text-zinc-600 mt-1">Upload files or enter arXiv IDs below.</p>
          </div>
        ) : (
          filteredDocs.map((doc) => (
            <div
              key={doc.source}
              className="group relative p-2.5 rounded-xl border border-zinc-800 bg-zinc-900/20 hover:bg-zinc-800/40 hover:border-zinc-700/60 transition-all flex flex-col gap-1 overflow-hidden"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2 min-w-0">
                  {getFileIcon(doc.file_type)}
                  <span className="text-xs font-semibold text-zinc-200 truncate group-hover:text-white transition-colors" title={doc.title}>
                    {doc.title}
                  </span>
                </div>
                
                {/* Delete Button */}
                <button
                  onClick={() => handleDelete(doc.source)}
                  disabled={deletingSource === doc.source}
                  className="opacity-0 group-hover:opacity-100 focus:opacity-100 text-zinc-500 hover:text-red-400 p-1 rounded hover:bg-zinc-800 transition-all cursor-pointer"
                  title="Remove from database"
                >
                  <Trash2 className={`w-3.5 h-3.5 ${deletingSource === doc.source ? 'animate-pulse text-red-400' : ''}`} />
                </button>
              </div>

              {/* Document details line */}
              <div className="flex items-center justify-between text-[10px] text-zinc-500 font-mono mt-1 px-0.5">
                <span className="flex items-center gap-1">
                  <Layers className="w-3 h-3 text-zinc-600" />
                  {doc.chunk_count} chunks
                </span>
                <span className="flex items-center gap-1">
                  <Calendar className="w-3 h-3 text-zinc-600" />
                  {formatDate(doc.added_at)}
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
