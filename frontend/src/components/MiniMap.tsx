import { useEffect, useRef, useState } from 'react';
import type { RideInfo } from '../mockData';

const W = 1000, H = 600;
const COLS = [60, 165, 270, 375, 480, 585, 690, 795, 900];
const ROWS = [60, 145, 230, 315, 400, 485, 560];
const COL_NAMES = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th'];
const ROW_NAMES = ['Bryant', 'Brannan', 'Townsend', 'King', 'Mission', 'Howard', 'Folsom'];

const SEGMENTS: [number, number, number, number][] = [
  [165, 485, 165, 315],
  [165, 315, 480, 315],
  [480, 315, 480, 145],
  [480, 145, 900, 145],
];
const PICKUP: [number, number] = [165, 485];
const DEST: [number, number]   = [900, 145];

const SEG_LENS = SEGMENTS.map(([x1, y1, x2, y2]) => Math.hypot(x2 - x1, y2 - y1));
const TOTAL    = SEG_LENS.reduce((a, b) => a + b, 0);
const CUM      = SEG_LENS.reduce<number[]>((acc, l) => { acc.push((acc.at(-1) ?? 0) + l); return acc; }, []);

function carPos(t: number): [number, number] {
  const d = t * TOTAL;
  for (let i = 0; i < SEGMENTS.length; i++) {
    const start = i === 0 ? 0 : CUM[i - 1];
    if (d <= CUM[i]) {
      const f = (d - start) / SEG_LENS[i];
      const [x1, y1, x2, y2] = SEGMENTS[i];
      return [x1 + (x2 - x1) * f, y1 + (y2 - y1) * f];
    }
  }
  return DEST;
}

function traveledPath(t: number) {
  const d = t * TOTAL;
  let acc = 0, path = '';
  for (let i = 0; i < SEGMENTS.length; i++) {
    const [x1, y1, x2, y2] = SEGMENTS[i];
    if (i === 0) path += `M ${x1} ${y1}`;
    if (d <= acc + SEG_LENS[i]) {
      const f = (d - acc) / SEG_LENS[i];
      path += ` L ${x1 + (x2 - x1) * f} ${y1 + (y2 - y1) * f}`;
      break;
    }
    path += ` L ${x2} ${y2}`;
    acc += SEG_LENS[i];
  }
  return path;
}

const FULL_PATH = SEGMENTS.map(([x1, y1, x2, y2], i) => (i === 0 ? `M ${x1} ${y1}` : '') + ` L ${x2} ${y2}`).join('');
const ALERT_CLR: Record<string, string> = { blocked: '#f59e0b', hazard: '#ef4444' };

type View = { x: number; y: number; scale: number };
const INIT: View = { x: 0, y: 0, scale: 1 };

export function MiniMap({ ride }: { ride: RideInfo }) {
  const svgRef  = useRef<SVGSVGElement>(null);
  const viewRef = useRef<View>(INIT);
  const dragRef = useRef<{ mx: number; my: number; vx: number; vy: number } | null>(null);
  const [view, _setView] = useState<View>(INIT);
  const setView = (v: View) => { viewRef.current = v; _setView(v); };

  function toSvg(cx: number, cy: number): [number, number] {
    const el = svgRef.current;
    if (!el) return [cx, cy];
    const r = el.getBoundingClientRect();
    return [(cx - r.left) / r.width * W, (cy - r.top) / r.height * H];
  }

  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const v = viewRef.current;
      const [mx, my] = toSvg(e.clientX, e.clientY);
      const cx = (mx - v.x) / v.scale;
      const cy = (my - v.y) / v.scale;
      const ns = Math.min(Math.max(v.scale * (e.deltaY < 0 ? 1.15 : 0.87), 0.4), 8);
      setView({ scale: ns, x: mx - cx * ns, y: my - cy * ns });
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

  const onMouseDown = (e: React.MouseEvent) => {
    const [mx, my] = toSvg(e.clientX, e.clientY);
    dragRef.current = { mx, my, vx: view.x, vy: view.y };
  };
  const onMouseMove = (e: React.MouseEvent) => {
    if (!dragRef.current) return;
    const [mx, my] = toSvg(e.clientX, e.clientY);
    setView({ ...viewRef.current, x: viewRef.current.x + (mx - dragRef.current.mx), y: viewRef.current.y + (my - dragRef.current.my) });
    dragRef.current = { ...dragRef.current, mx, my };
  };
  const onMouseUp    = () => { dragRef.current = null; };
  const onMouseLeave = () => { dragRef.current = null; };

  const isAlert  = ride.state === 'blocked' || ride.state === 'hazard';
  const carColor = isAlert ? ALERT_CLR[ride.state] : '#3b82f6';
  const progress = Math.min(ride.carPosition.x / 100, 0.99);
  const [cx, cy] = carPos(progress);

  return (
    <div style={{
      position: 'absolute', bottom: '14px', left: '14px', zIndex: 20,
      width: '300px', borderRadius: '6px', overflow: 'hidden',
      border: '1px solid rgba(255,255,255,0.08)',
      background: 'rgba(6,8,16,0.88)',
      backdropFilter: 'blur(8px)',
      boxShadow: '0 4px 24px rgba(0,0,0,0.6)',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '5px 8px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
        <span style={{ fontSize: '9px', fontWeight: 600, letterSpacing: '0.12em', color: '#334155', fontFamily: 'var(--mono)' }}>ROUTE MAP</span>
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          <span style={{ fontSize: '9px', color: '#1e2d40', fontFamily: 'var(--mono)' }}>{view.scale.toFixed(1)}×</span>
          <button
            onClick={() => setView(INIT)}
            style={{ fontSize: '9px', color: '#334155', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
          >
            reset
          </button>
        </div>
      </div>

      {/* Map */}
      <div style={{ aspectRatio: `${W}/${H}`, position: 'relative' }}>
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          style={{ width: '100%', height: '100%', display: 'block', cursor: dragRef.current ? 'grabbing' : 'grab' }}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMouseLeave={onMouseLeave}
        >
          <g transform={`translate(${view.x} ${view.y}) scale(${view.scale})`}>
            {ROWS.slice(0, -1).map((y1, ri) =>
              COLS.slice(0, -1).map((x1, ci) => (
                <rect key={`${ci}-${ri}`} x={x1 + 6} y={y1 + 6} width={COLS[ci + 1] - x1 - 12} height={ROWS[ri + 1] - y1 - 12} fill="#0a0d18" rx="2" />
              ))
            )}
            {ROWS.map((y, i) => <line key={`h${i}`} x1="20" y1={y} x2={W - 20} y2={y} stroke="#111828" strokeWidth="9" />)}
            {COLS.map((x, i) => <line key={`v${i}`} x1={x} y1="20" x2={x} y2={H - 20} stroke="#111828" strokeWidth="9" />)}
            {ROW_NAMES.map((n, i) => <text key={n} x="22" y={ROWS[i] - 4} fontSize="8" fill="#1a2540" fontFamily="monospace">{n}</text>)}
            {COL_NAMES.map((n, i) => <text key={n} x={COLS[i]} y="14" fontSize="8" fill="#1a2540" fontFamily="monospace" textAnchor="middle">{n}</text>)}
            <path d={FULL_PATH} fill="none" stroke="#142040" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
            <path d={traveledPath(progress)} fill="none" stroke="#3b82f6" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx={PICKUP[0]} cy={PICKUP[1]} r="6" fill="#111828" stroke="#334155" strokeWidth="1.5" />
            <circle cx={PICKUP[0]} cy={PICKUP[1]} r="2.5" fill="#475569" />
            <circle cx={DEST[0]} cy={DEST[1]} r="7" fill="#031c12" stroke="#10b981" strokeWidth="1.5" />
            <circle cx={DEST[0]} cy={DEST[1]} r="3" fill="#10b981" />
            {isAlert && <circle cx={cx} cy={cy} r="16" fill={carColor} opacity="0.1" />}
            <circle cx={cx} cy={cy} r="6" fill={carColor} />
            <circle cx={cx} cy={cy} r="10" fill="none" stroke={carColor} strokeWidth="1.5" opacity="0.4" />
          </g>
        </svg>
      </div>
    </div>
  );
}
