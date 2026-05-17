import { useEffect, useRef, useState } from 'react';
import type { RideInfo } from '../mockData';

type View = { x: number; y: number; scale: number };
const INIT: View = { x: 0, y: 0, scale: 1 };

export function LiveFeed({ ride }: { ride: RideInfo }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewRef      = useRef<View>(INIT);
  const dragRef      = useRef<{ mx: number; my: number; vx: number; vy: number } | null>(null);
  const [view, _setView] = useState<View>(INIT);
  const setView = (v: View) => { viewRef.current = v; _setView(v); };

  const latest = ride.vlmEvents.at(-1);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const v  = viewRef.current;
      const r  = el.getBoundingClientRect();
      const mx = e.clientX - r.left;
      const my = e.clientY - r.top;
      const cx = (mx - v.x) / v.scale;
      const cy = (my - v.y) / v.scale;
      const ns = Math.min(Math.max(v.scale * (e.deltaY < 0 ? 1.12 : 0.9), 1), 6);
      const nw = r.width  * ns;
      const nh = r.height * ns;
      const nx = Math.min(0, Math.max(mx - cx * ns, r.width  - nw));
      const ny = Math.min(0, Math.max(my - cy * ns, r.height - nh));
      setView({ scale: ns, x: nx, y: ny });
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

  const onMouseDown = (e: React.MouseEvent) => {
    dragRef.current = { mx: e.clientX, my: e.clientY, vx: viewRef.current.x, vy: viewRef.current.y };
  };
  const onMouseMove = (e: React.MouseEvent) => {
    if (!dragRef.current) return;
    const el = containerRef.current;
    if (!el) return;
    const v  = viewRef.current;
    const r  = el.getBoundingClientRect();
    const nw = r.width  * v.scale;
    const nh = r.height * v.scale;
    const nx = Math.min(0, Math.max(dragRef.current.vx + (e.clientX - dragRef.current.mx), r.width  - nw));
    const ny = Math.min(0, Math.max(dragRef.current.vy + (e.clientY - dragRef.current.my), r.height - nh));
    setView({ ...v, x: nx, y: ny });
  };
  const stopDrag = () => { dragRef.current = null; };

  return (
    <div
      ref={containerRef}
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseUp={stopDrag}
      onMouseLeave={stopDrag}
      onDoubleClick={() => setView(INIT)}
      style={{
        position: 'relative', width: '100%', height: '100%',
        background: '#060810', overflow: 'hidden',
        cursor: dragRef.current ? 'grabbing' : 'grab',
      }}
    >
      {/* ── Zoomable camera content ── */}
      <div style={{
        position: 'absolute', inset: 0,
        transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`,
        transformOrigin: '0 0',
        willChange: 'transform',
      }}>
        {/* Scanlines */}
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,0,0,0.1) 3px, rgba(0,0,0,0.1) 4px)',
        }} />

        {/* Rule-of-thirds grid */}
        <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', opacity: 0.06 }}>
          <line x1="33.33%" y1="0" x2="33.33%" y2="100%" stroke="#fff" strokeWidth="0.5" />
          <line x1="66.66%" y1="0" x2="66.66%" y2="100%" stroke="#fff" strokeWidth="0.5" />
          <line x1="0" y1="33.33%" x2="100%" y2="33.33%" stroke="#fff" strokeWidth="0.5" />
          <line x1="0" y1="66.66%" x2="100%" y2="66.66%" stroke="#fff" strokeWidth="0.5" />
          <line x1="50%" y1="47%" x2="50%" y2="53%" stroke="#fff" strokeWidth="0.5" />
          <line x1="47%" y1="50%" x2="53%" y2="50%" stroke="#fff" strokeWidth="0.5" />
        </svg>

        {/* Placeholder */}
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '8px' }}>
          <div style={{ fontSize: '11px', letterSpacing: '0.2em', color: '#1a2035', fontFamily: 'var(--mono)' }}>CARLA RGB CAMERA · EGO VEHICLE</div>
          <div style={{ fontSize: '10px', color: '#111825', fontFamily: 'var(--mono)' }}>awaiting simulation feed</div>
        </div>
      </div>

      {/* ── Fixed HUD (stays put when zooming) ── */}

      {/* Corner brackets */}
      <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', opacity: 0.25, zIndex: 5 }}>
        <path d="M 22 13 L 11 13 L 11 28" stroke="#fff" strokeWidth="1" fill="none" />
        <path d="M calc(100% - 22px) 13 L calc(100% - 11px) 13 L calc(100% - 11px) 28" stroke="#fff" strokeWidth="1" fill="none" />
        <path d="M 11 calc(100% - 28px) L 11 calc(100% - 13px) L 22 calc(100% - 13px)" stroke="#fff" strokeWidth="1" fill="none" />
        <path d="M calc(100% - 11px) calc(100% - 28px) L calc(100% - 11px) calc(100% - 13px) L calc(100% - 22px) calc(100% - 13px)" stroke="#fff" strokeWidth="1" fill="none" />
      </svg>

      {/* LIVE badge */}
      <div style={{ position: 'absolute', top: '12px', left: '12px', zIndex: 10, display: 'flex', alignItems: 'center', gap: '6px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '3px 8px', borderRadius: '3px', background: 'rgba(0,0,0,0.55)', border: '1px solid rgba(255,255,255,0.07)' }}>
          <span className="blink" style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#ef4444', display: 'inline-block' }} />
          <span style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '0.14em', color: '#e2e8f0', fontFamily: 'var(--mono)' }}>LIVE</span>
        </div>
      </div>

      {/* Frame counter */}
      <div style={{ position: 'absolute', top: '12px', right: '12px', zIndex: 10 }}>
        <div style={{ padding: '3px 8px', borderRadius: '3px', background: 'rgba(0,0,0,0.55)', border: '1px solid rgba(255,255,255,0.06)' }}>
          <span style={{ fontSize: '10px', color: '#2a3555', fontFamily: 'var(--mono)' }}>F#{latest?.frameId ?? 0}</span>
        </div>
      </div>

      {/* Ride info bottom-right */}
      <div style={{ position: 'absolute', bottom: '12px', right: '12px', zIndex: 10 }}>
        <div style={{ padding: '4px 8px', borderRadius: '3px', background: 'rgba(0,0,0,0.55)', border: '1px solid rgba(255,255,255,0.05)' }}>
          <div style={{ fontSize: '10px', color: '#2a3555', fontFamily: 'var(--mono)', lineHeight: 1.5 }}>{ride.rideId} · {ride.passengerName}</div>
        </div>
      </div>

      {/* Zoom hint — only at 1× */}
      {view.scale === 1 && (
        <div style={{ position: 'absolute', bottom: '12px', left: '50%', transform: 'translateX(-50%)', zIndex: 10, pointerEvents: 'none' }}>
          <span style={{ fontSize: '9px', color: '#1a2540', fontFamily: 'var(--mono)', letterSpacing: '0.08em' }}>
            scroll to zoom · drag to pan · dbl-click to reset
          </span>
        </div>
      )}
    </div>
  );
}
