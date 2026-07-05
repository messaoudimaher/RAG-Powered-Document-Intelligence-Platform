'use client';

import React, { useState, useRef } from 'react';
import { 
  UploadCloud, 
  Globe, 
  FileText, 
  AlertCircle, 
  CheckCircle2, 
  Cpu, 
  Layers, 
  Loader2,
  HelpCircle
} from 'lucide-react';
import { api } from '../utils/api';

interface IngestPanelProps {
  activeCollection: 'public' | 'papers';
  onIngestionSuccess: () => void;
}

type IngestStep = 'idle' | 'uploading' | 'chunking' | 'embedding' | 'completed' | 'failed';

export default function IngestPanel({ activeCollection, onIngestionSuccess }: IngestPanelProps) {
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  
  // arXiv Ingestion State
  const [arxivId, setArxivId] = useState('');
  const [arxivLoading, setArxivLoading] = useState(false);

  // Status/Progress tracking
  const [ingestState, setIngestState] = useState<IngestStep>('idle');
  const [chunksCount, setChunksCount] = useState(0);
  const [errorMessage, setErrorMessage] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      validateAndSetFile(droppedFile);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (selectedFile: File) => {
    const ext = selectedFile.name.split('.').pop()?.toLowerCase();
    const allowed = ['pdf', 'docx', 'doc', 'txt', 'md', 'markdown'];
    
    setErrorMessage('');
    setIngestState('idle');
    
    if (!ext || !allowed.includes(ext)) {
      setErrorMessage(`Unsupported format .${ext}. Choose PDF, DOCX, TXT or MD.`);
      setFile(null);
      return;
    }
    
    const sizeMb = selectedFile.size / (1024 * 1024);
    if (sizeMb > 15) {
      setErrorMessage('File exceeds size limit of 15MB.');
      setFile(null);
      return;
    }
    
    setFile(selectedFile);
  };

  const pollTaskStatus = (taskId: string) => {
    const interval = setInterval(async () => {
      try {
        const res = await api.getTaskStatus(taskId);
        
        if (res.status === 'PENDING' || res.status === 'RECEIVED') {
          setIngestState('uploading');
        } else if (res.status === 'STARTED' || res.status === 'PROGRESS') {
          setIngestState('embedding');
        } else if (res.status === 'SUCCESS') {
          clearInterval(interval);
          if (res.result) {
            setChunksCount(res.result.chunks_count);
          }
          setIngestState('completed');
          setFile(null);
          if (fileInputRef.current) fileInputRef.current.value = '';
          onIngestionSuccess();
        } else if (res.status === 'FAILURE') {
          clearInterval(interval);
          setErrorMessage(res.error || 'Ingestion task execution failed.');
          setIngestState('failed');
        }
      } catch (err: any) {
        clearInterval(interval);
        setErrorMessage(err.message || 'Error tracking background task.');
        setIngestState('failed');
      }
    }, 1500);
  };

  const handleIngestFile = async () => {
    if (!file) return;
    setIngestState('uploading');
    setErrorMessage('');
    
    try {
      const res = await api.uploadFile(activeCollection, file);
      pollTaskStatus(res.task_id);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to dispatch file ingestion');
      setIngestState('failed');
    }
  };

  const handleIngestArxiv = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanId = arxivId.trim();
    if (!cleanId) return;
    
    setArxivLoading(true);
    setErrorMessage('');
    setIngestState('idle');
    
    try {
      setIngestState('uploading');
      setChunksCount(0);
      
      const res = await api.ingestArxiv(activeCollection, cleanId);
      setArxivId('');
      pollTaskStatus(res.task_id);
    } catch (err: any) {
      setErrorMessage(err.message || 'arXiv download & vectorization failed');
      setIngestState('failed');
    } finally {
      setArxivLoading(false);
    }
  };

  return (
    <div className="glass-panel p-5 rounded-2xl border border-zinc-800 flex flex-col gap-5 h-full justify-between">
      <div>
        <h2 className="text-lg font-semibold text-zinc-100 flex items-center gap-2 mb-3">
          <UploadCloud className="w-5 h-5 text-indigo-400" />
          Ingest Knowledge
        </h2>
        
        {/* File Dropzone */}
        <div
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-6 flex flex-col items-center justify-center text-center cursor-pointer transition-all ${
            dragActive 
              ? 'border-indigo-500 bg-indigo-500/5 shadow-[0_0_15px_rgba(99,102,241,0.1)]' 
              : file 
                ? 'border-indigo-500/50 bg-indigo-500/2'
                : 'border-zinc-800 hover:border-zinc-700 bg-zinc-900/10 hover:bg-zinc-900/20'
          }`}
        >
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            className="hidden"
            accept=".pdf,.docx,.doc,.txt,.md,.markdown"
          />
          
          {file ? (
            <div className="flex flex-col items-center gap-2">
              <FileText className="w-10 h-10 text-indigo-400 animate-pulse-glow rounded" />
              <span className="text-xs font-semibold text-zinc-200 truncate max-w-[200px]">
                {file.name}
              </span>
              <span className="text-[10px] text-zinc-500 font-mono">
                {(file.size / (1024 * 1024)).toFixed(2)} MB
              </span>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <UploadCloud className="w-10 h-10 text-zinc-600 group-hover:text-indigo-400 transition-colors" />
              <span className="text-xs font-medium text-zinc-300">
                Drag & drop document or <span className="text-indigo-400 hover:underline">browse</span>
              </span>
              <span className="text-[10px] text-zinc-500">
                PDF, DOCX, TXT, MD (Max 15MB)
              </span>
            </div>
          )}
        </div>

        {/* Action Button for File Ingest */}
        {file && (
          <button
            onClick={handleIngestFile}
            disabled={ingestState !== 'idle' && ingestState !== 'completed'}
            className="w-full mt-3 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs py-2.5 rounded-lg transition-colors flex items-center justify-center gap-2 cursor-pointer shadow-md hover:shadow-lg"
          >
            {ingestState === 'uploading' || ingestState === 'chunking' || ingestState === 'embedding' ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Vectorizing Document...
              </>
            ) : (
              <>Ingest Document</>
            )}
          </button>
        )}

        {/* Divider */}
        <div className="relative my-5">
          <div className="absolute inset-0 flex items-center" aria-hidden="true">
            <div className="w-full border-t border-zinc-800" />
          </div>
          <div className="relative flex justify-center text-[10px] font-bold uppercase tracking-wider">
            <span className="bg-[#0e0f16] px-2 text-zinc-500">Or Ingest arXiv Paper</span>
          </div>
        </div>

        {/* arXiv Ingestion Input */}
        <form onSubmit={handleIngestArxiv} className="flex gap-2">
          <div className="relative flex-1">
            <Globe className="absolute left-3 top-2.5 w-4 h-4 text-zinc-600" />
            <input
              type="text"
              placeholder="e.g. 2305.16300"
              value={arxivId}
              onChange={(e) => setArxivId(e.target.value)}
              disabled={arxivLoading}
              className="w-full bg-zinc-900/60 border border-zinc-800 text-zinc-200 text-xs pl-9 pr-3 py-2 rounded-lg focus:outline-none focus:border-zinc-700 placeholder-zinc-600"
            />
          </div>
          <button
            type="submit"
            disabled={arxivLoading || !arxivId.trim()}
            className="bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white font-semibold text-xs px-4 rounded-lg transition-colors flex items-center justify-center cursor-pointer"
          >
            {arxivLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Fetch'}
          </button>
        </form>
      </div>

      {/* Progress & Feedback State Dashboard Overlay */}
      {(ingestState !== 'idle' || errorMessage) && (
        <div className="mt-4 p-3 rounded-xl border border-zinc-800/80 bg-zinc-950/40 space-y-2.5 animate-fade-in">
          {/* Status Message */}
          <div className="flex items-center gap-2">
            {ingestState === 'uploading' && (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
                <span className="text-xs text-zinc-300">Downloading/Reading file stream...</span>
              </>
            )}
            {ingestState === 'chunking' && (
              <>
                <Layers className="w-4 h-4 text-indigo-400 animate-pulse" />
                <span className="text-xs text-zinc-300">Splitting text into recursive chunks...</span>
              </>
            )}
            {ingestState === 'embedding' && (
              <>
                <Cpu className="w-4 h-4 text-indigo-400 animate-spin" />
                <span className="text-xs text-zinc-300">Computing embeddings (Ollama local)...</span>
              </>
            )}
            {ingestState === 'completed' && (
              <>
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <div className="flex flex-col">
                  <span className="text-xs font-semibold text-emerald-400">Ingested Successfully!</span>
                  <span className="text-[10px] text-zinc-400">Created {chunksCount} vector embeddings in {activeCollection}.</span>
                </div>
              </>
            )}
            {ingestState === 'failed' && (
              <>
                <AlertCircle className="w-4 h-4 text-red-400" />
                <span className="text-xs font-semibold text-red-400">Ingestion failed</span>
              </>
            )}
          </div>

          {/* Progress Bar (Visual representation) */}
          <div className="w-full bg-zinc-900 rounded-full h-1.5 overflow-hidden">
            <div 
              className={`h-full transition-all duration-500 rounded-full ${
                ingestState === 'completed' 
                  ? 'bg-emerald-500 w-full' 
                  : ingestState === 'failed' 
                    ? 'bg-red-500 w-full'
                    : ingestState === 'uploading' 
                      ? 'bg-indigo-600 w-[25%]'
                      : ingestState === 'chunking' 
                        ? 'bg-indigo-600 w-[60%]'
                        : ingestState === 'embedding' 
                          ? 'bg-indigo-600 w-[85%]'
                          : 'w-0'
              }`}
            />
          </div>

          {/* Error Message */}
          {errorMessage && (
            <p className="text-[10px] text-red-400 leading-normal border-t border-zinc-800 pt-2 font-mono break-all">
              Details: {errorMessage}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
