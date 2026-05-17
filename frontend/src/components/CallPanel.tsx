import { useEffect, useRef } from 'react';
import type { RideInfo } from '../mockData';

function formatDuration(s: number) {
  return `${Math.floor(s / 60).toString().padStart(2, '0')}:${(s % 60).toString().padStart(2, '0')}`;
}

function PhoneIcon({ color }: { color: string }) {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
      <path
        d="M3 1h3.5l1.5 3.5L6.5 6a9.5 9.5 0 0 0 3.5 3.5l1.5-1.5L15 9.5V13a1 1 0 0 1-1 1C5.716 14 1 9.284 1 3a1 1 0 0 1 1-1h1z"
        stroke={color} strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"
      />
    </svg>
  );
}

export function CallPanel({ ride }: { ride: RideInfo }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [ride.transcript]);

  const isActive = ride.callState === 'calling' || ride.callState === 'in_call';
  const statusColor = isActive ? '#22c55e' : '#374151';
  const statusLabel =
    ride.callState === 'calling'  ? 'DIALING' :
    ride.callState === 'in_call'  ? `IN CALL  ${formatDuration(ride.callDuration)}` :
    ride.callState === 'ended'    ? 'ENDED'   : 'STANDBY';

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-label">Voice Channel</span>
        <span className={isActive ? 'blink' : ''} style={{ fontFamily: 'var(--mono)', fontSize: '10px', color: statusColor }}>
          {statusLabel}
        </span>
      </div>

      {/* Caller row */}
      <div style={{ padding: '10px 10px 0' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: '10px', padding: '9px 10px', borderRadius: '4px',
          background: isActive ? 'color-mix(in srgb, #22c55e 5%, var(--s2))' : 'var(--s2)',
          border: `1px solid ${isActive ? 'color-mix(in srgb, #22c55e 18%, transparent)' : 'var(--border-subtle)'}`,
        }}>
          <div style={{ position: 'relative', width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            {ride.callState === 'calling' && (
              <>
                <span className="ripple" style={{ position: 'absolute', width: '32px', height: '32px', borderRadius: '50%', background: '#22c55e' }} />
                <span className="ripple-delay" style={{ position: 'absolute', width: '32px', height: '32px', borderRadius: '50%', background: '#22c55e' }} />
              </>
            )}
            <div style={{ position: 'relative', zIndex: 1, width: '32px', height: '32px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: isActive ? 'color-mix(in srgb, #22c55e 12%, var(--s3))' : 'var(--s3)' }}>
              <PhoneIcon color={isActive ? '#22c55e' : '#475569'} />
            </div>
          </div>

          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-1)', lineHeight: 1.3 }}>{ride.passengerName}</div>
            <div style={{ fontSize: '11px', color: 'var(--text-3)', fontFamily: 'var(--mono)', marginTop: '1px' }}>{ride.passengerPhone}</div>
          </div>

          {ride.callState === 'in_call' && (
            <span style={{ fontFamily: 'var(--mono)', fontSize: '13px', fontWeight: 500, color: '#22c55e', flexShrink: 0 }}>
              {formatDuration(ride.callDuration)}
            </span>
          )}
        </div>
      </div>

      {/* Transcript */}
      <div style={{ padding: '10px 10px 10px', display: 'flex', flexDirection: 'column', gap: '8px', flex: 1, minHeight: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span className="panel-label">Transcript</span>
          {ride.transcript.length > 0 && (
            <span className="panel-meta">{ride.transcript.length} turns</span>
          )}
        </div>

        <div ref={scrollRef} style={{ overflowY: 'auto', maxHeight: '190px', minHeight: '60px' }}>
          {ride.transcript.length === 0 ? (
            <div style={{ fontSize: '11px', color: 'var(--text-4)', textAlign: 'center', padding: '20px 0', fontStyle: 'italic' }}>
              No transcript
            </div>
          ) : (
            ride.transcript.map((entry) => (
              <div key={entry.id} className="fade-in" style={{ display: 'flex', gap: '8px', padding: '6px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                <span style={{
                  fontFamily: 'var(--mono)', fontSize: '10px', fontWeight: 600, flexShrink: 0, paddingTop: '1px', width: '46px',
                  color: entry.speaker === 'agent' ? '#3b82f6' : '#22c55e',
                }}>
                  {entry.speaker === 'agent' ? 'AGENT' : 'RIDER'}
                </span>
                <span style={{ fontSize: '12px', color: 'var(--text-2)', lineHeight: 1.5 }}>{entry.text}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
