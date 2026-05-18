import { useEffect, useRef, useState } from 'react';
import { submitTranscript } from '../api';
import type { RideInfo } from '../mockData';

function fmt(s: number) {
  return `${Math.floor(s / 60).toString().padStart(2, '0')}:${(s % 60).toString().padStart(2, '0')}`;
}

function PhoneIcon({ color }: { color: string }) {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
      <path d="M3 1h3.5l1.5 3.5L6.5 6a9.5 9.5 0 0 0 3.5 3.5l1.5-1.5L15 9.5V13a1 1 0 0 1-1 1C5.716 14 1 9.284 1 3a1 1 0 0 1 1-1h1z"
        stroke={color} strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Sidebar({ ride }: { ride: RideInfo }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [text, setText] = useState('');
  const [status, setStatus] = useState<string | null>(null);
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [ride.transcript]);

  const isActive = ride.callState === 'calling' || ride.callState === 'in_call';
  const callColor =
    ride.callState === 'in_call'  ? '#22c55e' :
    ride.callState === 'calling'  ? '#f59e0b' :
    ride.callState === 'ended'    ? '#475569' : '#1e2535';

  const callLabel =
    ride.callState === 'calling'  ? 'DIALING...' :
    ride.callState === 'in_call'  ? 'IN CALL' :
    ride.callState === 'ended'    ? 'CALL ENDED' : 'STANDBY';

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const transcript = text.trim();
    if (!transcript) return;
    setStatus('sending...');
    try {
      const result = await submitTranscript(transcript);
      setText('');
      setStatus(`decision: ${result.decision}`);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 0 }}>

      {/* ── Call status ── */}
      <div style={{ padding: '16px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.1em', color: 'var(--text-4)', textTransform: 'uppercase', marginBottom: '12px', fontFamily: 'var(--mono)' }}>
          Voice Channel
        </div>

        {/* Call badge */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 12px', borderRadius: '6px',
          background: isActive ? 'color-mix(in srgb, #22c55e 5%, var(--s2))' : 'var(--s2)',
          border: `1px solid ${isActive ? 'color-mix(in srgb, #22c55e 18%, transparent)' : 'var(--border)'}`,
        }}>
          <div style={{ position: 'relative', width: '34px', height: '34px', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            {ride.callState === 'calling' && (
              <>
                <span className="ripple" style={{ position: 'absolute', width: '34px', height: '34px', borderRadius: '50%', background: '#f59e0b' }} />
                <span className="ripple-delay" style={{ position: 'absolute', width: '34px', height: '34px', borderRadius: '50%', background: '#f59e0b' }} />
              </>
            )}
            <div style={{ position: 'relative', zIndex: 1, width: '34px', height: '34px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--s3)' }}>
              <PhoneIcon color={isActive ? (ride.callState === 'calling' ? '#f59e0b' : '#22c55e') : '#374151'} />
            </div>
          </div>

          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-1)' }}>{ride.passengerName}</div>
            <div style={{ fontSize: '11px', color: 'var(--text-3)', fontFamily: 'var(--mono)', marginTop: '1px' }}>{ride.passengerPhone}</div>
          </div>
        </div>

        {/* Status row */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '8px', padding: '0 2px' }}>
          <span className={isActive ? 'blink' : ''} style={{ fontSize: '11px', fontWeight: 600, letterSpacing: '0.08em', color: callColor, fontFamily: 'var(--mono)' }}>
            {callLabel}
          </span>
          {ride.callState === 'in_call' && (
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#22c55e', fontFamily: 'var(--mono)' }}>
              {fmt(ride.callDuration)}
            </span>
          )}
        </div>
      </div>

      {/* ── Transcript ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, padding: '12px 16px 16px' }}>
        <div style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.1em', color: 'var(--text-4)', textTransform: 'uppercase', marginBottom: '10px', fontFamily: 'var(--mono)' }}>
          Transcript
        </div>

        <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
          {ride.transcript.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '80px' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-4)', fontStyle: 'italic' }}>No active call</span>
            </div>
          ) : (
            ride.transcript.map((entry) => (
              <div key={entry.id} className="fade-in" style={{ marginBottom: '12px' }}>
                <div style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.08em', marginBottom: '3px', fontFamily: 'var(--mono)', color: entry.speaker === 'agent' ? '#3b82f6' : '#22c55e' }}>
                  {entry.speaker === 'agent' ? 'CLARA (AGENT)' : 'PASSENGER'}
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-2)', lineHeight: 1.55, paddingLeft: '8px', borderLeft: `2px solid ${entry.speaker === 'agent' ? '#1e3a5f' : '#14321e'}` }}>
                  {entry.text}
                </div>
              </div>
            ))
          )}
        </div>

        <form onSubmit={onSubmit} style={{ marginTop: '12px', borderTop: '1px solid var(--border)', paddingTop: '12px' }}>
          <div style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.1em', color: 'var(--text-4)', textTransform: 'uppercase', marginBottom: '8px', fontFamily: 'var(--mono)' }}>
            Provide Transcript
          </div>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Type what the passenger said, e.g. reroute me to the alternate pickup"
            rows={3}
            style={{
              width: '100%', boxSizing: 'border-box', resize: 'vertical', borderRadius: '4px',
              background: 'var(--s2)', border: '1px solid var(--border)', color: 'var(--text-1)',
              padding: '8px', fontSize: '12px', lineHeight: 1.4, outline: 'none',
            }}
          />
          <button
            type="submit"
            style={{
              width: '100%', marginTop: '8px', padding: '8px', borderRadius: '4px', cursor: 'pointer',
              background: '#1d4ed8', border: '1px solid #2563eb', color: '#eff6ff',
              fontSize: '11px', fontWeight: 700, letterSpacing: '0.08em', fontFamily: 'var(--mono)',
            }}
          >
            Submit Passenger Line
          </button>
          {status && <div style={{ marginTop: '6px', color: 'var(--text-3)', fontSize: '10px', fontFamily: 'var(--mono)' }}>{status}</div>}
        </form>
      </div>
    </div>
  );
}
