export type RideState = 'idle' | 'en_route' | 'blocked' | 'hazard' | 'rerouting' | 'arrived';

export type CallState = 'none' | 'calling' | 'in_call' | 'ended';

export type VlmEventType = 'en_route' | 'blocked' | 'hazard' | 'rerouting' | 'arrived';

export interface VlmEvent {
  id: string;
  timestamp: Date;
  type: VlmEventType;
  reason: string;
  confidence: number;
  frameId: number;
}

export interface CallTranscriptEntry {
  id: string;
  timestamp: Date;
  speaker: 'agent' | 'passenger';
  text: string;
}

export interface EventLogEntry {
  id: string;
  timestamp: Date;
  category: 'vlm' | 'call' | 'system' | 'ride';
  message: string;
  severity: 'info' | 'warn' | 'error' | 'success';
}

export interface RideInfo {
  rideId: string;
  passengerName: string;
  passengerPhone: string;
  pickup: string;
  destination: string;
  eta: number; // seconds
  state: RideState;
  callState: CallState;
  callDuration: number; // seconds
  vlmEvents: VlmEvent[];
  transcript: CallTranscriptEntry[];
  eventLog: EventLogEntry[];
  carPosition: { x: number; y: number }; // 0-100 along route
  blockedReason?: string;
}

let frameCounter = 0;

export const VLM_EVENTS_POOL: Record<VlmEventType, Array<{ reason: string }>> = {
  en_route: [
    { reason: 'Clear road ahead, proceeding at 35 mph' },
    { reason: 'Green light, intersection clear' },
    { reason: 'Lane free, maintaining route' },
    { reason: 'No obstacles detected in 200m radius' },
    { reason: 'Smooth road conditions, speed limit 40 mph' },
  ],
  blocked: [
    { reason: 'Double-parked delivery truck blocking lane' },
    { reason: 'Construction zone ahead, lane closed' },
    { reason: 'Stopped vehicle in path, no bypass available' },
  ],
  hazard: [
    { reason: 'Debris detected in roadway' },
    { reason: 'Pedestrian stepping into crosswalk unexpectedly' },
    { reason: 'Road surface damage detected' },
  ],
  rerouting: [
    { reason: 'Traffic congestion, alternate route via Mission St' },
    { reason: 'Road closure ahead, recalculating via 3rd Ave' },
  ],
  arrived: [
    { reason: 'Destination landmark confirmed, passenger dropzone clear' },
    { reason: 'GPS confirms arrival within 15m of destination' },
  ],
};

export const CALL_SCRIPTS: Record<string, CallTranscriptEntry[]> = {
  blocked: [
    { id: 'c1', timestamp: new Date(), speaker: 'agent', text: "Hi, this is your Waymo. I'm currently blocked by a delivery truck at 5th and Market. Estimated delay is 3 minutes." },
    { id: 'c2', timestamp: new Date(), speaker: 'passenger', text: "Okay, should I come out now or wait inside?" },
    { id: 'c3', timestamp: new Date(), speaker: 'agent', text: "I'd suggest waiting inside — I'll notify you once I've cleared the blockage and I'm within 30 seconds of your location." },
    { id: 'c4', timestamp: new Date(), speaker: 'passenger', text: "Sounds good, thanks." },
    { id: 'c5', timestamp: new Date(), speaker: 'agent', text: "Perfect. I'll call again when I'm ready. Have a good day!" },
  ],
  arrived: [
    { id: 'a1', timestamp: new Date(), speaker: 'agent', text: "Hello! Your Waymo has arrived at 123 Main Street. I'm parked in the white zone." },
    { id: 'a2', timestamp: new Date(), speaker: 'passenger', text: "Great, I'll be right out in 2 minutes." },
    { id: 'a3', timestamp: new Date(), speaker: 'agent', text: "No problem, I'll wait. Your door is on the curb side. Safe travels!" },
  ],
  hazard: [
    { id: 'h1', timestamp: new Date(), speaker: 'agent', text: "Hi, I've detected a road hazard and stopped for your safety. There's debris in the roadway on Valencia St." },
    { id: 'h2', timestamp: new Date(), speaker: 'passenger', text: "Is everything okay?" },
    { id: 'h3', timestamp: new Date(), speaker: 'agent', text: "Yes, everything is fine. I'm waiting for the obstacle to clear. Updated ETA is 8 minutes." },
  ],
};

function uid() {
  return Math.random().toString(36).slice(2, 9);
}

export function makeVlmEvent(type: VlmEventType): VlmEvent {
  const pool = VLM_EVENTS_POOL[type];
  const entry = pool[Math.floor(Math.random() * pool.length)];
  return {
    id: uid(),
    timestamp: new Date(),
    type,
    reason: entry.reason,
    confidence: 0.85 + Math.random() * 0.14,
    frameId: ++frameCounter,
  };
}

export function makeLogEntry(
  category: EventLogEntry['category'],
  message: string,
  severity: EventLogEntry['severity'] = 'info'
): EventLogEntry {
  return { id: uid(), timestamp: new Date(), category, message, severity };
}

export const INITIAL_RIDE: RideInfo = {
  rideId: 'WMO-2847',
  passengerName: 'Alex Chen',
  passengerPhone: '+1 (415) 555-0182',
  pickup: '101 Market St, SF',
  destination: '123 Main St, SF',
  eta: 420,
  state: 'en_route',
  callState: 'none',
  callDuration: 0,
  vlmEvents: [
    makeVlmEvent('en_route'),
    makeVlmEvent('en_route'),
  ],
  transcript: [],
  eventLog: [
    makeLogEntry('system', 'Banana Taxi dispatch initialized', 'info'),
    makeLogEntry('ride', 'Ride WMO-2847 started — passenger: Alex Chen', 'success'),
    makeLogEntry('vlm', 'Gemini Live session opened', 'info'),
    makeLogEntry('ride', 'En route to 123 Main St', 'info'),
  ],
  carPosition: { x: 10, y: 50 },
};
