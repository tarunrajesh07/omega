import { useEffect, useRef, useState } from 'react';
import {
  INITIAL_RIDE,
  makeVlmEvent,
  type RideInfo,
} from './mockData';

import { LiveFeed } from './components/LiveFeed';
import { MiniMap } from './components/MiniMap';
import { Sidebar } from './components/Sidebar';

function deepClone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj, (_k, v) => (v instanceof Date ? v.toISOString() : v)));
}

function reviveDates(ride: RideInfo): RideInfo {
  return {
    ...ride,
    vlmEvents: ride.vlmEvents.map(e => ({ ...e, timestamp: new Date(e.timestamp) })),
    transcript: ride.transcript.map(e => ({ ...e, timestamp: new Date(e.timestamp) })),
    eventLog: ride.eventLog.map(e => ({ ...e, timestamp: new Date(e.timestamp) })),
  };
}

export default function App() {
  const [ride, setRide] = useState<RideInfo>(() => reviveDates(deepClone(INITIAL_RIDE)));
  const tickRef     = useRef<ReturnType<typeof setInterval> | null>(null);
  const callTickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [clock, setClock] = useState(() => new Date().toLocaleTimeString('en-US', { hour12: false }));

  useEffect(() => {
    const t = setInterval(() => setClock(new Date().toLocaleTimeString('en-US', { hour12: false })), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    tickRef.current = setInterval(() => {
      setRide(prev => {
        if (prev.state === 'arrived' || prev.state === 'idle') return prev;
        const moving = prev.state === 'en_route' || prev.state === 'rerouting';
        const newEta = Math.max(0, prev.eta - (moving ? 1 : 0));
        const newPos = moving ? Math.min(100, prev.carPosition.x + 0.15) : prev.carPosition.x;
        const emit   = moving && Math.random() < 0.06;
        const vlmEv  = emit ? makeVlmEvent('en_route') : null;
        return {
          ...prev,
          eta: newEta,
          carPosition: { x: newPos, y: 50 },
          vlmEvents: vlmEv ? [...prev.vlmEvents, vlmEv] : prev.vlmEvents,
          eventLog: prev.eventLog,
        };
      });
    }, 1000);
    return () => { if (tickRef.current) clearInterval(tickRef.current); };
  }, []);

  useEffect(() => {
    if (ride.callState === 'in_call') {
      callTickRef.current = setInterval(() => {
        setRide(prev => ({ ...prev, callDuration: prev.callDuration + 1 }));
      }, 1000);
    } else {
      if (callTickRef.current) clearInterval(callTickRef.current);
    }
    return () => { if (callTickRef.current) clearInterval(callTickRef.current); };
  }, [ride.callState]);

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--s0)', color: 'var(--text-1)', overflow: 'hidden' }}>

      {/* ── Header ── */}
      <header style={{ height: '44px', flexShrink: 0, borderBottom: '1px solid var(--border)', background: 'var(--s1)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 16px', gap: '16px' }}>

        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
          <div style={{ width: '24px', height: '24px', borderRadius: '4px', background: '#1d4ed8', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', fontWeight: 700, color: '#fff', letterSpacing: '0.05em' }}>C</div>
          <span style={{ fontSize: '13px', fontWeight: 600 }}>CLARA</span>
          <span style={{ fontSize: '10px', color: 'var(--text-4)', letterSpacing: '0.1em', textTransform: 'uppercase', fontFamily: 'var(--mono)' }}>Ops</span>
        </div>

        {/* Status dots + clock */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexShrink: 0, fontFamily: 'var(--mono)', fontSize: '10px' }}>
          {[{ label: 'Gemini', ok: true }, { label: 'AgentPhone', ok: true }, { label: 'CARLA', ok: false }].map(({ label, ok }) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span className={ok ? 'blink' : ''} style={{ width: '5px', height: '5px', borderRadius: '50%', background: ok ? '#22c55e' : '#f59e0b', display: 'inline-block' }} />
              <span style={{ color: 'var(--text-3)' }}>{label}</span>
            </div>
          ))}
          <span style={{ color: 'var(--text-4)', borderLeft: '1px solid var(--border)', paddingLeft: '14px' }}>{clock}</span>
        </div>
      </header>

      {/* ── Body ── */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>

        {/* Center: live feed + mini map overlay */}
        <div style={{ flex: 1, position: 'relative', minWidth: 0 }}>
          <LiveFeed ride={ride} />
          <MiniMap ride={ride} />
        </div>

        {/* Right sidebar */}
        <div style={{ width: '300px', flexShrink: 0, borderLeft: '1px solid var(--border)', background: 'var(--s1)', overflowY: 'auto' }}>
          <Sidebar ride={ride} />
        </div>
      </div>
    </div>
  );
}
