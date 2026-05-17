import { useEffect, useRef, useState } from 'react';
import type { RideInfo } from '../mockData';

// Expanded city grid — 1000×600 SVG units
const W = 1000;
const H = 600;
const COLS = [60, 165, 270, 375, 480, 585, 690, 795, 900]; // 9 vertical streets
const ROWS = [60, 145, 230, 315, 400, 485, 560];            // 7 horizontal streets
const COL_NAMES = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th'];
const ROW_NAMES = ['Bryant St', 'Brannan St', 'Townsend St', 'King St', 'Mission St', 'Howard St', 'Folsom St'];

// Route: pickup at (165, 485) → destination at (900, 145)
const SEGMENTS: [number, number, number, number][] = [
  [165, 485, 165, 315],  // north on 2nd: Howard→King
  [165, 315, 480, 315],  // east on King: 2nd→5th
  [480, 315, 480, 145],  // north on 5th: King→Brannan
  [480, 145, 900, 145],  // east on Brannan: 5th→9th
];
const PICKUP: [number, number] = [165, 485];
const DEST: [number, number]   = [900, 145];

const SEG_LENS = SEGMENTS.map(([x1, y1, x2, y2]) => Math.hypot(x2 - x1, y2 - y1));
const TOTAL = SEG_LENS.reduce((a, b) => a + b, 0);
const CUM   = SEG_LENS.reduce<number[]>((acc, l) => { acc.push((acc.at(-1) ?? 0) + l); return acc; }, []);

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

function traveledPath(t: number): string {
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

const FULL_PATH = SEGMENTS.map(([x1, y1, x2, y2], i) =>
  (i === 0 ? `M ${x1} ${y1}` : '') + ` L ${x2} ${y2}`
).join('');

const ALERT_CLR: Record<string, string> = { blocked: '#f59e0b', hazard: '#ef4444' };

type View = { x: number; y: number; scale: number };
const INIT_VIEW: View = { x: 0, y: 0, scale: 1 };

export function MapView({ ride }: { ride: RideInfo }) {
  const svgRef   = useRef<SVGSVGElement>(null);
  const viewRef  = useRef<View>(INIT_VIEW);
  const dragRef  = useRef<{ mx: number; my: number; vx: number; vy: number } | null>(null);
  const [view, _setView] = useState<View>(INIT_VIEW);

  function setView(v: View) { viewRef.current = v; _setView(v); }

  // SVG-coordinate mouse position
  function toSvg(cx: number, cy: number): [number, number] {
    const el = svgRef.current;
    if (!el) return [cx, cy];
    const r = el.getBoundingClientRect();
    return [(cx - r.left) / r.width * W, (cy - r.top) / r.height * H];
  }

  // Wheel zoom (non-passive, toward cursor)
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const v = viewRef.current;
      const [mx, my] = toSvg(e.clientX, e.clientY);
      const cx = (mx - v.x) / v.scale;
      const cy = (my - v.y) / v.scale;
      const factor = e.deltaY < 0 ? 1.15 : 0.87;
      const ns = Math.min(Math.max(v.scale * factor, 0.35), 8);
      setView({ scale: ns, x: mx - cx * ns, y: my - cy * ns });
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

  function onMouseDown(e: React.MouseEvent) {
    const [mx, my] = toSvg(e.clientX, e.clientY);
    dragRef.current = { mx, my, vx: view.x, vy: view.y };
  }
  function onMouseMove(e: React.MouseEvent) {
    if (!dragRef.current) return;
    const [mx, my] = toSvg(e.clientX, e.clientY);
    const { mx: sx, my: sy, vx, vy } = dragRef.current;
    setView({ ...viewRef.current, x: vx + (mx - sx), y: vy + (my - sy) });
  }
  function onMouseUp()    { dragRef.current = null; }
  function onMouseLeave() { dragRef.current = null; }

  const isAlert  = ride.state === 'blocked' || ride.state === 'hazard';
  const alertClr = isAlert ? ALERT_CLR[ride.state] : null;
  const carColor = alertClr ?? '#3b82f6';
  const progress = Math.min(ride.carPosition.x / 100, 0.99);
  const [cx, cy] = carPos(progress);

  const gTransform = `translate(${view.x} ${view.y}) scale(${view.scale})`;

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-label">Live Map</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {isAlert && (
            <span style={{ fontSize: '10px', fontWeight: 600, padding: '2px 7px', borderRadius: '3px', color: alertClr!, background: `${alertClr!}18`, border: `1px solid ${alertClr!}35` }}>
              {ride.state === 'blocked' ? 'STOPPED' : 'HAZARD'}
            </span>
          )}
          <span className="panel-meta">scroll/drag</span>
          <button
            onClick={() => setView(INIT_VIEW)}
            style={{ fontSize: '10px', padding: '2px 7px', borderRadius: '3px', background: 'var(--s3)', border: '1px solid var(--border)', color: 'var(--text-3)', cursor: 'pointer' }}
          >
            Reset
          </button>
        </div>
      </div>

      <div style={{ padding: '10px 10px 6px' }}>
        <div style={{ position: 'relative', borderRadius: '4px', overflow: 'hidden', border: '1px solid var(--border-subtle)', background: 'var(--s0)', aspectRatio: `${W}/${H}` }}>
          <svg
            ref={svgRef}
            viewBox={`0 0 ${W} ${H}`}
            style={{ width: '100%', height: '100%', display: 'block', cursor: dragRef.current ? 'grabbing' : 'grab', userSelect: 'none' }}
            onMouseDown={onMouseDown}
            onMouseMove={onMouseMove}
            onMouseUp={onMouseUp}
            onMouseLeave={onMouseLeave}
          >
            <g transform={gTransform}>
              {/* City blocks */}
              {ROWS.slice(0, -1).map((y1, ri) =>
                COLS.slice(0, -1).map((x1, ci) => (
                  <rect key={`${ci}-${ri}`} x={x1 + 6} y={y1 + 6}
                    width={COLS[ci + 1] - x1 - 12} height={ROWS[ri + 1] - y1 - 12}
                    fill="#0c0f1a" rx="2" />
                ))
              )}

              {/* Street beds (horizontal) */}
              {ROWS.map((y, i) => (
                <line key={`h${i}`} x1="20" y1={y} x2={W - 20} y2={y} stroke="#141928" strokeWidth="10" />
              ))}
              {/* Street beds (vertical) */}
              {COLS.map((x, i) => (
                <line key={`v${i}`} x1={x} y1="20" x2={x} y2={H - 20} stroke="#141928" strokeWidth="10" />
              ))}

              {/* Street center lines (horizontal) */}
              {ROWS.map((y, i) => (
                <line key={`hc${i}`} x1="20" y1={y} x2={W - 20} y2={y} stroke="#1c2238" strokeWidth="1" strokeDasharray="8 6" />
              ))}
              {/* Street center lines (vertical) */}
              {COLS.map((x, i) => (
                <line key={`vc${i}`} x1={x} y1="20" x2={x} y2={H - 20} stroke="#1c2238" strokeWidth="1" strokeDasharray="8 6" />
              ))}

              {/* Street name labels (horizontal streets) */}
              {ROW_NAMES.map((name, i) => (
                <text key={name} x="22" y={ROWS[i] - 5} fontSize="9" fill="#252e45" fontFamily="monospace">{name}</text>
              ))}
              {/* Street name labels (vertical streets) */}
              {COL_NAMES.map((name, i) => (
                <text key={name} x={COLS[i]} y="15" fontSize="9" fill="#252e45" fontFamily="monospace" textAnchor="middle">{name}</text>
              ))}

              {/* Full route (unvisited) */}
              <path d={FULL_PATH} fill="none" stroke="#1a3060" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
              {/* Traveled */}
              <path d={traveledPath(progress)} fill="none" stroke="#3b82f6" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />

              {/* Pickup dot */}
              <circle cx={PICKUP[0]} cy={PICKUP[1]} r="6" fill="#1e2535" stroke="#475569" strokeWidth="1.5" />
              <circle cx={PICKUP[0]} cy={PICKUP[1]} r="3" fill="#64748b" />
              <text x={PICKUP[0] + 10} y={PICKUP[1] + 4} fontSize="9" fill="#475569" fontFamily="monospace">PICKUP</text>

              {/* Destination pin */}
              <circle cx={DEST[0]} cy={DEST[1]} r="8" fill="#052e1e" stroke="#10b981" strokeWidth="1.5" />
              <circle cx={DEST[0]} cy={DEST[1]} r="3.5" fill="#10b981" />
              <circle cx={DEST[0]} cy={DEST[1]} r="14" fill="none" stroke="#10b981" strokeWidth="1" opacity="0.3" />
              <text x={DEST[0] - 9} y={DEST[1] - 14} fontSize="9" fill="#10b981" fontFamily="monospace">DEST</text>

              {/* Alert glow */}
              {isAlert && (
                <>
                  <circle cx={cx} cy={cy} r="22" fill={carColor} opacity="0.05" />
                  <circle cx={cx} cy={cy} r="13" fill={carColor} opacity="0.1" />
                </>
              )}
              {/* Car */}
              <circle cx={cx} cy={cy} r="6" fill={carColor} />
              <circle cx={cx} cy={cy} r="10" fill="none" stroke={carColor} strokeWidth="1.5" opacity="0.55" />
            </g>
          </svg>
        </div>

        {/* Stats row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '6px', fontFamily: 'var(--mono)', fontSize: '10px', color: 'var(--text-4)' }}>
          <span>PROGRESS <span style={{ color: 'var(--text-3)' }}>{ride.carPosition.x.toFixed(0)}%</span></span>
          <span>SPEED <span style={{ color: 'var(--text-3)' }}>{ride.state === 'blocked' || ride.state === 'hazard' || ride.state === 'arrived' ? '0' : '35'} mph</span></span>
          <span>ZOOM <span style={{ color: 'var(--text-3)' }}>{view.scale.toFixed(1)}×</span></span>
        </div>
      </div>
    </div>
  );
}
