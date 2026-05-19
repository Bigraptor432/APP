import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  MessageSquare, LayoutDashboard, Shield, Terminal,
  Settings, X, Eye, EyeOff, Send, CheckCircle,
  XCircle, Plus, AlertCircle, CheckSquare, Square,
  Key, Save, Loader2, Hash, Radio, ChevronRight, AlertTriangle,
  FileSearch, GitBranch, Globe, Code2, Database,
  Zap, Activity, Lock, Minus, Square as SquareIcon, ArrowUp, Columns2, Paperclip
} from 'lucide-react';

// ─── TITLE BAR ──────────────────────────────────────────────────────────
function TitleBar() {
  if (!window.electron) return null;
  const isMac = navigator.platform.toLowerCase().includes('mac');
  const btn = 'h-full px-4 flex items-center justify-center transition-colors';
  return (
    <div
      className="flex items-center justify-between h-8 flex-shrink-0"
      style={{ background: '#0a0a0a', borderBottom: '1px solid #1a1a1a', WebkitAppRegion: 'drag', paddingLeft: isMac ? 72 : 0 }}
    >
      <div className="flex items-center gap-2 px-3">
        <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: '#ff3333' }} />
        <span className="font-mono text-[10px] tracking-widest" style={{ color: '#666' }}>MANUCASPT · PENTEST PLATFORM</span>
      </div>
      {!isMac && (
      <div className="flex items-center h-full" style={{ WebkitAppRegion: 'no-drag' }}>
        <button className={btn} style={{ color: '#888' }} onClick={() => window.electron.winMinimize()}
          onMouseEnter={e => e.currentTarget.style.background = '#1a1a1a'}
          onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
          <Minus size={12} />
        </button>
        <button className={btn} style={{ color: '#888' }} onClick={() => window.electron.winMaximize()}
          onMouseEnter={e => e.currentTarget.style.background = '#1a1a1a'}
          onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
          <SquareIcon size={10} />
        </button>
        <button className={btn} style={{ color: '#888' }} onClick={() => window.electron.winClose()}
          onMouseEnter={e => { e.currentTarget.style.background = '#ff3333'; e.currentTarget.style.color = '#fff'; }}
          onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#888'; }}>
          <X size={12} />
        </button>
      </div>
      )}
    </div>
  );
}

// ─── CONSTANTS ────────────────────────────────────────────────────────────────

const C = {
  bg: '#0d0d0d',
  panel: '#141414',
  border: '#1e1e1e',
  red: '#ff3333',
  redDim: 'rgba(255,51,51,0.12)',
  redBorder: 'rgba(255,51,51,0.25)',
  text: '#c9c9c9',
  textDim: '#666',
  textFaint: '#3a3a3a',
  green: '#22c55e',
  orange: '#f97316',
};

// ─── STATIC DATA ──────────────────────────────────────────────────────────────

const TARGETS_DEFAULT = [];

const CONVERSATIONS = [];

const TARGET_FINDINGS = {};

const TARGET_PLAN = {};

const NAV_ITEMS = [
  { id: 'chat',      label: 'Chat',      Icon: MessageSquare    },
  { id: 'dashboard', label: 'Dashboard', Icon: LayoutDashboard  },
  { id: 'pentest',   label: 'Pentest',   Icon: Shield           },
  { id: 'terminals', label: 'Terminal', Icon: Terminal         },
];


// ─── PERSISTENCE ────────────────────────────────────────────────────────────

const LS = {
  get: (key, fallback) => { try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; } catch { return fallback; } },
  set: (key, val)      => { try { localStorage.setItem(key, JSON.stringify(val)); } catch {} },
};

const supaHeaders = (key) => ({
  'apikey': key,
  'Authorization': `Bearer ${key}`,
  'Content-Type': 'application/json',
});

const supaLoad = async (url, key) => {
  const r = await fetch(`${url}/rest/v1/app_state?select=key,value`, { headers: supaHeaders(key) });
  if (!r.ok) throw new Error(r.status);
  return r.json();
};

const supaSave = async (url, key, rows) => {
  const r = await fetch(`${url}/rest/v1/app_state`, {
    method: 'POST',
    headers: { ...supaHeaders(key), 'Prefer': 'resolution=merge-duplicates' },
    body: JSON.stringify(rows),
  });
  if (!r.ok) throw new Error(r.status);
};

// ─── HELPERS ──────────────────────────────────────────────────────────────────

const now = () => {
  const d = new Date();
  return [d.getHours(), d.getMinutes(), d.getSeconds()]
    .map(n => String(n).padStart(2, '0'))
    .join(':');
};


// ─── CONFIRM MODAL ─────────────────────────────────────────────────────────────

function ConfirmModal({ open, message, onConfirm, onCancel }) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(6px)' }}
    >
      <div
        className="rounded-xl shadow-2xl border p-6 flex flex-col gap-5"
        style={{ background: '#111', border: `1px solid ${C.border}`, minWidth: 300, maxWidth: 360 }}
      >
        <div className="flex items-start gap-3">
          <AlertTriangle size={16} style={{ color: C.red, flexShrink: 0, marginTop: 1 }} />
          <p className="font-mono text-xs leading-relaxed" style={{ color: '#bbb' }}>{message}</p>
        </div>
        <div className="flex gap-2 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded-lg font-mono text-xs transition-all"
            style={{ border: `1px solid ${C.border}`, color: C.textDim }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = '#333')}
            onMouseLeave={e => (e.currentTarget.style.borderColor = C.border)}
          >
            Cancelar
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 rounded-lg font-mono text-xs font-medium transition-all"
            style={{ background: C.redDim, border: `1px solid ${C.redBorder}`, color: C.red }}
            onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,51,51,0.2)')}
            onMouseLeave={e => (e.currentTarget.style.background = C.redDim)}
          >
            Confirmar
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── SETTINGS MODAL ────────────────────────────────────────────────────────────

function SettingsModal({ open, onClose, anthropicKey, groqKey, supaUrl, supaKey, mcpUrl, onSave, onReset }) {
  const [aVal,  setAVal]  = useState(anthropicKey);
  const [gVal,  setGVal]  = useState(groqKey);
  const [sUrl,  setSUrl]  = useState(supaUrl);
  const [sKey,  setSKey]  = useState(supaKey);
  const [mUrl,  setMUrl]  = useState(mcpUrl);
  const [showA, setShowA] = useState(false);
  const [showG, setShowG] = useState(false);
  const [showS, setShowS] = useState(false);
  const [aStatus, setAStatus] = useState('idle');
  const [gStatus, setGStatus] = useState('idle');
  const [mStatus, setMStatus] = useState('idle');
  const [mTools,  setMTools]  = useState(0);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [updStatus,   setUpdStatus]   = useState('idle');  // idle | checking | uptodate | available
  const [updInfo,     setUpdInfo]     = useState(null);
  const CURRENT_VER = typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : '?';

  const checkUpdates = async () => {
    setUpdStatus('checking');
    try {
      const res  = await fetch('https://api.github.com/repos/Bigraptor432/APP/releases/latest');
      const data = await res.json();
      const latest = (data.tag_name || '').replace(/^v/, '');
      if (latest && latest !== CURRENT_VER) {
        const dlUrl = data.assets?.find(a => a.name.endsWith('.exe'))?.browser_download_url || null;
        setUpdStatus('available');
        setUpdInfo({ version: latest, url: data.html_url, downloadUrl: dlUrl });
      } else {
        setUpdStatus('uptodate');
      }
    } catch (_) {
      setUpdStatus('idle');
    }
  };

  const checkKey = async (type, key, setStatus) => {
    if (!key.trim() || !window.electron) { setStatus('idle'); return; }
    setStatus('checking');
    try {
      const r = await window.electron.validateKey({ type, key: key.trim() });
      setStatus(r.ok ? 'ok' : 'error');
    } catch { setStatus('error'); }
  };

  const checkMcp = async (url) => {
    if (!url.trim() || !window.electron) { setMStatus('idle'); setMTools(0); return; }
    setMStatus('checking');
    try {
      const r = await window.electron.mcpGetTools(url.trim());
      if (r?.tools?.length > 0) { setMStatus('ok'); setMTools(r.tools.length); }
      else { setMStatus('error'); setMTools(0); }
    } catch { setMStatus('error'); setMTools(0); }
  };

  useEffect(() => {
    if (open) {
      setAVal(anthropicKey); setGVal(groqKey); setSUrl(supaUrl); setSKey(supaKey); setMUrl(mcpUrl);
      setAStatus('idle'); setGStatus('idle'); setMStatus('idle'); setMTools(0);
      if (anthropicKey) checkKey('anthropic', anthropicKey, setAStatus);
      if (groqKey)      checkKey('groq',      groqKey,      setGStatus);
      if (mcpUrl)       checkMcp(mcpUrl);
    }
  }, [open]);
  if (!open) return null;

  const dotColor = (status, val) => {
    if (!val.trim()) return C.red;
    if (status === 'ok')       return C.green;
    if (status === 'checking') return C.orange;
    if (status === 'error')    return C.red;
    return '#555';
  };

  const save = () => { onSave({ anthropic: aVal.trim(), groq: gVal.trim(), supaUrl: sUrl.trim(), supaKey: sKey.trim(), mcpUrl: mUrl.trim() }); onClose(); };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(4px)' }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="w-full max-w-md rounded-xl shadow-2xl border"
        style={{ background: C.panel, borderColor: C.border }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b" style={{ borderColor: C.border }}>
          <div className="flex items-center gap-2">
            <Key size={14} style={{ color: C.red }} />
            <span className="font-mono text-xs tracking-widest uppercase" style={{ color: C.text }}>
              Configurações
            </span>
          </div>
          <button onClick={onClose} className="transition-colors hover:opacity-70" style={{ color: C.textDim }}>
            <X size={15} />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-4">
          {/* Anthropic key */}
          <div>
            <label className="block font-mono text-[10px] uppercase tracking-widest mb-2" style={{ color: C.textDim }}>
              <span style={{ color: dotColor(aStatus, aVal) }}>●</span> Anthropic API Key
              {aStatus === 'checking' && <span style={{ color: C.orange }}> · a verificar...</span>}
              {aStatus === 'ok'       && <span style={{ color: C.green  }}> · válida</span>}
              {aStatus === 'error'    && <span style={{ color: C.red    }}> · inválida</span>}
              <span style={{ color: C.textFaint }}>{aStatus === 'idle' ? ' · principal (Claude)' : ''}</span>
            </label>
            <div className="relative">
              <input
                type={showA ? 'text' : 'password'}
                value={aVal}
                onChange={e => setAVal(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && save()}
                placeholder="sk-ant-..."
                className="w-full rounded-lg px-3 py-2.5 pr-10 font-mono text-xs outline-none transition-all"
                style={{ background: C.bg, border: `1px solid ${C.border}`, color: C.text }}
                onFocus={e => (e.target.style.borderColor = C.red)}
                onBlur={e  => { e.target.style.borderColor = C.border; checkKey('anthropic', aVal, setAStatus); }}
              />
              <button
                onClick={() => setShowA(s => !s)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 transition-opacity hover:opacity-70"
                style={{ color: C.textDim }}
              >
                {showA ? <EyeOff size={13} /> : <Eye size={13} />}
              </button>
            </div>
            <p className="font-mono text-[9px] mt-1.5" style={{ color: C.textFaint }}>
              console.anthropic.com → Settings → API Keys
            </p>
          </div>

          {/* Groq key */}
          <div>
            <label className="block font-mono text-[10px] uppercase tracking-widest mb-2" style={{ color: C.textDim }}>
              <span style={{ color: dotColor(gStatus, gVal) }}>●</span> Groq API Key
              {gStatus === 'checking' && <span style={{ color: C.orange }}> · a verificar...</span>}
              {gStatus === 'ok'       && <span style={{ color: C.green  }}> · válida</span>}
              {gStatus === 'error'    && <span style={{ color: C.red    }}> · inválida</span>}
              <span style={{ color: C.textFaint }}>{gStatus === 'idle' ? ' · auxiliar (Gemma) · grátis' : ''}</span>
            </label>
            <div className="relative">
              <input
                type={showG ? 'text' : 'password'}
                value={gVal}
                onChange={e => setGVal(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && save()}
                placeholder="gsk_..."
                className="w-full rounded-lg px-3 py-2.5 pr-10 font-mono text-xs outline-none transition-all"
                style={{ background: C.bg, border: `1px solid ${C.border}`, color: C.text }}
                onFocus={e => (e.target.style.borderColor = C.green)}
                onBlur={e  => { e.target.style.borderColor = C.border; checkKey('groq', gVal, setGStatus); }}
              />
              <button
                onClick={() => setShowG(s => !s)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 transition-opacity hover:opacity-70"
                style={{ color: C.textDim }}
              >
                {showG ? <EyeOff size={13} /> : <Eye size={13} />}
              </button>
            </div>
            <p className="font-mono text-[9px] mt-1.5" style={{ color: C.textFaint }}>
              console.groq.com → API Keys (free tier · ~30 req/min)
            </p>
          </div>

          {/* Supabase */}
          <div style={{ borderTop: `1px solid ${C.border}`, paddingTop: 14 }}>
            <label className="block font-mono text-[10px] uppercase tracking-widest mb-3" style={{ color: C.textDim }}>
              <span style={{ color: '#3ecf8e' }}>●</span> Supabase <span style={{ color: C.textFaint }}>· cloud database · opcional · grátis</span>
            </label>
            <div className="space-y-2">
              <input
                type="text"
                value={sUrl}
                onChange={e => setSUrl(e.target.value)}
                placeholder="https://xxxx.supabase.co"
                className="w-full rounded-lg px-3 py-2 font-mono text-xs outline-none transition-all"
                style={{ background: C.bg, border: `1px solid ${C.border}`, color: C.text }}
                onFocus={e => (e.target.style.borderColor = '#3ecf8e')}
                onBlur={e  => (e.target.style.borderColor = C.border)}
              />
              <div className="relative">
                <input
                  type={showS ? 'text' : 'password'}
                  value={sKey}
                  onChange={e => setSKey(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && save()}
                  placeholder="anon key (eyJ...)"
                  className="w-full rounded-lg px-3 py-2 pr-10 font-mono text-xs outline-none transition-all"
                  style={{ background: C.bg, border: `1px solid ${C.border}`, color: C.text }}
                  onFocus={e => (e.target.style.borderColor = '#3ecf8e')}
                  onBlur={e  => (e.target.style.borderColor = C.border)}
                />
                <button
                  onClick={() => setShowS(s => !s)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 transition-opacity hover:opacity-70"
                  style={{ color: C.textDim }}
                >
                  {showS ? <EyeOff size={13} /> : <Eye size={13} />}
                </button>
              </div>
            </div>
            <p className="font-mono text-[9px] mt-1.5" style={{ color: C.textFaint }}>
              supabase.com → Project → Settings → API (URL + anon key)
            </p>
          </div>

          {/* MCP Server */}
          <div style={{ borderTop: `1px solid ${C.border}`, paddingTop: 14 }}>
            <label className="block font-mono text-[10px] uppercase tracking-widest mb-2" style={{ color: C.textDim }}>
              <span style={{ color: dotColor(mStatus, mUrl) }}>●</span> Kali MCP Server
              {mStatus === 'checking' && <span style={{ color: C.orange }}> · a ligar...</span>}
              {mStatus === 'ok'       && <span style={{ color: C.green  }}> · {mTools} tools ativas</span>}
              {mStatus === 'error'    && <span style={{ color: C.red    }}> · sem ligação</span>}
              {(mStatus === 'idle' || mStatus === 'unknown') && <span style={{ color: C.textFaint }}> · tools de pentest · opcional</span>}
            </label>
            <input
              type="text"
              value={mUrl}
              onChange={e => { setMUrl(e.target.value); setMStatus('idle'); }}
              onKeyDown={e => e.key === 'Enter' && checkMcp(mUrl)}
              placeholder="http://192.168.1.100:3000"
              className="w-full rounded-lg px-3 py-2 font-mono text-xs outline-none transition-all"
              style={{ background: C.bg, border: `1px solid ${C.border}`, color: C.text }}
              onFocus={e => (e.target.style.borderColor = C.orange)}
              onBlur={e  => { e.target.style.borderColor = C.border; checkMcp(mUrl); }}
            />
            <p className="font-mono text-[9px] mt-1.5" style={{ color: C.textFaint }}>
              IP do Kali → python3 kali-mcp-server.py
            </p>
          </div>

          {/* Versão / Atualização */}
          <div style={{ borderTop: `1px solid ${C.border}`, paddingTop: 14 }}>
            <div className="flex items-center justify-between">
              <div>
                <span className="font-mono text-[10px] uppercase tracking-widest" style={{ color: C.textDim }}>Versão</span>
                <span className="font-mono text-[10px] ml-2" style={{ color: '#444' }}>v{CURRENT_VER}</span>
                {updStatus === 'uptodate'  && <span className="font-mono text-[10px] ml-2" style={{ color: C.green }}>· atualizado ✓</span>}
                {updStatus === 'checking'  && <span className="font-mono text-[10px] ml-2" style={{ color: C.orange }}>· a verificar...</span>}
                {updStatus === 'available' && updInfo && <span className="font-mono text-[10px] ml-2" style={{ color: C.red }}>· v{updInfo.version} disponível</span>}
              </div>
              {updStatus === 'available' && updInfo ? (
                <button
                  onClick={() => {
                    if (updInfo.downloadUrl) window.electron?.downloadUpdate({ url: updInfo.downloadUrl });
                    else window.electron?.openExternal(updInfo.url);
                  }}
                  className="font-mono text-[9px] px-3 py-1 rounded-lg font-bold uppercase tracking-widest"
                  style={{ background: C.redDim, border: `1px solid ${C.redBorder}`, color: C.red }}
                >
                  ↓ Baixar v{updInfo.version}
                </button>
              ) : (
                <button
                  onClick={checkUpdates}
                  disabled={updStatus === 'checking'}
                  className="font-mono text-[9px] px-3 py-1 rounded-lg transition-all"
                  style={{ background: '#1a1a1a', color: C.textDim, border: `1px solid ${C.border}`, opacity: updStatus === 'checking' ? 0.5 : 1 }}
                >
                  Verificar atualização
                </button>
              )}
            </div>
          </div>

          <div className="flex gap-2 pt-1">
            <button
              onClick={save}
              className="flex-1 flex items-center justify-center gap-2 rounded-lg py-2.5 font-mono text-xs font-medium transition-all"
              style={{
                background: C.redDim,
                border: `1px solid ${C.redBorder}`,
                color: C.red,
              }}
              onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,51,51,0.2)')}
              onMouseLeave={e => (e.currentTarget.style.background = C.redDim)}
            >
              <Save size={13} /> Guardar
            </button>
            <button
              onClick={onClose}
              className="px-5 rounded-lg font-mono text-xs transition-all"
              style={{ border: `1px solid ${C.border}`, color: C.textDim }}
              onMouseEnter={e => (e.currentTarget.style.borderColor = '#333')}
              onMouseLeave={e => (e.currentTarget.style.borderColor = C.border)}
            >
              Cancelar
            </button>
            <button
              onClick={() => setConfirmOpen(true)}
              className="px-3 rounded-lg font-mono text-xs transition-all"
              style={{ border: '1px solid #2a1a1a', color: '#552222' }}
              title="Apagar todos os dados"
              onMouseEnter={e => { e.currentTarget.style.borderColor = C.redBorder; e.currentTarget.style.color = C.red; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = '#2a1a1a'; e.currentTarget.style.color = '#552222'; }}
            >
              Reset
            </button>
          </div>
        </div>
      </div>
      <ConfirmModal
        open={confirmOpen}
        message="Apagar TODOS os dados locais e na cloud? Esta ação não pode ser desfeita."
        onConfirm={() => { setConfirmOpen(false); onReset(); onClose(); }}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}

// ─── SIDEBAR ITEMS WITH INLINE RENAME ────────────────────────────────────────

function TargetItem({ t, isActive, onClick, onDelete, onRename }) {
  const [editing, setEditing] = useState(false);
  const [val, setVal]         = useState(t.name);
  const inputRef              = useRef(null);

  const start = (e) => { e.stopPropagation(); setVal(t.name); setEditing(true); setTimeout(() => inputRef.current?.select(), 0); };
  const commit = () => { const v = val.trim(); if (v && v !== t.name) onRename(t.id, v); setEditing(false); };
  const onKey  = (e) => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') setEditing(false); };

  return (
    <div
      onClick={onClick}
      className="group flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer transition-all"
      style={{ background: isActive ? '#1c1c1c' : 'transparent' }}
      onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = '#181818'; }}
      onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
    >
      <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: isActive ? C.red : '#3a3a3a' }} />
      <div className="min-w-0 flex-1">
        {editing ? (
          <input
            ref={inputRef}
            value={val}
            onChange={e => setVal(e.target.value)}
            onBlur={commit}
            onKeyDown={onKey}
            onClick={e => e.stopPropagation()}
            className="w-full font-mono text-[10px] outline-none"
            style={{ color: '#ccc', background: 'transparent', caretColor: C.red, border: 'none' }}
          />
        ) : (
          <div className="font-mono text-[10px] truncate" style={{ color: isActive ? '#bbb' : C.textDim }} onDoubleClick={start}>
            {t.name}
          </div>
        )}
      </div>
      {!editing && (
        <button onClick={e => { e.stopPropagation(); onDelete(t.id); }} className="opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" style={{ color: '#555' }} title="Remover">
          <X size={9} />
        </button>
      )}
    </div>
  );
}

function ConvItem({ c, isCurrent, onClick, onDelete, onRename }) {
  const [editing, setEditing] = useState(false);
  const [val, setVal]         = useState(c.label);
  const inputRef              = useRef(null);

  const start  = (e) => { e.stopPropagation(); setVal(c.label); setEditing(true); setTimeout(() => inputRef.current?.select(), 0); };
  const commit = () => { const v = val.trim(); if (v && v !== c.label) onRename(c.id, v); setEditing(false); };
  const onKey  = (e) => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') setEditing(false); };

  return (
    <div
      onClick={onClick}
      className="group flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer font-mono text-[10px] transition-all"
      style={{ background: isCurrent ? '#1c1c1c' : 'transparent', color: isCurrent ? '#bbb' : '#4a4a4a' }}
      onMouseEnter={e => { if (!isCurrent) { e.currentTarget.style.background = '#181818'; e.currentTarget.style.color = '#777'; } }}
      onMouseLeave={e => { if (!isCurrent) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#4a4a4a'; } }}
    >
      <MessageSquare size={9} style={{ flexShrink: 0, color: isCurrent ? C.red : 'inherit' }} />
      {editing ? (
        <input
          ref={inputRef}
          value={val}
          onChange={e => setVal(e.target.value)}
          onBlur={commit}
          onKeyDown={onKey}
          onClick={e => e.stopPropagation()}
          className="flex-1 font-mono text-[10px] outline-none"
          style={{ color: '#ccc', background: 'transparent', caretColor: C.red, border: 'none' }}
        />
      ) : (
        <span className="truncate flex-1" onDoubleClick={start}>{c.label}</span>
      )}
      {!editing && (
        <button onClick={e => { e.stopPropagation(); onDelete(c.id); }} className="opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" style={{ color: '#555' }} title="Apagar">
          <X size={9} />
        </button>
      )}
    </div>
  );
}

// ─── SIDEBAR ───────────────────────────────────────────────────────────────────

function Sidebar({ onSettings, activeNav, onNavChange, targets, activeTarget, onTargetChange, onAddTarget, onDeleteTarget, onRenameTarget, convs, activeConv, onConvChange, onAddConv, onDeleteConv, onRenameConv, updateInfo, onUpdateClick }) {
  return (
    <aside
      className="flex flex-col flex-shrink-0 h-full select-none"
      style={{ width: 172, background: '#0f0f0f', borderRight: `1px solid ${C.border}` }}
    >
      {/* Logo row */}
      <div
        className="flex items-center justify-between px-4 py-3.5"
        style={{ borderBottom: `1px solid ${C.border}` }}
      >
        <span className="font-mono font-bold text-sm tracking-[.18em]" style={{ color: C.red }}>
          ManucasPT
        </span>
        <div className="flex items-center gap-1.5">
          {updateInfo && (
            <button
              onClick={onUpdateClick}
              title={`Atualização disponível: v${updateInfo.version}`}
              className="relative flex items-center justify-center w-5 h-5 rounded-full animate-pulse"
              style={{ background: 'rgba(249,115,22,0.15)', border: '1px solid #f97316' }}
            >
              <span style={{ color: '#f97316', fontSize: 9, fontWeight: 700 }}>↑</span>
            </button>
          )}
          <button
            onClick={onSettings}
            className="transition-opacity hover:opacity-60"
            style={{ color: C.textDim }}
            title="Configurações"
          >
            <Settings size={13} />
          </button>
        </div>
      </div>

      {/* Nav */}
      <nav className="p-2 space-y-px" style={{ borderBottom: `1px solid ${C.border}` }}>
        {NAV_ITEMS.map(({ id, label, Icon }) => {
          const isActive = activeNav === id;
          return (
            <button
              key={id}
              onClick={() => onNavChange(id)}
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded text-xs font-medium transition-all"
              style={{
                background:   isActive ? C.redDim : 'transparent',
                border:       isActive ? `1px solid ${C.redBorder}` : '1px solid transparent',
                color:        isActive ? C.red    : C.textDim,
              }}
              onMouseEnter={e => { if (!isActive) e.currentTarget.style.color = '#aaa'; }}
              onMouseLeave={e => { if (!isActive) e.currentTarget.style.color = C.textDim; }}
            >
              <Icon size={12} />
              {label}
            </button>
          );
        })}
      </nav>

      {/* Targets */}
      <div className="p-3" style={{ borderBottom: `1px solid ${C.border}` }}>
        <div className="flex items-center justify-between mb-2">
          <span className="font-mono text-[9px] uppercase tracking-widest" style={{ color: C.textDim }}>
            ALVOS
          </span>
          <button onClick={onAddTarget} style={{ color: C.textDim }} className="hover:opacity-80 transition-opacity">
            <Plus size={10} />
          </button>
        </div>
        <div className="space-y-1">
          {targets.map(t => (
            <TargetItem
              key={t.id}
              t={t}
              isActive={activeTarget === t.id}
              onClick={() => onTargetChange(t.id)}
              onDelete={onDeleteTarget}
              onRename={onRenameTarget}
            />
          ))}
        </div>
      </div>

      {/* Conversations */}
      <div className="p-3 flex-1 overflow-y-auto">
        <div className="flex items-center justify-between mb-2">
          <span className="font-mono text-[9px] uppercase tracking-widest" style={{ color: C.textDim }}>
            CONVERSAS
          </span>
          <button onClick={onAddConv} style={{ color: C.textDim }} className="hover:opacity-80 transition-opacity">
            <Plus size={10} />
          </button>
        </div>
        <div className="space-y-px">
          {convs.map(c => (
            <ConvItem
              key={c.id}
              c={c}
              isCurrent={activeConv === c.id}
              onClick={() => onConvChange(c.id)}
              onDelete={onDeleteConv}
              onRename={onRenameConv}
            />
          ))}
        </div>
      </div>
    </aside>
  );
}

// ─── ACTIVITY LOG ──────────────────────────────────────────────────────────────

function ActivityLog({ logs, activeTarget }) {
  const ref = useRef(null);

  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [logs]);

  return (
    <section
      className="flex flex-col flex-shrink-0 h-full"
      style={{ width: 215, background: C.bg, borderRight: `1px solid ${C.border}` }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-3 py-2.5"
        style={{ borderBottom: `1px solid ${C.border}` }}
      >
        <span className="font-mono text-[9px] uppercase tracking-widest" style={{ color: C.textDim }}>
          ACTIVITY
        </span>
        <div className="flex items-center gap-1.5">
          <span
            className="inline-block w-1.5 h-1.5 rounded-full"
            style={{ background: C.red, animation: 'cursor-blink 1.2s step-end infinite' }}
          />
          <span className="font-mono text-[9px]" style={{ color: '#444' }}>live</span>
        </div>
      </div>

      {/* Entries */}
      <div ref={ref} className="flex-1 overflow-y-auto py-1">
        {logs.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-2 px-3">
            <Activity size={16} style={{ color: '#2a2a2a' }} />
            <p className="font-mono text-[9px] text-center" style={{ color: '#333' }}>
              nenhuma atividade<br/>inicie um scan em Pentest
            </p>
          </div>
        )}
        {logs.map((entry, i) => (
          <div
            key={entry.id}
            className="flex items-center gap-1.5 px-3 py-[3px] hover:bg-[#141414] transition-colors entry-in"
          >
            <span
              className="font-mono tabular-nums flex-shrink-0"
              style={{ fontSize: 9, color: '#3a3a3a', width: 52 }}
            >
              {entry.time}
            </span>
            {entry.status === 'success' ? (
              <CheckCircle size={9} style={{ color: '#22c55e', flexShrink: 0 }} />
            ) : (
              <XCircle size={9} style={{ color: C.red, flexShrink: 0 }} />
            )}
            <span
              className="font-mono truncate"
              style={{
                fontSize: 10,
                color: entry.status === 'error' ? 'rgba(255,51,51,0.75)' : '#5a5a5a',
              }}
            >
              {entry.tool}
            </span>
            <span className="font-mono ml-auto flex-shrink-0" style={{ fontSize: 9, color: '#333' }}>
              #2
            </span>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div
        className="px-3 py-2"
        style={{ borderTop: `1px solid ${C.border}` }}
      >
        <p className="font-mono" style={{ fontSize: 9, color: '#3a3a3a' }}>
          {logs.length > 0 ? `${logs.length} entradas · target-0${activeTarget}` : 'aguardando execução...'}
        </p>
      </div>
    </section>
  );
}

// ─── FINDING CARD ──────────────────────────────────────────────────────────────

function FindingCard({ severity, type, cve, url, scanner }) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{ background: C.panel, border: `1px solid ${C.border}` }}
    >
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left"
        style={{ borderBottom: expanded ? `1px solid ${C.border}` : 'none' }}
      >
        <span
          className="inline-block w-1.5 h-1.5 rounded-full flex-shrink-0"
          style={{ background: C.red }}
        />
        <span className="font-mono text-[11px] font-semibold flex-1" style={{ color: C.red }}>
          [CRITICAL] {type}
        </span>
        <ChevronRight
          size={11}
          style={{
            color: C.textDim,
            transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s',
          }}
        />
      </button>

      {expanded && (
        <div className="p-3 space-y-2 font-mono text-[10px]">
          <div style={{ color: '#555' }}>
            template:{' '}
            <span style={{ color: C.orange }}>{cve}</span>
          </div>
          <div style={{ color: '#555' }}>url:</div>
          <div
            className="rounded-lg p-2.5 break-all leading-relaxed text-[9px]"
            style={{ background: C.bg, color: 'rgba(74,222,128,0.75)' }}
          >
            {url}
          </div>
          <div style={{ color: '#555' }}>
            scanner: <span style={{ color: '#888' }}>{scanner}</span>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── PLAN SECTION ──────────────────────────────────────────────────────────────

function PlanSection({ items, onToggle }) {
  return (
    <div
      className="rounded-xl p-3"
      style={{ background: C.panel, border: `1px solid ${C.border}` }}
    >
      <div className="flex items-center gap-2 mb-3">
        <Hash size={11} style={{ color: C.textDim }} />
        <span className="font-mono text-[10px] uppercase tracking-widest" style={{ color: '#666' }}>
          PLANO:
        </span>
        <span className="font-mono text-[9px] ml-auto" style={{ color: '#3a3a3a' }}>
          {items.filter(i => i.checked).length}/{items.length}
        </span>
      </div>

      <div className="space-y-2">
        {items.map(item => (
          <label
            key={item.id}
            onClick={() => onToggle(item.id)}
            className="flex items-start gap-2.5 cursor-pointer group"
          >
            <div className="flex-shrink-0 mt-[1px]">
              {item.checked ? (
                <CheckSquare size={12} style={{ color: C.red }} />
              ) : (
                <Square size={12} style={{ color: '#444' }} className="group-hover:!text-[#888] transition-colors" />
              )}
            </div>
            <span
              className="font-mono text-[10px] leading-relaxed transition-all"
              style={{
                color:          item.checked ? '#3a3a3a' : '#8a8a8a',
                textDecoration: item.checked ? 'line-through' : 'none',
              }}
            >
              {item.text}
            </span>
          </label>
        ))}
      </div>
    </div>
  );
}

// ─── CHAT AREA ─────────────────────────────────────────────────────────────────

function ToolCallMessage({ msg }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex justify-start entry-in">
      <div className="max-w-[92%] rounded-lg font-mono" style={{ background: '#0c130c', border: '1px solid #1a2e1a', fontSize: 9 }}>
        <button
          onClick={() => setOpen(o => !o)}
          className="flex items-center gap-1.5 px-3 py-1.5 w-full text-left"
          style={{ color: '#3ecf8e' }}
        >
          <Zap size={8} style={{ flexShrink: 0 }} />
          <span className="font-bold">{msg.name}</span>
          <span style={{ color: '#2a4a2a' }}>·</span>
          <span style={{ color: '#2a4a2a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 220 }}>
            {JSON.stringify(msg.args)}
          </span>
          <span style={{ marginLeft: 'auto', color: '#2a4a2a' }}>{open ? '▲' : '▼'}</span>
        </button>
        {open && (
          <pre style={{ color: '#3a5a3a', whiteSpace: 'pre-wrap', margin: 0, padding: '4px 12px 8px', maxHeight: 200, overflow: 'auto', fontSize: 8, borderTop: '1px solid #1a2e1a' }}>
            {msg.output}
          </pre>
        )}
      </div>
    </div>
  );
}

function ChatMessage({ msg }) {
  const isUser = msg.role === 'user';

  if (msg.role === 'tool_call') return <ToolCallMessage msg={msg} />;

  return (
    <div className={`flex entry-in ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className="max-w-[88%] rounded-xl px-3 py-2.5 font-mono text-[10px] leading-relaxed"
        style={
          isUser
            ? { background: C.redDim, border: `1px solid ${C.redBorder}`, color: '#d4d4d4' }
            : { background: C.panel,  border: `1px solid ${C.border}`,    color: '#7a7a7a' }
        }
      >
        {msg.loading ? (
          <span className="flex items-center gap-1.5" style={{ color: '#555' }}>
            <Loader2 size={10} className="animate-spin" />
            processando...
          </span>
        ) : (
          msg.text
        )}
      </div>
    </div>
  );
}

// ─── DASHBOARD VIEW ────────────────────────────────────────────────────────────

function DashboardView({ logs, findings, targets }) {
  const errCount  = logs.filter(l => l.status === 'error').length;
  const okCount   = logs.filter(l => l.status === 'success').length;
  const critCount = findings.filter(f => /critical|sqli|rce/i.test(f.type || '')).length;

  const stats = [
    { label: 'TOOLS EXECUTADAS',  value: logs.length,     color: '#aaa',   sub: logs.length === 0 ? 'sem actividade' : 'total de chamadas' },
    { label: 'CRITICAL FINDINGS', value: critCount,       color: C.red,    sub: critCount === 0 ? 'nenhum crítico' : `${findings.length} findings totais` },
    { label: 'ERROS',             value: errCount,        color: C.orange, sub: `${okCount} com sucesso` },
    { label: 'ALVOS ATIVOS',      value: targets.length,  color: C.green,  sub: targets.length === 1 ? 'em execução' : 'em execução' },
  ];

  const sevOf = (type) => /critical|rce/i.test(type) ? 'CRITICAL'
                       : /sqli|injection/i.test(type) ? 'CRITICAL'
                       : /cors|xss|auth/i.test(type) ? 'HIGH'
                       : /clickjack|csrf/i.test(type) ? 'MEDIUM'
                       : 'INFO';

  const sevColor = { CRITICAL: C.red, HIGH: C.orange, MEDIUM: '#eab308', INFO: '#6b7280' };

  // Top tools: count occurrences in logs, sort desc
  const toolCounts = logs.reduce((acc, l) => { acc[l.tool] = (acc[l.tool] || 0) + 1; return acc; }, {});
  const topTools   = Object.entries(toolCounts).sort((a, b) => b[1] - a[1]).slice(0, 5);
  const maxCount   = topTools[0]?.[1] || 1;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        {stats.map((s, i) => (
          <div key={i} className="rounded-xl p-3" style={{ background: C.panel, border: `1px solid ${C.border}` }}>
            <div className="font-mono text-[9px] uppercase tracking-widest mb-2" style={{ color: C.textDim }}>{s.label}</div>
            <div className="font-mono text-2xl font-bold mb-1" style={{ color: s.color }}>{s.value}</div>
            <div className="font-mono text-[9px]" style={{ color: '#3a3a3a' }}>{s.sub}</div>
          </div>
        ))}
      </div>

      <div className="rounded-xl overflow-hidden" style={{ background: C.panel, border: `1px solid ${C.border}` }}>
        <div className="px-3 py-2" style={{ borderBottom: `1px solid ${C.border}` }}>
          <span className="font-mono text-[9px] uppercase tracking-widest" style={{ color: C.textDim }}>FINDINGS RECENTES</span>
        </div>
        {findings.length === 0 ? (
          <div className="px-3 py-6 font-mono text-[10px] text-center" style={{ color: '#333' }}>
            sem findings registados — inicie um scan em Pentest
          </div>
        ) : findings.slice(0, 5).map((f, i, arr) => {
          const sev = sevOf(f.type);
          return (
            <div
              key={f.id ?? i}
              className="flex items-center gap-2.5 px-3 py-2 hover:bg-[#1a1a1a] transition-colors"
              style={{ borderBottom: i < arr.length - 1 ? `1px solid ${C.border}` : 'none' }}
            >
              <span
                className="font-mono text-[9px] px-1.5 py-0.5 rounded flex-shrink-0"
                style={{ color: sevColor[sev], background: `${sevColor[sev]}18`, border: `1px solid ${sevColor[sev]}28` }}
              >
                {sev}
              </span>
              <span className="font-mono text-[10px] flex-1 truncate" style={{ color: '#777' }}>{f.type}</span>
              <span className="font-mono text-[9px] flex-shrink-0" style={{ color: '#3a3a3a' }}>{f.scanner}</span>
            </div>
          );
        })}
      </div>

      <div className="rounded-xl p-3" style={{ background: C.panel, border: `1px solid ${C.border}` }}>
        <div className="font-mono text-[9px] uppercase tracking-widest mb-3" style={{ color: C.textDim }}>TOP TOOLS</div>
        {topTools.length === 0 ? (
          <div className="py-3 font-mono text-[10px] text-center" style={{ color: '#333' }}>
            sem execuções registadas
          </div>
        ) : topTools.map(([tool, count]) => {
          const pct = (count / maxCount) * 100;
          return (
            <div key={tool} className="mb-2.5 last:mb-0">
              <div className="flex justify-between mb-1">
                <span className="font-mono text-[9px]" style={{ color: '#555' }}>{tool}</span>
                <span className="font-mono text-[9px]" style={{ color: '#333' }}>{count}x</span>
              </div>
              <div className="h-px rounded-full" style={{ background: '#1e1e1e' }}>
                <div className="h-full rounded-full" style={{ width: `${pct}%`, background: C.red, transition: 'width 0.5s' }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── PENTEST VIEW ───────────────────────────────────────────────────────────────

const TOOL_BINS = {
  subfinder: 'subfinder', httpx: 'httpx', ghauri: 'ghauri', ffuf: 'ffuf',
  aquatone: 'aquatone',  burp_suite: 'bash', naabu_scan: 'nmap',
  katana_crawl: 'curl',  nuclei_fast: 'nuclei',   sqli_scan: 'sqlmap',
  xss_check: 'nuclei',   cors_check: 'nuclei',    js_analyze: 'whatweb',
  dir_fuzz: 'gobuster',  ssrf_check: 'nuclei',    lfi_test: 'nuclei',
};

function PentestView({ apiKey, mcpUrl, mcpTools }) {
  const [target,     setTarget]     = useState('https://target-01.com');
  const [running,    setRunning]    = useState(false);
  const [log,        setLog]        = useState([]);
  const [toolStatus, setToolStatus] = useState({});
  const [tools,   setTools]   = useState({
    subfinder:    true,
    httpx:        true,
    ghauri:       true,
    ffuf:         true,
    aquatone:     false,
    burp_suite:   false,
    naabu_scan:   false,
    katana_crawl: false,
    nuclei_fast:  true,
    sqli_scan:    false,
    xss_check:    false,
    cors_check:   false,
    js_analyze:   false,
    dir_fuzz:     false,
    ssrf_check:   false,
    lfi_test:     false,
  });
  const PRIMARY   = ['subfinder','httpx','ghauri','ffuf','aquatone','burp_suite'];
  const SECONDARY = ['naabu_scan','katana_crawl','nuclei_fast','sqli_scan','xss_check','cors_check','js_analyze','dir_fuzz','ssrf_check','lfi_test'];
  const logRef = useRef(null);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [log]);

  const toggle      = (t) => setTools(prev => ({ ...prev, [t]: !prev[t] }));
  const activeCount = Object.values(tools).filter(Boolean).length;

  useEffect(() => {
    if (!mcpUrl) return;
    const checked = {};
    const pairs = Object.entries(TOOL_BINS);
    const unique = [...new Set(pairs.map(([,b]) => b))];
    Promise.all(unique.map(async bin => {
      try {
        const r  = await fetch(`${mcpUrl}/call/shell`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ command: `which ${bin} 2>/dev/null && echo __OK__ || echo __MISS__` }) });
        const d  = await r.json();
        const ok = (d.output || '').includes('__OK__');
        pairs.filter(([,b]) => b === bin).forEach(([k]) => { checked[k] = ok; });
      } catch { pairs.filter(([,b]) => b === bin).forEach(([k]) => { checked[k] = false; }); }
    })).then(() => setToolStatus({ ...checked }));
  }, [mcpUrl]);

  const TOOL_MAP = {
    subfinder:    { tool: 'subfinder',   args: (t) => ({ domain: t, flags: '-silent' }) },
    httpx:        { tool: 'httpx',       args: (t) => ({ target: t, flags: '-status-code -title -tech-detect' }) },
    ghauri:       { tool: 'ghauri',      args: (t) => ({ url: t, flags: '--dbs --batch' }) },
    ffuf:         { tool: 'ffuf',        args: (t) => ({ url: `${t}/FUZZ`, wordlist: '/usr/share/seclists/Discovery/Web-Content/common.txt', flags: '-mc 200,301,302,403' }) },
    aquatone:     { tool: 'aquatone',    args: (t) => ({ target: t }) },
    burp_suite:   { tool: 'shell',       args: (_t) => ({ command: 'nohup burpsuite &>/dev/null &' }) },
    naabu_scan:   { tool: 'nmap',        args: (t) => ({ target: t, flags: '-sV -sC -p- --min-rate 5000' }) },
    katana_crawl: { tool: 'curl',        args: (t) => ({ url: t, flags: '-L -I' }) },
    nuclei_fast:  { tool: 'nuclei',      args: (t) => ({ target: t, templates: 'cves,misconfig,exposure', severity: 'critical,high,medium' }) },
    sqli_scan:    { tool: 'sqlmap',      args: (t) => ({ url: t, flags: '--batch --dbs --level=2' }) },
    xss_check:    { tool: 'nuclei',      args: (t) => ({ target: t, templates: 'xss', severity: 'high,medium' }) },
    cors_check:   { tool: 'nuclei',      args: (t) => ({ target: t, templates: 'misconfig', severity: 'high,medium,low' }) },
    js_analyze:   { tool: 'whatweb',     args: (t) => ({ target: t, flags: '-a 3' }) },
    dir_fuzz:     { tool: 'gobuster',    args: (t) => ({ target: t }) },
    ssrf_check:   { tool: 'nuclei',      args: (t) => ({ target: t, templates: 'ssrf', severity: 'critical,high' }) },
    lfi_test:     { tool: 'nuclei',      args: (t) => ({ target: t, templates: 'lfi', severity: 'critical,high,medium' }) },
  };

  const runPentest = async () => {
    if (!apiKey) { setLog([{ t: 'err', m: 'API Key Anthropic não configurada nas Settings.' }]); return; }
    if (!mcpUrl)  { setLog([{ t: 'err', m: 'Kali MCP Server não configurado nas Settings.' }]); return; }
    setRunning(true);
    setLog([{ t: 'info', m: `▶ Iniciando pentest em ${target}` }]);

    const selected = Object.entries(tools).filter(([,on]) => on).map(([k]) => k);
    const results  = [];

    for (const toolKey of selected) {
      const map = TOOL_MAP[toolKey];
      if (!map) continue;
      setLog(prev => [...prev, { t: 'run', m: `  → ${toolKey} (${map.tool})...` }]);
      try {
        const r   = await fetch(`${mcpUrl}/call/${map.tool}`, {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify(map.args(target)),
        });
        const rd  = await r.json();
        const out = (rd.output || rd.error || '').slice(0, 2000);
        results.push(`## ${toolKey} (${map.tool})\n${out}`);
        setLog(prev => [...prev, { t: 'ok', m: `  ✓ ${toolKey} concluído` }]);
      } catch (e) {
        setLog(prev => [...prev, { t: 'err', m: `  ✗ ${toolKey}: ${e.message}` }]);
      }
    }

    setLog(prev => [...prev, { t: 'info', m: '  Analisando resultados com Claude...' }]);
    const prompt = `Analisa os resultados deste pentest ao alvo ${target} e cria um relatório com: vulnerabilidades encontradas, severidade, CVEs relevantes, e recomendações.\n\n${results.join('\n\n')}`;
    try {
      const res = await window.electron.callClaude({
        messages: [{ role: 'user', content: prompt }],
        apiKey,
        tools:  mcpTools.length > 0 ? mcpTools : undefined,
        mcpUrl: mcpTools.length > 0 ? mcpUrl   : undefined,
      });
      const txt = res.content?.find(b => b.type === 'text')?.text || 'Sem resposta.';
      setLog(prev => [...prev, { t: 'report', m: txt }]);
    } catch (e) {
      setLog(prev => [...prev, { t: 'err', m: `Claude: ${e.message}` }]);
    }
    setRunning(false);
  };

  const stop = () => setRunning(false);

  return (
    <div className="space-y-4">
      <div className="rounded-xl p-3" style={{ background: C.panel, border: `1px solid ${C.border}` }}>
        <div className="font-mono text-[9px] uppercase tracking-widest mb-2" style={{ color: C.textDim }}>ALVO</div>
        <input
          type="text"
          value={target}
          onChange={e => setTarget(e.target.value)}
          className="w-full rounded-lg px-3 py-2 font-mono text-xs outline-none transition-all"
          style={{ background: C.bg, border: `1px solid ${C.border}`, color: C.text, caretColor: C.red }}
          onFocus={e => (e.target.style.borderColor = C.red)}
          onBlur={e  => (e.target.style.borderColor = C.border)}
        />
      </div>

      <div className="rounded-xl p-3 space-y-3" style={{ background: C.panel, border: `1px solid ${C.border}` }}>
        <div className="flex items-center justify-between">
          <span className="font-mono text-[9px] uppercase tracking-widest" style={{ color: C.textDim }}>FERRAMENTAS</span>
          <span className="font-mono text-[9px]" style={{ color: '#3a3a3a' }}>{activeCount} ativas</span>
        </div>

        <div>
          <div className="font-mono text-[8px] uppercase tracking-widest mb-1.5" style={{ color: C.red, opacity: 0.6 }}>Principais</div>
          <div className="grid grid-cols-2 gap-1.5">
            {PRIMARY.map(tool => (
              <button
                key={tool}
                onClick={() => toggle(tool)}
                className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-left transition-all"
                style={{ background: tools[tool] ? C.redDim : 'transparent', border: `1px solid ${tools[tool] ? C.redBorder : C.border}` }}
              >
                <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: tools[tool] ? C.red : '#333' }} />
                <span className="font-mono text-[9px] truncate flex-1" style={{ color: tools[tool] ? '#bbb' : '#444' }}>{tool.replace(/_/g, ' ')}</span>
                {toolStatus[tool] === true  && <span style={{ color: '#22c55e', fontSize: 9 }}>✓</span>}
                {toolStatus[tool] === false && <span style={{ color: '#ef4444', fontSize: 9 }}>✗</span>}
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="font-mono text-[8px] uppercase tracking-widest mb-1.5" style={{ color: C.textDim, opacity: 0.5 }}>Secundárias</div>
          <div className="grid grid-cols-2 gap-1.5">
            {SECONDARY.map(tool => (
              <button
                key={tool}
                onClick={() => toggle(tool)}
                className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-left transition-all"
                style={{ background: tools[tool] ? 'rgba(255,255,255,0.04)' : 'transparent', border: `1px solid ${tools[tool] ? '#333' : C.border}` }}
              >
                <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: tools[tool] ? '#555' : '#222' }} />
                <span className="font-mono text-[9px] truncate flex-1" style={{ color: tools[tool] ? '#666' : '#333' }}>{tool.replace(/_/g, ' ')}</span>
                {toolStatus[tool] === true  && <span style={{ color: '#22c55e', fontSize: 9 }}>✓</span>}
                {toolStatus[tool] === false && <span style={{ color: '#ef4444', fontSize: 9 }}>✗</span>}
              </button>
            ))}
          </div>
        </div>
      </div>

      <button
        onClick={running ? stop : runPentest}
        className="w-full py-3 rounded-xl font-mono text-xs font-semibold tracking-widest uppercase transition-all"
        style={running
          ? { background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)', color: '#ef4444' }
          : { background: C.redDim, border: `1px solid ${C.redBorder}`, color: C.red }
        }
      >
        {running ? '■  PARAR SCAN' : '▶  INICIAR PENTEST'}
      </button>

      {log.length > 0 && (
        <div
          ref={logRef}
          className="rounded-xl p-3 font-mono overflow-y-auto"
          style={{ background: '#050505', border: `1px solid ${C.border}`, maxHeight: 320, fontSize: 10 }}
        >
          {log.map((l, i) => (
            <div key={i} className="mb-1" style={{
              color: l.t === 'err' ? C.red : l.t === 'ok' ? '#22c55e' : l.t === 'report' ? '#aaa' : l.t === 'run' ? C.orange : '#555'
            }}>
              <pre className="whitespace-pre-wrap">{l.m}</pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── TERMINALS VIEW ─────────────────────────────────────────────────────────────

const TERM_INIT = [
  { type: 'out', text: 'manucaspt terminal v1.0.0 — pentest automation shell\n─────────────────────────────────────────────────' },
];

function TerminalsView({ mcpUrl }) {
  const [input,   setInput]   = useState('');
  const [history, setHistory] = useState(TERM_INIT);
  const [cmdHist, setCmdHist] = useState([]);
  const [histIdx, setHistIdx] = useState(-1);
  const [mode,    setMode]    = useState('windows');
  const scrollRef = useRef(null);
  const inputRef  = useRef(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [history]);

  const submit = async () => {
    if (!input.trim()) return;
    const cmd = input.trim();
    setHistory(prev => [...prev, { type: 'cmd', text: cmd, mode }]);
    setCmdHist(prev => [cmd, ...prev]);
    setHistIdx(-1);
    setInput('');
    if (mode === 'kali') {
      if (!mcpUrl) {
        setHistory(prev => [...prev, { type: 'out', text: '[ERRO] Kali MCP Server não configurado nas Settings.' }]);
        return;
      }
      try {
        const r   = await fetch(`${mcpUrl}/call/shell`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ command: cmd }) });
        const rd  = await r.json();
        setHistory(prev => [...prev, { type: 'out', text: rd.output || rd.error || '(sem saída)' }]);
      } catch (e) {
        setHistory(prev => [...prev, { type: 'out', text: `[ERRO] ${e.message}` }]);
      }
    } else if (window.electron) {
      const { stdout, stderr, error } = await window.electron.runTerminal(cmd);
      const out = stdout || stderr || error || '(sem saída)';
      setHistory(prev => [...prev, { type: 'out', text: out }]);
    } else {
      setHistory(prev => [...prev, { type: 'out', text: `[INFO] terminal real disponível apenas na app desktop.` }]);
    }
  };

  const onTermKey = (e) => {
    if (e.key === 'Enter') { e.preventDefault(); submit(); return; }
    if (e.key === 'ArrowUp') {
      const idx = Math.min(histIdx + 1, cmdHist.length - 1);
      setHistIdx(idx); setInput(cmdHist[idx] ?? '');
    }
    if (e.key === 'ArrowDown') {
      const idx = Math.max(histIdx - 1, -1);
      setHistIdx(idx); setInput(idx === -1 ? '' : cmdHist[idx]);
    }
  };

  return (
    <div
      className="flex flex-col flex-1 h-full overflow-hidden"
      style={{ background: '#0a0a0a' }}
      onClick={() => inputRef.current?.focus()}
    >
      <div
        className="px-3 py-2 flex-shrink-0 flex items-center justify-between"
        style={{ borderBottom: `1px solid ${C.border}` }}
      >
        <span className="font-mono text-[9px] uppercase tracking-widest" style={{ color: C.textDim }}>TERMINAL</span>
        <div className="flex items-center gap-1" style={{ background: '#111', borderRadius: 6, padding: '2px 3px', border: `1px solid ${C.border}` }}>
          <button onClick={() => { setMode('windows'); setHistory(TERM_INIT); }} className="font-mono text-[9px] px-2 py-0.5 rounded transition-all" style={{ background: mode === 'windows' ? C.panel : 'transparent', color: mode === 'windows' ? '#ccc' : '#444' }}>windows</button>
          <button onClick={() => { setMode('kali'); setHistory([{ type: 'out', text: 'kali terminal — comandos executam no servidor Kali via MCP\n─────────────────────────────────────────────────' }]); }} className="font-mono text-[9px] px-2 py-0.5 rounded transition-all" style={{ background: mode === 'kali' ? C.red : 'transparent', color: mode === 'kali' ? '#fff' : '#444' }}>kali</button>
        </div>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 font-mono leading-relaxed"
        style={{ fontSize: 11 }}
      >
        {history.map((line, i) => (
          <div key={i} className="mb-1.5">
            {line.type === 'cmd' ? (
              <div className="flex gap-2">
                <span style={{ color: C.red }}>❯</span>
                <span style={{ color: '#d4d4d4' }}>{line.text}</span>
              </div>
            ) : (
              <pre className="whitespace-pre-wrap pl-4" style={{ color: 'rgba(74,222,128,0.65)', fontSize: 10 }}>
                {line.text}
              </pre>
            )}
          </div>
        ))}
        <div className="flex gap-2 items-center">
          <span style={{ color: C.red }}>❯</span>
          <span style={{ color: '#d4d4d4' }}>{input}</span>
          <span className="cursor-blink" />
        </div>
      </div>

      <div
        className="flex items-center gap-2 px-4 py-2.5 flex-shrink-0"
        style={{ borderTop: `1px solid ${C.border}`, background: C.panel }}
      >
        <span className="font-mono text-xs" style={{ color: C.red }}>❯</span>
        <input
          ref={inputRef}
          autoFocus
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={onTermKey}
          placeholder="comando..."
          className="flex-1 bg-transparent outline-none font-mono text-xs"
          style={{ color: '#d4d4d4', caretColor: C.red }}
        />
      </div>
    </div>
  );
}

// ─── MAIN INTERACTION PANEL ────────────────────────────────────────────────────

function InteractionPanel({ planItems, onPlanToggle, messages, onSend, apiKey, groqKey, activeNav, activeTarget, activeConv, convs, targets, logs, activeModel, onModelChange, onSplit, isSplit, onCloseSplit, supaUrl, syncStatus, mcpTools, toolProgress, mcpUrl }) {
  const [input, setInput]         = useState('');
  const [tab, setTab]             = useState('findings');
  const [attachment, setAttachment] = useState(null);
  const chatRef                   = useRef(null);
  const inputRef                  = useRef(null);
  const fileRef                   = useRef(null);

  const onFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => setAttachment({ name: file.name, content: ev.target.result, size: file.size });
    reader.onerror = () => setAttachment({ name: file.name, content: null, size: file.size });
    if (file.size > 500_000) {
      setAttachment({ name: file.name, content: `[arquivo muito grande: ${(file.size/1024).toFixed(0)}KB]`, size: file.size });
    } else {
      reader.readAsText(file);
    }
    e.target.value = '';
  };

  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [messages]);

  useEffect(() => { setTab('chat');     }, [activeConv]);
  useEffect(() => { setTab('findings'); }, [activeTarget]);
  const send = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed && !attachment) return;
    const fullText = attachment
      ? `${trimmed ? trimmed + '\n\n' : ''}[arquivo: ${attachment.name}]\n\`\`\`\n${attachment.content ?? ''}\n\`\`\``
      : trimmed;
    onSend(fullText);
    setInput('');
    setAttachment(null);
    inputRef.current?.focus();
  }, [input, attachment, onSend]);

  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  };

  if (activeNav === 'terminals') return <TerminalsView mcpUrl={mcpUrl} />;

  const modelInfo = activeModel === 'gemma'
    ? { label: 'Gemma 9B · Groq', dot: '#22c55e' }
    : { label: 'Sonnet 4.5 · Anthropic', dot: '#ff3333' };
  const headerTitle = { dashboard: 'Dashboard', pentest: 'Pentest Config' };

  const tabs = [
    { id: 'findings', label: 'FINDINGS' },
    { id: 'plano',    label: 'PLANO'    },
    { id: 'chat',     label: 'CHAT'     },
  ];

  return (
    <section className="flex flex-col flex-1 h-full overflow-hidden" style={{ background: C.bg }}>
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-2.5 flex-shrink-0"
        style={{ borderBottom: `1px solid ${C.border}` }}
      >
        <div className="flex items-center gap-3">
          {activeNav === 'chat' ? (
            <button
              onClick={() => onModelChange(activeModel === 'gemma' ? 'claude' : 'gemma')}
              className="flex items-center gap-1.5 font-mono text-[10px] tracking-wider px-2 py-1 rounded transition-colors"
              style={{ color: '#888', background: '#141414', border: '1px solid #222' }}
              title="Alternar modelo"
              onMouseEnter={e => e.currentTarget.style.borderColor = '#333'}
              onMouseLeave={e => e.currentTarget.style.borderColor = '#222'}
            >
              <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: modelInfo.dot }} />
              {modelInfo.label}
            </button>
          ) : (
            <span className="font-mono text-[10px] tracking-wider" style={{ color: '#555' }}>
              {headerTitle[activeNav]}
            </span>
          )}
          {activeNav === 'chat' && (() => {
            const target = targets.find(t => t.id === activeTarget);
            const conv   = convs.find(c => c.id === activeConv);
            const count  = (TARGET_FINDINGS[activeTarget] || []).length;
            return (
              <div className="flex items-center gap-1.5">
                {target && (
                  <span
                    className="font-mono text-[9px] px-2 py-0.5 rounded flex items-center gap-1.5"
                    style={{ background: '#1a1a1a', color: '#555', border: `1px solid #222` }}
                  >
                    <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: C.red }} />
                    {target.name}
                  </span>
                )}
                {conv && (
                  <span
                    className="font-mono text-[9px] px-2 py-0.5 rounded"
                    style={{ background: C.redDim, color: '#555', border: `1px solid ${C.redBorder}` }}
                  >
                    {conv.label}
                  </span>
                )}
                {count > 0 && (
                  <span className="font-mono text-[9px]" style={{ color: C.red }}>
                    {count} finding{count !== 1 ? 's' : ''}
                  </span>
                )}
              </div>
            );
          })()}
        </div>

        {activeNav === 'chat' && <div className="flex items-center gap-1">
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className="px-2.5 py-1 rounded font-mono text-[9px] uppercase tracking-wider transition-all"
              style={
                tab === t.id
                  ? { background: C.redDim, border: `1px solid ${C.redBorder}`, color: C.red }
                  : { background: 'transparent', border: '1px solid transparent', color: '#444' }
              }
              onMouseEnter={e => { if (tab !== t.id) e.currentTarget.style.color = '#888'; }}
              onMouseLeave={e => { if (tab !== t.id) e.currentTarget.style.color = '#444'; }}
            >
              {t.label}
            </button>
          ))}
          <div style={{ width: 1, height: 12, background: '#222', margin: '0 4px' }} />
          {!isSplit && onSplit && (
            <button
              onClick={onSplit}
              title="Abrir painel paralelo"
              className="flex items-center justify-center w-6 h-5 rounded transition-colors"
              style={{ color: '#333', border: '1px solid #222', background: 'transparent' }}
              onMouseEnter={e => { e.currentTarget.style.color = '#666'; e.currentTarget.style.borderColor = '#333'; }}
              onMouseLeave={e => { e.currentTarget.style.color = '#333'; e.currentTarget.style.borderColor = '#222'; }}
            >
              <Columns2 size={10} />
            </button>
          )}
          {isSplit && (
            <button
              onClick={onCloseSplit}
              title="Fechar painel paralelo"
              className="flex items-center justify-center w-6 h-5 rounded transition-colors"
              style={{ color: '#555', border: `1px solid ${C.redBorder}`, background: C.redDim }}
              onMouseEnter={e => { e.currentTarget.style.color = C.red; }}
              onMouseLeave={e => { e.currentTarget.style.color = '#555'; }}
            >
              <X size={10} />
            </button>
          )}
        </div>}
      </div>

      {/* Scrollable content */}
      <div ref={chatRef} className="flex-1 overflow-y-auto p-4 space-y-4">

        {activeNav === 'dashboard' && <DashboardView logs={logs} findings={TARGET_FINDINGS[activeTarget] || []} targets={targets} />}
        {activeNav === 'pentest'   && <PentestView apiKey={apiKey} mcpUrl={mcpUrl} mcpTools={mcpTools} />}

        {/* Findings tab */}
        {activeNav === 'chat' && (tab === 'findings' || tab === 'plano') && (
          <>
            {tab === 'findings' && (
              <>
                {(TARGET_FINDINGS[activeTarget] || []).length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-16 gap-3">
                    <Shield size={22} style={{ color: '#2a2a2a' }} />
                    <p className="font-mono text-[10px] text-center" style={{ color: '#333' }}>
                      nenhum finding · inicie um scan em Pentest
                    </p>
                  </div>
                ) : (
                  (TARGET_FINDINGS[activeTarget] || []).map(f => (
                    <FindingCard key={f.id} type={f.type} cve={f.cve} url={f.url} scanner={f.scanner} />
                  ))
                )}
              </>
            )}

            <PlanSection items={planItems} onToggle={onPlanToggle} />
          </>
        )}

        {/* Chat tab */}
        {activeNav === 'chat' && tab === 'chat' && (
          <div className="space-y-3">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center py-12 gap-3">
                <Lock size={22} style={{ color: '#2a2a2a' }} />
                <p className="font-mono text-[10px] text-center" style={{ color: '#333' }}>
                  nenhuma mensagem ainda.<br />
                  {apiKey ? 'API Key configurada — pronto.' : 'configura a API Key para respostas reais.'}
                </p>
              </div>
            )}
            {messages.map((m, i) => <ChatMessage key={i} msg={m} />)}
          </div>
        )}
      </div>

      {/* Chat input */}
      {activeNav === 'chat' && <div className="flex-shrink-0 p-3" style={{ borderTop: `1px solid ${C.border}` }}>
        {!(activeModel === 'gemma' ? groqKey : apiKey) && (
          <div
            className="flex items-center gap-1.5 font-mono mb-2"
            style={{ fontSize: 9, color: 'rgba(255,51,51,0.45)' }}
          >
            <AlertCircle size={9} />
            API Key não configurada — respostas simuladas ativas.
          </div>
        )}
        {attachment && (
          <div className="flex items-center gap-1.5 mb-1.5 px-1">
            <div
              className="flex items-center gap-1.5 px-2 py-1 rounded-lg font-mono"
              style={{ fontSize: 9, background: '#1a1a1a', border: '1px solid #252525', color: '#555' }}
            >
              <Paperclip size={8} style={{ color: C.red }} />
              <span style={{ color: '#777' }}>{attachment.name}</span>
              <span style={{ color: '#333' }}>· {(attachment.size / 1024).toFixed(0)}KB</span>
              <button
                onClick={() => setAttachment(null)}
                className="ml-1 transition-colors"
                style={{ color: '#333' }}
                onMouseEnter={e => e.currentTarget.style.color = '#ff3333'}
                onMouseLeave={e => e.currentTarget.style.color = '#333'}
              >
                <X size={8} />
              </button>
            </div>
          </div>
        )}
        <input ref={fileRef} type="file" className="hidden" onChange={onFileChange} />
        <div
          className="flex items-center gap-2 rounded-xl px-3.5 py-2.5 transition-all"
          style={{ background: C.panel, border: `1px solid ${C.border}` }}
          onFocusCapture={e => (e.currentTarget.style.borderColor = 'rgba(255,51,51,0.3)')}
          onBlurCapture={e  => (e.currentTarget.style.borderColor = C.border)}
        >
          <button
            onClick={() => fileRef.current?.click()}
            className="flex-shrink-0 transition-colors"
            title="Anexar arquivo"
            style={{ color: attachment ? C.red : '#2e2e2e' }}
            onMouseEnter={e => e.currentTarget.style.color = '#555'}
            onMouseLeave={e => e.currentTarget.style.color = attachment ? C.red : '#2e2e2e'}
          >
            <Paperclip size={12} />
          </button>
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={onKey}
            placeholder="Pergunte algo..."
            className="flex-1 bg-transparent outline-none font-mono text-xs"
            style={{ color: C.text, caretColor: C.red }}
          />
          <button
            onClick={send}
            disabled={!input.trim() && !attachment}
            className="flex items-center justify-center w-6 h-6 rounded-lg transition-all flex-shrink-0"
            style={{ background: (input.trim() || attachment) ? C.red : '#1e1e1e', color: (input.trim() || attachment) ? '#fff' : '#333' }}
          >
            <ArrowUp size={11} />
          </button>
        </div>

        <div className="flex items-center justify-between mt-2 px-1">
          <div className="flex items-center gap-1.5 font-mono" style={{ fontSize: 9, color: '#383838' }}>
            <span className="inline-block w-1 h-1 rounded-full" style={{ background: activeModel === 'gemma' ? '#22c55e' : C.red }} />
            {activeModel === 'gemma' ? 'gemma2-9b · groq' : 'claude-sonnet-4-5 · anthropic'}
            <span style={{ color: '#2a2a2a' }}>·</span>
            <span style={{ color: '#2a2a2a' }}>ready</span>
            {supaUrl && (
              <>
                <span style={{ color: '#1e1e1e' }}>·</span>
                <span style={{
                  color: syncStatus === 'synced' ? '#3ecf8e' : syncStatus === 'error' ? C.red : '#555'
                }}>
                  {syncStatus === 'synced' ? '☁ synced' : syncStatus === 'error' ? '⊗ sync err' : '↻ syncing'}
                </span>
              </>
            )}
            {mcpTools.length > 0 && (
              <>
                <span style={{ color: '#1e1e1e' }}>·</span>
                <span style={{ color: C.orange }}>⚡ {mcpTools.length} tools</span>
              </>
            )}
            {toolProgress && (
              <>
                <span style={{ color: '#1e1e1e' }}>·</span>
                <span style={{ color: '#555' }}>passo {toolProgress.step}</span>
                <span style={{ color: '#2a2a2a' }}>–</span>
                <span style={{ color: '#3a3a3a' }}>{toolProgress.msg}</span>
              </>
            )}
          </div>
          <div className="flex items-center gap-3 font-mono" style={{ fontSize: 9 }}>
            <button onClick={() => setTab('plano')} className="transition-colors hover:opacity-70" style={{ color: tab === 'plano' ? '#555' : '#2e2e2e' }}>
              plano {planItems.filter(p => !p.checked).length > 0 && <span style={{ color: C.red }}>·{planItems.filter(p => !p.checked).length}</span>}
            </button>
            <button onClick={() => setTab('findings')} className="transition-colors hover:opacity-70" style={{ color: tab === 'findings' ? '#555' : '#2e2e2e' }}>
              findings {(TARGET_FINDINGS[activeTarget]||[]).length > 0 && <span style={{ color: C.orange }}>·{(TARGET_FINDINGS[activeTarget]||[]).length}</span>}
            </button>
            <span style={{ color: logs.length > 0 ? '#555' : '#2e2e2e' }}>
              atividade{logs.length > 0 && <span style={{ color: '#555' }}> ·{logs.length}</span>}
            </span>
          </div>
        </div>
      </div>}
    </section>
  );
}

// ─── ROOT APP ──────────────────────────────────────────────────────────────────

export default function App() {
  const [targets,      setTargets]      = useState(() => LS.get('manucas_targets',      TARGETS_DEFAULT));
  const [activeNav,    setActiveNav]    = useState('chat');
  const [activeTarget, setActiveTarget] = useState(() => LS.get('manucas_active_target', 1));
  const [convs,        setConvs]        = useState(() => LS.get('manucas_convs',         CONVERSATIONS));
  const [activeConv,   setActiveConv]   = useState(() => LS.get('manucas_active_conv',   1));
  const [targetLogs,   setTargetLogs]   = useState(() => LS.get('manucas_target_logs',   {}));
  const [targetPlans,  setTargetPlans]  = useState(() => LS.get('manucas_target_plans',  TARGET_PLAN));
  const [convMessages, setConvMessages] = useState(() => LS.get('manucas_conv_messages', {}));
  const [settingsOpen, setSettings]     = useState(false);
  const [apiKey,       setApiKey]       = useState(() => localStorage.getItem('manucas_api_key')  || '');
  const [groqKey,      setGroqKey]      = useState(() => localStorage.getItem('manucas_groq_key') || '');
  const [activeModel,  setActiveModel]  = useState(() => localStorage.getItem('manucas_model')    || 'claude');
  const [supaUrl,      setSupaUrl]      = useState(() => localStorage.getItem('manucas_supa_url') || 'https://ckwwhudzanicwqzxlhaj.supabase.co');
  const [supaKey,      setSupaKey]      = useState(() => localStorage.getItem('manucas_supa_key') || 'sb_publishable_KEYC_kTzaGr2bx67IvwekQ_-xmk58q5');
  const [syncStatus,   setSyncStatus]   = useState('idle');
  const [mcpUrl,       setMcpUrl]       = useState(() => localStorage.getItem('manucas_mcp_url') || '');
  const [mcpTools,     setMcpTools]     = useState([]);
  const [toolProgress, setToolProgress] = useState(null);
  const [updateInfo,      setUpdateInfo]      = useState(null);
  const [showUpdateModal, setShowUpdateModal] = useState(false);
  const [dlProgress,      setDlProgress]      = useState(null);
  const [dlDest,          setDlDest]          = useState(null);
  const logs     = targetLogs[activeTarget]   || [];
  const plan     = targetPlans[activeTarget]  || [];
  const messages = convMessages[activeConv]   || [];

  useEffect(() => { LS.set('manucas_targets',      targets);      }, [targets]);
  useEffect(() => { LS.set('manucas_active_target', activeTarget); }, [activeTarget]);
  useEffect(() => { LS.set('manucas_convs',         convs);        }, [convs]);
  useEffect(() => { LS.set('manucas_active_conv',   activeConv);   }, [activeConv]);
  useEffect(() => { LS.set('manucas_target_logs',   targetLogs);   }, [targetLogs]);
  useEffect(() => { LS.set('manucas_target_plans',  targetPlans);  }, [targetPlans]);
  useEffect(() => { LS.set('manucas_conv_messages', convMessages); }, [convMessages]);

  // ── MCP: listen for tool-use progress events ───────────────────────────────────
  useEffect(() => {
    const check = async () => {
      try {
        const res  = await fetch('https://api.github.com/repos/Bigraptor432/APP/releases/latest');
        const data = await res.json();
        const latest = (data.tag_name || '').replace(/^v/, '');
        const current = typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : '0.0.0';
        if (latest && latest !== current) {
          const dlUrl = data.assets?.find(a => a.name.endsWith('.exe'))?.browser_download_url || null;
          setUpdateInfo({ version: latest, url: data.html_url, downloadUrl: dlUrl });
          setShowUpdateModal(true);
        }
      } catch (_) {}
    };
    setTimeout(check, 3000);
  }, []);

  useEffect(() => {
    if (!window.electron?.onDownloadProgress) return;
    window.electron.onDownloadProgress(({ percent, done, dest }) => {
      setDlProgress(done ? 100 : percent);
      if (done && dest) setDlDest(dest);
    });
    return () => window.electron.offDownloadProgress?.();
  }, []);

  useEffect(() => {
    if (!window.electron) return;
    let clearTimer;
    window.electron.onToolProgress(({ step, msg }) => {
      setToolProgress({ step, msg });
      clearTimeout(clearTimer);
      clearTimer = setTimeout(() => setToolProgress(null), 4000);
    });
    return () => { window.electron.offToolProgress(); clearTimeout(clearTimer); };
  }, []);

  // ── MCP: fetch tools when URL changes ─────────────────────────────────────────
  useEffect(() => {
    if (!mcpUrl || !window.electron) { setMcpTools([]); return; }
    window.electron.mcpGetTools(mcpUrl)
      .then(d => setMcpTools(d?.tools || []))
      .catch(() => setMcpTools([]));
  }, [mcpUrl]);

  // ── Supabase: load from cloud on mount ────────────────────────────────────
  useEffect(() => {
    if (!supaUrl || !supaKey) return;
    const t = setTimeout(async () => {
      try {
        setSyncStatus('syncing');
        const data = await supaLoad(supaUrl, supaKey);
        const map = Object.fromEntries(data.map(r => [r.key, r.value]));
        if (map.manucas_convs)         setConvs(map.manucas_convs);
        if (map.manucas_conv_messages) setConvMessages(map.manucas_conv_messages);
        if (map.manucas_targets)       setTargets(map.manucas_targets);
        if (map.manucas_target_logs)   setTargetLogs(map.manucas_target_logs);
        if (map.manucas_target_plans)  setTargetPlans(map.manucas_target_plans);
        if (map.manucas_active_target) setActiveTarget(map.manucas_active_target);
        if (map.manucas_active_conv)   setActiveConv(map.manucas_active_conv);
        setSyncStatus('synced');
      } catch { setSyncStatus('error'); }
    }, 500);
    return () => clearTimeout(t);
  }, []);

  // ── Supabase: debounced cloud sync on every state change ──────────────────
  useEffect(() => {
    if (!supaUrl || !supaKey) return;
    const timer = setTimeout(async () => {
      try {
        setSyncStatus('syncing');
        await supaSave(supaUrl, supaKey, [
          { key: 'manucas_convs',         value: convs },
          { key: 'manucas_conv_messages', value: convMessages },
          { key: 'manucas_targets',       value: targets },
          { key: 'manucas_target_logs',   value: targetLogs },
          { key: 'manucas_target_plans',  value: targetPlans },
          { key: 'manucas_active_target', value: activeTarget },
          { key: 'manucas_active_conv',   value: activeConv },
          { key: 'manucas_api_key',       value: apiKey },
          { key: 'manucas_groq_key',      value: groqKey },
          { key: 'manucas_mcp_url',       value: mcpUrl },
        ]);
        setSyncStatus('synced');
      } catch { setSyncStatus('error'); }
    }, 2000);
    return () => clearTimeout(timer);
  }, [convs, convMessages, targets, targetLogs, targetPlans, activeTarget, activeConv, apiKey, groqKey, mcpUrl]);

  // ── Supabase: polling every 10s for real-time sync between users ────────────
  useEffect(() => {
    if (!supaUrl || !supaKey) return;
    const apply = (set, remote) => set(prev => JSON.stringify(prev) !== JSON.stringify(remote) ? remote : prev);
    const poll = async () => {
      try {
        const data = await supaLoad(supaUrl, supaKey);
        const map  = Object.fromEntries(data.map(r => [r.key, r.value]));
        if (map.manucas_convs         != null) apply(setConvs,        map.manucas_convs);
        if (map.manucas_conv_messages != null) apply(setConvMessages,  map.manucas_conv_messages);
        if (map.manucas_targets       != null) apply(setTargets,       map.manucas_targets);
        if (map.manucas_target_logs   != null) apply(setTargetLogs,    map.manucas_target_logs);
        if (map.manucas_target_plans  != null) apply(setTargetPlans,   map.manucas_target_plans);
        if (map.manucas_active_target != null) setActiveTarget(prev => prev !== map.manucas_active_target ? map.manucas_active_target : prev);
        if (map.manucas_active_conv   != null) setActiveConv(prev   => prev !== map.manucas_active_conv   ? map.manucas_active_conv   : prev);
        if (map.manucas_api_key  != null) setApiKey(prev  => prev !== map.manucas_api_key  ? map.manucas_api_key  : prev);
        if (map.manucas_groq_key != null) setGroqKey(prev => prev !== map.manucas_groq_key ? map.manucas_groq_key : prev);
        if (map.manucas_mcp_url  != null) setMcpUrl(prev  => prev !== map.manucas_mcp_url  ? map.manucas_mcp_url  : prev);
        setSyncStatus('synced');
      } catch { setSyncStatus('error'); }
    };
    const interval = setInterval(poll, 10000);
    return () => clearInterval(interval);
  }, [supaUrl, supaKey]);

  const togglePlan = useCallback((itemId) => {
    setTargetPlans(prev => ({
      ...prev,
      [activeTarget]: prev[activeTarget].map(i => i.id === itemId ? { ...i, checked: !i.checked } : i),
    }));
  }, [activeTarget]);

  const saveKeys = useCallback(({ anthropic, groq, supaUrl: su, supaKey: sk, mcpUrl: mu }) => {
    setApiKey(anthropic);
    setGroqKey(groq);
    setSupaUrl(su);
    setSupaKey(sk);
    setMcpUrl(mu);
    if (anthropic) localStorage.setItem('manucas_api_key',  anthropic); else localStorage.removeItem('manucas_api_key');
    if (groq)      localStorage.setItem('manucas_groq_key', groq);      else localStorage.removeItem('manucas_groq_key');
    if (su)        localStorage.setItem('manucas_supa_url', su);        else localStorage.removeItem('manucas_supa_url');
    if (sk)        localStorage.setItem('manucas_supa_key', sk);        else localStorage.removeItem('manucas_supa_key');
    if (mu)        localStorage.setItem('manucas_mcp_url',  mu);        else localStorage.removeItem('manucas_mcp_url');
  }, []);

  const changeModel = useCallback((m) => {
    setActiveModel(m);
    localStorage.setItem('manucas_model', m);
  }, []);

  const sendMessage = useCallback(async (text, convIdOverride) => {
    const convId  = convIdOverride ?? activeConv;
    const history = (convMessages[convId] || [])
      .filter(m => !m.loading && m.text && m.role !== 'tool_call')
      .map(m => ({ role: m.role, content: m.text }));
    history.push({ role: 'user', content: text });

    setConvMessages(prev => ({
      ...prev,
      [convId]: [...(prev[convId] || []), { role: 'user', text }, { role: 'assistant', text: '', loading: true }],
    }));

    if (!window.electron) {
      setTimeout(() => setConvMessages(prev => {
        const msgs = [...(prev[convId] || [])];
        msgs[msgs.length - 1] = { role: 'assistant', text: 'Abre a app desktop para respostas reais.', loading: false };
        return { ...prev, [convId]: msgs };
      }), 300);
      return;
    }

    const useGemma = activeModel === 'gemma';
    const key      = useGemma ? groqKey : apiKey;
    if (!key) {
      setConvMessages(prev => {
        const msgs = [...(prev[convId] || [])];
        msgs[msgs.length - 1] = { role: 'assistant', text: `Configure a ${useGemma ? 'Groq' : 'Anthropic'} API Key (⚙).`, loading: false };
        return { ...prev, [convId]: msgs };
      });
      return;
    }

    try {
      const hasTools = !useGemma && mcpTools.length > 0;
      const res = useGemma
        ? await window.electron.callGemma({ messages: history, apiKey: key })
        : await window.electron.callClaude({ messages: history, apiKey: key, tools: hasTools ? mcpTools : undefined, mcpUrl: hasTools ? mcpUrl : undefined });

      const replyText = useGemma
        ? (res.choices?.[0]?.message?.content || res.error?.message || res.error || 'Resposta vazia.')
        : (res.content?.find(b => b.type === 'text')?.text || res.error || 'Resposta vazia.');

      const toolMsgs = (res.toolCalls || []).map(tc => ({
        role: 'tool_call', name: tc.tool, args: tc.args, output: tc.output
      }));

      setConvMessages(prev => {
        const msgs = [...(prev[convId] || [])];
        const base = msgs.slice(0, -1);
        return { ...prev, [convId]: [...base, ...toolMsgs, { role: 'assistant', text: replyText, loading: false }] };
      });
    } catch (e) {
      setConvMessages(prev => {
        const msgs = [...(prev[convId] || [])];
        msgs[msgs.length - 1] = { role: 'assistant', text: `Erro: ${e.message}`, loading: false };
        return { ...prev, [convId]: msgs };
      });
    }
  }, [activeConv, apiKey, groqKey, activeModel, convMessages, mcpTools, mcpUrl]);

  const [splitConv, setSplitConv] = useState(null);

  const openSplit = useCallback(() => {
    const other = convs.find(c => c.id !== activeConv);
    if (other) {
      setSplitConv(other.id);
    } else {
      const id = Date.now();
      setConvs(prev => [...prev, { id, label: `sessão · ${prev.length + 1}` }]);
      setSplitConv(id);
    }
  }, [convs, activeConv]);

  const closeSplit = useCallback(() => setSplitConv(null), []);

  const addConv = useCallback(() => {
    const id = Date.now();
    setConvs(prev => [...prev, { id, label: `sessão · ${prev.length + 1}` }]);
    setActiveConv(id);
    setActiveNav('chat');
  }, []);

  const handleConvChange = useCallback((id) => {
    setActiveConv(id);
    setActiveNav('chat');
  }, []);

  const deleteConv = useCallback((id) => {
    let next = convs.filter(c => c.id !== id);
    if (next.length === 0) {
      const newId = Date.now();
      next = [{ id: newId, label: 'sessão · 1' }];
      setActiveConv(newId);
    } else if (id === activeConv) {
      setActiveConv(next[next.length - 1].id);
    }
    setConvs(next);
    setConvMessages(prev => { const n = { ...prev }; delete n[id]; return n; });
  }, [convs, activeConv]);

  const addTarget = useCallback(() => {
    const id   = Date.now();
    const num  = targets.length + 1;
    const name = `target-0${num}.com`;
    setTargets(prev => [...prev, { id, name }]);
    setTargetLogs(prev  => ({ ...prev,  [id]: [] }));
    setTargetPlans(prev => ({ ...prev,  [id]: [
      { id: 1, text: 'Registrar alvo e verificar scope',                         checked: false },
      { id: 2, text: 'Recon: DNS, portas, CDN/WAF, tech stack, headers',         checked: false },
      { id: 3, text: 'Enumerar endpoints, APIs, admin panels, JS files',         checked: false },
    ] }));
    setActiveTarget(id);
    setActiveNav('chat');
  }, [targets.length]);

  const handleTargetChange = useCallback((id) => {
    setActiveTarget(id);
    setActiveNav('chat');
  }, []);

  const deleteTarget = useCallback((id) => {
    const next = targets.filter(t => t.id !== id);
    if (next.length === 0) return;
    if (id === activeTarget) setActiveTarget(next[next.length - 1].id);
    setTargets(next);
    setTargetLogs(prev  => { const n = { ...prev }; delete n[id]; return n; });
    setTargetPlans(prev => { const n = { ...prev }; delete n[id]; return n; });
  }, [targets, activeTarget]);

  const renameTarget = useCallback((id, name) => {
    setTargets(prev => prev.map(t => t.id === id ? { ...t, name } : t));
  }, []);

  const renameConv = useCallback((id, label) => {
    setConvs(prev => prev.map(c => c.id === id ? { ...c, label } : c));
  }, []);

  const resetAll = useCallback(async () => {
    localStorage.clear();
    setTargets([]); setConvs([]); setConvMessages({}); setTargetLogs({}); setTargetPlans({});
    setActiveTarget(null); setActiveConv(null);
    if (supaUrl && supaKey) {
      try {
        await supaSave(supaUrl, supaKey, [
          { key: 'manucas_convs',         value: [] },
          { key: 'manucas_conv_messages', value: {} },
          { key: 'manucas_targets',       value: [] },
          { key: 'manucas_target_logs',   value: {} },
          { key: 'manucas_target_plans',  value: {} },
          { key: 'manucas_active_target', value: null },
          { key: 'manucas_active_conv',   value: null },
        ]);
      } catch {}
    }
  }, [supaUrl, supaKey]);

  return (
    <div
      className="flex flex-col h-screen w-screen overflow-hidden select-none"
      style={{ background: C.bg, color: C.text, fontFamily: 'Inter, system-ui, sans-serif' }}
    >
      {showUpdateModal && updateInfo && (
        <div
          className="fixed inset-0 flex items-center justify-center"
          style={{ zIndex: 9999, background: 'rgba(0,0,0,0.75)' }}
          onClick={() => dlProgress === null && setShowUpdateModal(false)}
        >
          <div
            className="rounded-2xl p-6 flex flex-col gap-4"
            style={{ background: '#111', border: `1px solid ${C.redBorder}`, width: 400, boxShadow: `0 0 40px rgba(255,51,51,0.15)` }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0" style={{ background: C.redDim, border: `1px solid ${C.redBorder}` }}>
                <span style={{ color: C.red, fontSize: 16 }}>↑</span>
              </div>
              <div>
                <div className="font-mono font-bold text-sm" style={{ color: C.red }}>Atualização disponível</div>
                <div className="font-mono text-[10px]" style={{ color: '#555' }}>versão v{updateInfo.version}</div>
              </div>
            </div>
            <p className="font-mono text-[10px] leading-relaxed" style={{ color: '#666' }}>
              Uma nova versão da ManucasPT está disponível. O ficheiro será descarregado automaticamente.
            </p>

            {dlProgress !== null ? (
              <div className="flex flex-col gap-2">
                <div className="flex justify-between font-mono text-[9px]" style={{ color: '#555' }}>
                  <span>{dlProgress < 100 ? 'A descarregar...' : 'Pronto!'}</span>
                  <span>{dlProgress}%</span>
                </div>
                <div className="w-full rounded-full overflow-hidden" style={{ height: 6, background: '#1a1a1a' }}>
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${dlProgress}%`, background: dlProgress === 100 ? C.green : C.red }}
                  />
                </div>
                {dlProgress === 100 && dlDest && (
                  <button
                    onClick={() => window.electron?.launchUpdate({ dest: dlDest })}
                    className="w-full py-2 rounded-lg font-mono text-[10px] font-bold uppercase tracking-widest mt-1"
                    style={{ background: C.green ? 'rgba(34,197,94,0.15)' : C.redDim, border: '1px solid rgba(34,197,94,0.3)', color: '#22c55e' }}
                  >
                    ▶ Instalar e fechar
                  </button>
                )}
              </div>
            ) : (
              <div className="flex gap-2">
                <button
                  onClick={async () => {
                    if (!updateInfo.downloadUrl) { window.electron?.openExternal(updateInfo.url); return; }
                    setDlProgress(0);
                    await window.electron?.downloadUpdate({ url: updateInfo.downloadUrl });
                  }}
                  className="flex-1 py-2 rounded-lg font-mono text-[10px] font-bold uppercase tracking-widest transition-all"
                  style={{ background: C.redDim, border: `1px solid ${C.redBorder}`, color: C.red }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,51,51,0.2)'}
                  onMouseLeave={e => e.currentTarget.style.background = C.redDim}
                >
                  ↓ Baixar v{updateInfo.version}
                </button>
                <button
                  onClick={() => setShowUpdateModal(false)}
                  className="px-4 py-2 rounded-lg font-mono text-[10px]"
                  style={{ background: '#1a1a1a', color: '#555', border: '1px solid #222' }}
                >
                  Depois
                </button>
              </div>
            )}
          </div>
        </div>
      )}
      <TitleBar />
      <div className="flex flex-1 overflow-hidden">
      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettings(false)}
        anthropicKey={apiKey}
        groqKey={groqKey}
        supaUrl={supaUrl}
        supaKey={supaKey}
        mcpUrl={mcpUrl}
        onSave={saveKeys}
        onReset={resetAll}
      />

      <Sidebar
        onSettings={() => setSettings(true)}
        activeNav={activeNav}
        onNavChange={setActiveNav}
        targets={targets}
        activeTarget={activeTarget}
        onTargetChange={handleTargetChange}
        onAddTarget={addTarget}
        onDeleteTarget={deleteTarget}
        onRenameTarget={renameTarget}
        convs={convs}
        activeConv={activeConv}
        onConvChange={handleConvChange}
        onAddConv={addConv}
        onDeleteConv={deleteConv}
        onRenameConv={renameConv}
        updateInfo={updateInfo}
        onUpdateClick={() => setShowUpdateModal(true)}
      />
      <ActivityLog logs={logs} activeTarget={activeTarget} />
      <InteractionPanel
        planItems={plan}
        onPlanToggle={togglePlan}
        messages={messages}
        onSend={sendMessage}
        apiKey={apiKey}
        groqKey={groqKey}
        activeNav={activeNav}
        activeTarget={activeTarget}
        activeConv={activeConv}
        convs={convs}
        targets={targets}
        logs={logs}
        activeModel={activeModel}
        onModelChange={changeModel}
        onSplit={openSplit}
        onCloseSplit={closeSplit}
        supaUrl={supaUrl}
        syncStatus={syncStatus}
        mcpTools={mcpTools}
        toolProgress={toolProgress}
        mcpUrl={mcpUrl}
      />
      {splitConv && (
        <>
          <div style={{ width: 1, flexShrink: 0, background: '#1a1a1a' }} />
          <InteractionPanel
            planItems={plan}
            onPlanToggle={togglePlan}
            messages={convMessages[splitConv] || []}
            onSend={(text) => sendMessage(text, splitConv)}
            apiKey={apiKey}
            groqKey={groqKey}
            activeNav="chat"
            activeTarget={activeTarget}
            activeConv={splitConv}
            convs={convs}
            targets={targets}
            logs={logs}
            activeModel={activeModel}
            onModelChange={changeModel}
            isSplit
            onCloseSplit={closeSplit}
            supaUrl={supaUrl}
            syncStatus={syncStatus}
          />
        </>
      )}
      </div>
    </div>
  );
}
