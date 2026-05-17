type TriggerFn = (event: 'blocked' | 'hazard' | 'rerouting' | 'arrived' | 'reset') => void;

const ACTIONS: Array<{
  event: 'blocked' | 'hazard' | 'rerouting' | 'arrived' | 'reset';
  label: string;
  desc: string;
  color: string;
}> = [
  { event: 'blocked',   label: 'Blockage',  desc: 'Delivery truck in lane',  color: '#f59e0b' },
  { event: 'hazard',    label: 'Hazard',    desc: 'Road debris detected',    color: '#ef4444' },
  { event: 'rerouting', label: 'Reroute',   desc: 'Traffic congestion',      color: '#3b82f6' },
  { event: 'arrived',   label: 'Arrival',   desc: 'Destination reached',     color: '#a855f7' },
];

export function DemoControls({ onTrigger }: { onTrigger: TriggerFn }) {
  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-label">Scenario Injector</span>
        <span style={{ fontSize: '9px', fontWeight: 600, letterSpacing: '0.1em', padding: '2px 6px', borderRadius: '3px', color: '#f59e0b', background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.25)' }}>
          DEMO
        </span>
      </div>

      <div style={{ padding: '8px' }}>
        {ACTIONS.map((a) => (
          <button
            key={a.event}
            onClick={() => onTrigger(a.event)}
            style={{
              display: 'flex', alignItems: 'center', gap: '10px',
              width: '100%', padding: '8px 10px', marginBottom: '6px',
              borderRadius: '4px', textAlign: 'left', cursor: 'pointer',
              background: 'var(--s2)',
              border: '1px solid var(--border)',
              borderLeft: `3px solid ${a.color}30`,
              transition: 'border-left-color 0.15s',
            }}
            onMouseEnter={e => (e.currentTarget.style.borderLeftColor = a.color)}
            onMouseLeave={e => (e.currentTarget.style.borderLeftColor = `${a.color}30`)}
          >
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-1)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                Trigger {a.label}
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-3)', marginTop: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {a.desc}
              </div>
            </div>
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" style={{ flexShrink: 0, color: 'var(--text-4)' }}>
              <path d="M2 5h6M5 2l3 3-3 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        ))}

        <button
          onClick={() => onTrigger('reset')}
          style={{
            width: '100%', padding: '7px', borderRadius: '4px', cursor: 'pointer',
            background: 'transparent', border: '1px solid var(--border)',
            fontSize: '11px', color: 'var(--text-3)', textAlign: 'center',
            transition: 'color 0.15s, background 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'var(--s2)'; e.currentTarget.style.color = 'var(--text-2)'; }}
          onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-3)'; }}
        >
          Reset Demo
        </button>
      </div>
    </div>
  );
}
