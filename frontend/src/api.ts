import { INITIAL_RIDE, makeLogEntry, type CallTranscriptEntry, type EventLogEntry, type RideInfo, type VlmEvent } from './mockData';

type DashboardResponse = {
  rideId: string;
  passengerName: string;
  passengerPhone: string;
  pickup: string;
  destination: string;
  state: RideInfo['state'];
  callState: RideInfo['callState'];
  callDuration: number;
  transcript: Array<Omit<CallTranscriptEntry, 'timestamp'> & { timestamp: string }>;
  eventLog: Array<Omit<EventLogEntry, 'timestamp'> & { timestamp: string }>;
  lastEvent: (Omit<VlmEvent, 'timestamp'> & { timestamp: string }) | null;
  frame: { sequence: number; timestamp: string; source: string; sizeBytes: number } | null;
  vehicle: { x: number; y: number; z: number; yaw: number; speedMps: number; timestamp: string } | null;
  map: CarlaMap | null;
  camera: { snapshotUrl: string; streamUrl: string; available: boolean };
  integrations: { carla: boolean; gemini: boolean; agentphone: boolean };
};

export type CarlaMap = {
  name: string;
  segments: Array<{ x1: number; y1: number; x2: number; y2: number; roadId: number; laneId: number }>;
  bounds: { minX: number; minY: number; maxX: number; maxY: number } | null;
};

export type DashboardRide = RideInfo & {
  cameraAvailable: boolean;
  cameraStreamUrl: string;
  integrations: DashboardResponse['integrations'];
  vehicleTelemetry: DashboardResponse['vehicle'];
  carlaMap: CarlaMap | null;
};

export async function fetchDashboard(): Promise<DashboardRide> {
  const response = await fetch('/api/dashboard');
  if (!response.ok) {
    throw new Error(`Dashboard request failed: ${response.status}`);
  }
  return normalizeDashboard(await response.json());
}

export async function submitTranscript(text: string): Promise<{ decision: string; reply: string }> {
  const response = await fetch('/api/transcript', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  if (!response.ok) {
    throw new Error(`Transcript request failed: ${response.status}`);
  }
  return response.json();
}

function normalizeDashboard(data: DashboardResponse): DashboardRide {
  const lastEvent = data.lastEvent ? reviveVlmEvent(data.lastEvent) : null;
  const vlmEvents = lastEvent ? [lastEvent] : [];
  const eventLog = data.eventLog.length > 0
    ? data.eventLog.map(reviveLogEntry)
    : [makeLogEntry('system', 'Connected to Omega backend', 'success')];

  return {
    ...INITIAL_RIDE,
    rideId: data.rideId,
    passengerName: data.passengerName,
    passengerPhone: data.passengerPhone,
    pickup: data.pickup,
    destination: data.destination,
    state: data.state,
    callState: data.callState,
    callDuration: data.callDuration,
    eta: data.state === 'arrived' ? 0 : INITIAL_RIDE.eta,
    vlmEvents,
    transcript: data.transcript.map(reviveTranscriptEntry),
    eventLog,
    carPosition: estimateCarPosition(data.state, data.vehicle, data.frame?.sequence ?? 0),
    cameraAvailable: data.camera.available,
    cameraStreamUrl: data.camera.streamUrl,
    integrations: data.integrations,
    vehicleTelemetry: data.vehicle,
    carlaMap: data.map,
  };
}

function reviveVlmEvent(event: DashboardResponse['lastEvent'] extends infer T ? NonNullable<T> : never): VlmEvent {
  return { ...event, timestamp: new Date(event.timestamp) };
}

function reviveTranscriptEntry(entry: DashboardResponse['transcript'][number]): CallTranscriptEntry {
  return { ...entry, timestamp: new Date(entry.timestamp) };
}

function reviveLogEntry(entry: DashboardResponse['eventLog'][number]): EventLogEntry {
  return { ...entry, timestamp: new Date(entry.timestamp) };
}

function estimateCarPosition(state: RideInfo['state'], vehicle: DashboardResponse['vehicle'], frameSequence: number) {
  if (state === 'arrived') return { x: 100, y: 50 };
  if (state === 'idle') return { x: 5, y: 50 };
  if (vehicle) {
    const x = clamp(((vehicle.x + 250) / 500) * 100, 3, 97);
    const y = clamp(((vehicle.y + 250) / 500) * 100, 3, 97);
    return { x, y };
  }
  const x = Math.min(95, 10 + (frameSequence % 560) / 7);
  return { x, y: 50 };
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}
