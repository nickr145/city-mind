import { useState, useRef, useEffect } from 'react';

const SUGGESTED = [
  'Summarize all datasets at a glance',
  'How many building permits were issued this year?',
  'What is the status of water mains infrastructure?',
  'Show me bus stop coverage across municipalities',
];

function renderMarkdown(text) {
  // Minimal inline markdown → HTML (bold, inline code, links, line breaks)
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code style="background:#1e293b;color:#93c5fd;padding:1px 5px;border-radius:3px;font-size:0.85em">$1</code>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener" style="color:#60a5fa">$1</a>')
    .replace(/\n/g, '<br/>');
}

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: 'Hi! I\'m **CityMind AI**. Ask me anything about municipal datasets — permits, water mains, bus stops, or data quality.',
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (open) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
      inputRef.current?.focus();
    }
  }, [open, messages]);

  async function send(text) {
    const msg = (text || input).trim();
    if (!msg || loading) return;
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', text: msg }]);
    setLoading(true);
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL || ''}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg }),
      });
      const text = await res.text();
      let data;
      try { data = JSON.parse(text); } catch { data = {}; }
      if (!res.ok) throw new Error(data.detail || `Server error ${res.status}`);
      if (!data.reply) throw new Error('Empty response from agent');
      setMessages((prev) => [...prev, { role: 'assistant', text: data.reply }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: `**Error:** ${err.message}`, error: true },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <>
      {/* Floating toggle button */}
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? 'Close AI assistant' : 'Open AI assistant'}
        style={{
          position: 'fixed',
          bottom: '1.5rem',
          right: '1.5rem',
          width: 52,
          height: 52,
          borderRadius: '50%',
          background: 'var(--accent)',
          color: '#fff',
          border: 'none',
          cursor: 'pointer',
          fontSize: '1.4rem',
          boxShadow: '0 4px 16px rgba(37,99,235,0.45)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          transition: 'transform 0.15s',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.transform = 'scale(1.08)')}
        onMouseLeave={(e) => (e.currentTarget.style.transform = 'scale(1)')}
      >
        {open ? '✕' : '✦'}
      </button>

      {/* Chat panel */}
      {open && (
        <div
          style={{
            position: 'fixed',
            bottom: '5rem',
            right: '1.5rem',
            width: 380,
            maxWidth: 'calc(100vw - 2rem)',
            height: 520,
            maxHeight: 'calc(100vh - 7rem)',
            background: '#0f172a',
            border: '1px solid #1e293b',
            borderRadius: 12,
            display: 'flex',
            flexDirection: 'column',
            boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
            zIndex: 999,
            overflow: 'hidden',
          }}
        >
          {/* Header */}
          <div style={{
            padding: '0.75rem 1rem',
            borderBottom: '1px solid #1e293b',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            background: '#0f172a',
          }}>
            <span style={{ fontSize: '1rem' }}>✦</span>
            <div>
              <div style={{ color: '#f8fafc', fontWeight: 600, fontSize: '0.9rem', lineHeight: 1.2 }}>
                CityMind AI
              </div>
              <div style={{ color: '#64748b', fontSize: '0.72rem' }}>
                Municipal data assistant
              </div>
            </div>
            <div style={{
              marginLeft: 'auto',
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: loading ? '#d97706' : '#16a34a',
              transition: 'background 0.3s',
            }} />
          </div>

          {/* Messages */}
          <div style={{
            flex: 1,
            overflowY: 'auto',
            padding: '0.75rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.6rem',
          }}>
            {messages.map((m, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start',
                }}
              >
                <div
                  style={{
                    maxWidth: '88%',
                    padding: '0.55rem 0.75rem',
                    borderRadius: m.role === 'user' ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
                    background: m.role === 'user'
                      ? 'var(--accent)'
                      : m.error ? '#450a0a' : '#1e293b',
                    color: m.role === 'user' ? '#fff' : '#cbd5e1',
                    fontSize: '0.82rem',
                    lineHeight: 1.55,
                    wordBreak: 'break-word',
                  }}
                  // eslint-disable-next-line react/no-danger
                  dangerouslySetInnerHTML={{ __html: renderMarkdown(m.text) }}
                />
              </div>
            ))}

            {loading && (
              <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                <div style={{
                  padding: '0.55rem 0.9rem',
                  borderRadius: '12px 12px 12px 2px',
                  background: '#1e293b',
                  color: '#64748b',
                  fontSize: '0.82rem',
                  display: 'flex',
                  gap: 4,
                  alignItems: 'center',
                }}>
                  <span style={{ animation: 'chat-blink 1s 0s infinite' }}>●</span>
                  <span style={{ animation: 'chat-blink 1s 0.2s infinite' }}>●</span>
                  <span style={{ animation: 'chat-blink 1s 0.4s infinite' }}>●</span>
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* Suggestions — only show when just the greeting is present */}
          {messages.length === 1 && !loading && (
            <div style={{
              padding: '0 0.75rem 0.5rem',
              display: 'flex',
              flexWrap: 'wrap',
              gap: '0.35rem',
            }}>
              {SUGGESTED.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  style={{
                    background: '#1e293b',
                    border: '1px solid #334155',
                    color: '#94a3b8',
                    borderRadius: 20,
                    padding: '0.25rem 0.65rem',
                    fontSize: '0.72rem',
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#2563eb')}
                  onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#334155')}
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          {/* Input */}
          <div style={{
            padding: '0.6rem',
            borderTop: '1px solid #1e293b',
            display: 'flex',
            gap: '0.4rem',
            background: '#0f172a',
          }}>
            <textarea
              ref={inputRef}
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Ask about city data…"
              disabled={loading}
              style={{
                flex: 1,
                background: '#1e293b',
                border: '1px solid #334155',
                borderRadius: 8,
                color: '#e2e8f0',
                fontSize: '0.82rem',
                padding: '0.45rem 0.7rem',
                resize: 'none',
                outline: 'none',
                fontFamily: 'inherit',
                lineHeight: 1.4,
              }}
            />
            <button
              onClick={() => send()}
              disabled={loading || !input.trim()}
              style={{
                background: loading || !input.trim() ? '#1e293b' : 'var(--accent)',
                border: 'none',
                borderRadius: 8,
                color: loading || !input.trim() ? '#475569' : '#fff',
                cursor: loading || !input.trim() ? 'default' : 'pointer',
                padding: '0.45rem 0.75rem',
                fontSize: '0.85rem',
                transition: 'background 0.15s',
              }}
            >
              ↑
            </button>
          </div>
        </div>
      )}

      <style>{`
        @keyframes chat-blink {
          0%, 80%, 100% { opacity: 0.2; }
          40% { opacity: 1; }
        }
      `}</style>
    </>
  );
}
