import type {
  AgentDetail,
  AgentSummary,
  EmergenceReport,
  FullState,
  MetricsPoint,
  RunSummary,
  SettlementDetail,
  SettlementSummary,
  SimEvent,
  SnapshotInfo,
  TechnologyView,
  WorldConfig,
  WorldData,
} from './types'

const API_BASE = import.meta.env.VITE_API_URL ?? '/api'

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

const DEDUPE_MS = 1000
const inflight = new Map<string, Promise<unknown>>()
const recent = new Map<string, { at: number; value: unknown }>()

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? 'GET').toUpperCase()
  const key = `${method} ${path}`
  // Pages refresh their detail data whenever the sim day changes. At 8x speed
  // that is several identical GETs per second; collapse them into one.
  if (method === 'GET') {
    const cached = recent.get(key)
    if (cached && Date.now() - cached.at < DEDUPE_MS) return cached.value as T
    const pending = inflight.get(key)
    if (pending) return pending as Promise<T>
  }
  const promise = (async () => {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
      ...init,
    })
    if (!response.ok) {
      let detail = response.statusText
      try {
        const body = await response.json()
        detail = body.detail ?? detail
      } catch {
        // ignore non-JSON bodies
      }
      throw new ApiError(detail, response.status)
    }
    const value = await response.json()
    if (method === 'GET') {
      recent.set(key, { at: Date.now(), value })
    } else {
      // A write can invalidate anything the pages are showing.
      recent.clear()
    }
    return value as T
  })()
  if (method === 'GET') {
    inflight.set(key, promise)
    promise.finally(() => inflight.delete(key)).catch(() => undefined)
  }
  return promise
}

export const api = {
  health: () => request<{ status: string; app: string; runs: number; database: string; llm: boolean }>('/health'),
  llmStatus: () => request<Record<string, unknown>>('/llm/status'),

  listRuns: () => request<RunSummary[]>('/runs'),
  createRun: (world: Partial<WorldConfig>, note = '') =>
    request<RunSummary>('/runs', {
      method: 'POST',
      body: JSON.stringify({ world, note }),
    }),
  deleteRun: (runId: string) => request<{ deleted: boolean }>(`/runs/${runId}`, { method: 'DELETE' }),
  getRun: (runId: string) => request<{ summary: RunSummary; state: FullState }>(`/runs/${runId}`),
  getState: (runId: string) => request<FullState>(`/runs/${runId}/state`),
  getWorld: (runId: string) => request<WorldData>(`/runs/${runId}/world`),
  control: (runId: string, action: 'pause' | 'resume' | 'step' | 'speed', speed?: number) =>
    request<{ status: string; day: number; speed?: number; stepped?: boolean }>(`/runs/${runId}/control`, {
      method: 'POST',
      body: JSON.stringify({ action, speed }),
    }),

  getAgents: (runId: string) => request<AgentSummary[]>(`/runs/${runId}/agents`),
  getAgent: (runId: string, agentId: string) => request<AgentDetail>(`/runs/${runId}/agents/${agentId}`),
  getSettlements: (runId: string) => request<SettlementSummary[]>(`/runs/${runId}/settlements`),
  getSettlement: (runId: string, settlementId: string) =>
    request<SettlementDetail>(`/runs/${runId}/settlements/${settlementId}`),
  getTechnology: (runId: string) => request<TechnologyView>(`/runs/${runId}/technology`),
  getEmergence: (runId: string) => request<EmergenceReport>(`/runs/${runId}/emergence`),
  getEvents: (runId: string, category?: string, limit = 150) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (category && category !== 'all') params.set('category', category)
    return request<SimEvent[]>(`/runs/${runId}/events?${params.toString()}`)
  },
  getMetrics: (runId: string, limit = 1200) => request<MetricsPoint[]>(`/runs/${runId}/metrics?limit=${limit}`),
  getHistory: (runId: string, category?: string, limit = 300) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (category && category !== 'all') params.set('category', category)
    return request<SimEvent[]>(`/runs/${runId}/history?${params.toString()}`)
  },

  listSnapshots: (runId: string) => request<SnapshotInfo[]>(`/runs/${runId}/snapshots`),
  createSnapshot: (runId: string, label: string) =>
    request<SnapshotInfo>(`/runs/${runId}/snapshots`, {
      method: 'POST',
      body: JSON.stringify({ label }),
    }),
  branchRun: (runId: string, snapshotId: string | null, note: string) =>
    request<RunSummary>(`/runs/${runId}/branch`, {
      method: 'POST',
      body: JSON.stringify({ snapshot_id: snapshotId, note }),
    }),
  compare: (runIds: string[]) =>
    request<{
      runs: RunSummary[]
      series: Array<{ run_id: string; name: string; points: MetricsPoint[] }>
    }>('/experiments/compare', {
      method: 'POST',
      body: JSON.stringify({ run_ids: runIds }),
    }),
  chronicle: (runId: string, kind = 'summary', days = 50) =>
    request<{ text: string; model: string; day: number }>(`/runs/${runId}/chronicle`, {
      method: 'POST',
      body: JSON.stringify({ kind, days }),
    }),
}

export function websocketUrl(runId: string): string {
  const explicit = import.meta.env.VITE_WS_URL
  if (explicit) return `${explicit}/api/ws/runs/${runId}`
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/ws/runs/${runId}`
}
