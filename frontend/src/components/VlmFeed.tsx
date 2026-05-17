import type { VlmEvent, VlmEventType } from '../mockData';

const TYPE_CONFIG: Record<VlmEventType, { color: string; label: string }> = {
  en_route:  { color: '#22c55e', label: 'EN_ROUTE'  },
  blocked:   { color: '#f59e0b', label: 'BLOCKED'   },
  hazard:    { color: '#ef4444', label: 'HAZARD'    },
  rerouting: { color: '#3b82f6', label: 'REROUTING' },
  arrived:   { color: '#a855f7', label: 'ARRIVED'   },
};

function fmtTime(d: Date) {
  return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function VlmFeed({ events }: { events: VlmEvent[] }) {
  const sorted = [...events].reverse();
  const latest = sorted[0];

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-label">VLM Events</span>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <span className="panel-meta">Gemini Live</span>
          {latest && <span className="panel-meta">F#{latest.frameId}</span>}
        </div>
      </div>

      {/* Latest event */}
      {latest && (
        <div className="fade-in" style={{
          margin: '10px 10px 0', padding: '9px 10px', borderRadius: '4px',
          background: `color-mix(in srgb, ${TYPE_CONFIG[latest.type].color} 5%, var(--s2))`,
          border: `1px solid color-mix(in srgb, ${TYPE_CONFIG[latest.type].color} 20%, transparent)`,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
            <span style={{ fontFamily: 'var(--mono)', fontSize: '10px', fontWeight: 700, letterSpacing: '0.1em', color: TYPE_CONFIG[latest.type].color }}>
              {TYPE_CONFIG[latest.type].label}
            </span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: '10px', color: 'var(--text-3)' }}>
              {(latest.confidence * 100).toFixed(0)}% conf
            </span>
          </div>
          <p style={{ fontSize: '11px', color: 'var(--text-2)', lineHeight: 1.5, margin: 0 }}>{latest.reason}</p>
        </div>
      )}

      {/* History */}
      <div style={{ padding: '8px 10px 10px' }}>
        <div style={{ overflowY: 'auto', maxHeight: '150px', fontFamily: 'var(--mono)', fontSize: '10px' }}>
          {sorted.slice(1).length === 0 ? (
            <div style={{ color: 'var(--text-4)', fontStyle: 'italic', padding: '8px 0' }}>No history yet</div>
          ) : (
            sorted.slice(1).map((ev) => {
              const cfg = TYPE_CONFIG[ev.type];
              return (
                <div key={ev.id} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '3px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                  <span style={{ color: 'var(--text-4)', flexShrink: 0, width: '60px' }}>{fmtTime(ev.timestamp)}</span>
                  <span style={{ color: cfg.color, flexShrink: 0, width: '68px', fontWeight: 500 }}>{cfg.label}</span>
                  <span style={{ color: 'var(--text-4)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ev.reason}</span>
                  <span style={{ color: 'var(--text-4)', flexShrink: 0 }}>#{ev.frameId}</span>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
