import type { RideInfo, RideState } from '../mockData';

const STATE_LABELS: Record<RideState, string> = {
  idle: 'IDLE', en_route: 'EN ROUTE', blocked: 'BLOCKED',
  hazard: 'HAZARD', rerouting: 'REROUTING', arrived: 'ARRIVED',
};

function formatEta(s: number) {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return m > 0 ? `${m}m ${sec.toString().padStart(2, '0')}s` : `${sec}s`;
}

function Row({ label, value, mono = false, accent = false }: {
  label: string; value: string; mono?: boolean; accent?: boolean;
}) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '12px', padding: '5px 0', borderBottom: '1px solid var(--border-subtle)' }}>
      <span style={{ fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-3)', flexShrink: 0 }}>
        {label}
      </span>
      <span style={{
        fontSize: '12px',
        color: accent ? 'var(--sc)' : 'var(--text-1)',
        fontFamily: mono ? 'var(--mono)' : 'var(--sans)',
        textAlign: 'right',
        wordBreak: 'break-word',
        minWidth: 0,
      }}>
        {value}
      </span>
    </div>
  );
}

export function RideStatus({ ride }: { ride: RideInfo }) {
  return (
    <div className={`panel state-${ride.state}`}>
      <div className="panel-header">
        <span className="panel-label">Ride Status</span>
        <span className="panel-meta">{ride.rideId}</span>
      </div>

      <div style={{ margin: '12px 12px 0', padding: '8px 10px', borderRadius: '4px', background: 'var(--se)', border: '1px solid color-mix(in srgb, var(--sc) 25%, transparent)', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span className="blink" style={{ width: '7px', height: '7px', borderRadius: '50%', background: 'var(--sc)', flexShrink: 0, display: 'inline-block' }} />
        <span style={{ fontSize: '11px', fontWeight: 600, letterSpacing: '0.12em', color: 'var(--sc)' }}>
          {STATE_LABELS[ride.state]}
        </span>
        {ride.blockedReason && (
          <span style={{ fontSize: '11px', color: 'var(--text-2)', marginLeft: '2px' }}>
            — {ride.blockedReason}
          </span>
        )}
      </div>

      <div style={{ padding: '4px 12px 12px' }}>
        <Row label="Passenger" value={ride.passengerName} />
        <Row label="Phone" value={ride.passengerPhone} mono />
        <Row label="ETA" value={ride.state === 'arrived' ? 'Arrived' : formatEta(ride.eta)} mono accent />
        <Row label="Pickup" value={ride.pickup} />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '12px', padding: '5px 0' }}>
          <span style={{ fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-3)', flexShrink: 0 }}>Drop-off</span>
          <span style={{ fontSize: '12px', color: 'var(--text-1)', textAlign: 'right', wordBreak: 'break-word', minWidth: 0 }}>{ride.destination}</span>
        </div>
      </div>
    </div>
  );
}
