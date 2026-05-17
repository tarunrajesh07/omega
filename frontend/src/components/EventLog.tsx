import { useEffect, useRef } from 'react';
import type { EventLogEntry } from '../mockData';

const SEV_COLOR: Record<EventLogEntry['severity'], string> = {
  info: 'var(--text-3)', warn: '#f59e0b', error: '#ef4444', success: '#22c55e',
};
const CAT_LABEL: Record<EventLogEntry['category'], string> = {
  vlm: 'VLM', call: 'CALL', system: 'SYS', ride: 'RIDE',
};

function fmtTime(d: Date) {
  return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function EventLog({ entries }: { entries: EventLogEntry[] }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [entries]);

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-label">Event Log</span>
        <span className="panel-meta">{entries.length} events</span>
      </div>

      <div style={{ padding: '6px 10px 10px' }}>
        <div ref={scrollRef} style={{ overflowY: 'auto', maxHeight: '200px', fontFamily: 'var(--mono)', fontSize: '10px' }}>
          {entries.map((e) => (
            <div key={e.id} className="fade-in" style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', padding: '3px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-4)', flexShrink: 0, lineHeight: 1.6 }}>{fmtTime(e.timestamp)}</span>
              <span style={{
                flexShrink: 0, lineHeight: 1.6, padding: '0 4px', borderRadius: '2px',
                background: 'var(--s3)', border: '1px solid var(--border-subtle)', color: 'var(--text-3)',
              }}>
                {CAT_LABEL[e.category]}
              </span>
              <span style={{ color: SEV_COLOR[e.severity], lineHeight: 1.6, wordBreak: 'break-word' }}>{e.message}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
