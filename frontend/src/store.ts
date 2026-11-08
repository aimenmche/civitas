import { create } from 'zustand'
import { api, ApiError } from './api'
import type {
  AgentDetail,
  AgentSummary,
  FullState,
  MetricsPoint,
  Page,
  RunSummary,
  SettlementDetail,
  SimEvent,
  SnapshotInfo,
  SocketPayload,
  TechnologyView,
  WorldConfig,
  WorldData,
} from './types'

interface AppStore {
  page: Page
  runs: RunSummary[]
  currentRunId: string | null
  state: FullState | null
  world: WorldData | null
  metrics: MetricsPoint[]
  events: SimEvent[]
  technology: TechnologyView | null
  snapshots: SnapshotInfo[]
  selectedAgentId: string | null
  selectedSettlementId: string | null
  agentDetail: AgentDetail | null
  settlementDetail: SettlementDetail | null
  loading: boolean
  bootstrapped: boolean
  error: string | null
  socketStatus: 'offline' | 'connecting' | 'live' | 'error'
  simError: string | null

  setPage: (page: Page) => void
  bootstrap: () => Promise<void>
  selectRun: (runId: string) => Promise<void>
  refreshRuns: () => Promise<void>
  refreshState: () => Promise<void>
  refreshWorld: () => Promise<void>
  refreshMetrics: () => Promise<void>
  refreshEvents: () => Promise<void>
  refreshTechnology: () => Promise<void>
  refreshSnapshots: () => Promise<void>
  setSocketStatus: (status: AppStore['socketStatus']) => void
  handleSocket: (payload: SocketPayload) => void
  selectAgent: (agentId: string | null) => Promise<void>
  reloadAgent: () => Promise<void>
  selectSettlement: (settlementId: string | null) => Promise<void>
  reloadSettlement: () => Promise<void>
  control: (action: 'pause' | 'resume' | 'step' | 'speed', speed?: number) => Promise<void>
  createRun: (config: Partial<WorldConfig>, note?: string) => Promise<RunSummary>
  deleteRun: (runId: string) => Promise<void>
  branchRun: (snapshotId: string | null, note: string) => Promise<RunSummary>
  clearError: () => void
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return String(error)
}

export const useStore = create<AppStore>((set, get) => ({
  page: 'overview',
  runs: [],
  currentRunId: null,
  state: null,
  world: null,
  metrics: [],
  events: [],
  technology: null,
  snapshots: [],
  selectedAgentId: null,
  selectedSettlementId: null,
  agentDetail: null,
  settlementDetail: null,
  loading: false,
  bootstrapped: false,
  error: null,
  socketStatus: 'offline',
  simError: null,

  setPage: (page) => set({ page }),

  bootstrap: async () => {
    if (get().loading) return
    set({ loading: true, error: null })
    try {
      const runs = await api.listRuns()
      set({ runs, bootstrapped: true, loading: false })
      if (!get().currentRunId && runs.length > 0) {
        await get().selectRun(runs[0].id)
      }
    } catch (error) {
      set({ error: errorMessage(error), loading: false, bootstrapped: true })
    }
  },

  selectRun: async (runId) => {
    set({
      currentRunId: runId,
      state: null,
      world: null,
      metrics: [],
      events: [],
      technology: null,
      snapshots: [],
      agentDetail: null,
      settlementDetail: null,
      selectedAgentId: null,
      selectedSettlementId: null,
      error: null,
      simError: null,
    })
    try {
      const [state, world, metrics, events, technology, snapshots] = await Promise.all([
        api.getState(runId),
        api.getWorld(runId),
        api.getMetrics(runId),
        api.getEvents(runId, undefined, 200),
        api.getTechnology(runId),
        api.listSnapshots(runId),
      ])
      set({ state, world, metrics, events, technology, snapshots })
    } catch (error) {
      set({ error: errorMessage(error) })
    }
  },

  refreshRuns: async () => {
    try {
      set({ runs: await api.listRuns() })
    } catch (error) {
      set({ error: errorMessage(error) })
    }
  },

  refreshState: async () => {
    const runId = get().currentRunId
    if (!runId) return
    try {
      set({ state: await api.getState(runId) })
    } catch (error) {
      set({ error: errorMessage(error) })
    }
  },

  refreshWorld: async () => {
    const runId = get().currentRunId
    if (!runId) return
    try {
      set({ world: await api.getWorld(runId) })
    } catch (error) {
      set({ error: errorMessage(error) })
    }
  },

  refreshMetrics: async () => {
    const runId = get().currentRunId
    if (!runId) return
    try {
      set({ metrics: await api.getMetrics(runId) })
    } catch (error) {
      set({ error: errorMessage(error) })
    }
  },

  refreshEvents: async () => {
    const runId = get().currentRunId
    if (!runId) return
    try {
      set({ events: await api.getEvents(runId, undefined, 200) })
    } catch (error) {
      set({ error: errorMessage(error) })
    }
  },

  refreshTechnology: async () => {
    const runId = get().currentRunId
    if (!runId) return
    try {
      set({ technology: await api.getTechnology(runId) })
    } catch (error) {
      set({ error: errorMessage(error) })
    }
  },

  refreshSnapshots: async () => {
    const runId = get().currentRunId
    if (!runId) return
    try {
      set({ snapshots: await api.listSnapshots(runId) })
    } catch (error) {
      set({ error: errorMessage(error) })
    }
  },

  setSocketStatus: (socketStatus) => set({ socketStatus }),

  handleSocket: (payload) => {
    if (payload.type === 'state') {
      const full = payload.state
      set({
        state: full,
        currentRunId: full.run.id,
        metrics: full.metrics_history ?? get().metrics,
        events: full.events ?? get().events,
        technology: full.technology
          ? ({ ...(get().technology ?? {}), ...full.technology } as typeof full.technology)
          : get().technology,
      })
      return
    }
    if (payload.type === 'tick') {
      const current = get().state
      if (!current || payload.run_id !== current.run.id) return
      const eventMap = new Map(get().events.map((event) => [event.id, event]))
      for (const event of payload.events) eventMap.set(event.id, event)
      const events = Array.from(eventMap.values())
        .sort((a, b) => a.day - b.day)
        .slice(-400)
      const state: FullState = {
        ...current,
        run: {
          ...current.run,
          day: payload.day,
          tick: payload.tick,
          year: payload.year,
          season: payload.season,
          day_of_season: payload.day_of_season,
          time_label: payload.time_label,
          weather: payload.weather,
          status: payload.status,
          population: payload.population,
          births: payload.births,
          deaths: payload.deaths,
        },
        metrics: payload.metrics,
        agents: payload.agents,
        settlements: payload.settlements,
      }
      const runs = get().runs.map((run) =>
        run.id === payload.run_id
          ? {
              ...run,
              day: payload.day,
              population: payload.population,
              settlements: payload.settlements.length,
              status: payload.status,
            }
          : run,
      )
      set({
        state,
        events,
        metrics: [...get().metrics, payload.metrics].slice(-1500),
        runs,
        simError: null,
      })
      return
    }
    if (payload.type === 'status') {
      const current = get().state
      if (current && payload.run_id === current.run.id) {
        set({ state: { ...current, run: { ...current.run, status: payload.status, day: payload.day } } })
      }
      set({
        runs: get().runs.map((run) =>
          run.id === payload.run_id
            ? { ...run, status: payload.status, day: payload.day, speed: payload.speed ?? run.speed }
            : run,
        ),
      })
      return
    }
    if (payload.type === 'error') {
      set({ simError: payload.error, error: payload.error })
    }
  },

  selectAgent: async (agentId) => {
    set({ selectedAgentId: agentId, agentDetail: null })
    if (!agentId) return
    const runId = get().currentRunId
    if (!runId) return
    try {
      set({ agentDetail: await api.getAgent(runId, agentId) })
    } catch (error) {
      set({ error: errorMessage(error) })
    }
  },

  reloadAgent: async () => {
    const runId = get().currentRunId
    const agentId = get().selectedAgentId
    if (!runId || !agentId) return
    try {
      set({ agentDetail: await api.getAgent(runId, agentId) })
    } catch {
      // A dead agent can disappear from a branch; keep the last detail.
    }
  },

  selectSettlement: async (settlementId) => {
    set({ selectedSettlementId: settlementId, settlementDetail: null, selectedAgentId: null, agentDetail: null })
    if (!settlementId) return
    const runId = get().currentRunId
    if (!runId) return
    try {
      set({ settlementDetail: await api.getSettlement(runId, settlementId) })
    } catch (error) {
      set({ error: errorMessage(error) })
    }
  },

  reloadSettlement: async () => {
    const runId = get().currentRunId
    const settlementId = get().selectedSettlementId
    if (!runId || !settlementId) return
    try {
      set({ settlementDetail: await api.getSettlement(runId, settlementId) })
    } catch {
      // Ignore transient refetch failures.
    }
  },

  control: async (action, speed) => {
    const runId = get().currentRunId
    if (!runId) return
    try {
      const result = await api.control(runId, action, speed)
      const current = get().state
      if (current) {
        set({ state: { ...current, run: { ...current.run, status: result.status, day: result.day } } })
      }
      set({
        runs: get().runs.map((run) =>
          run.id === runId
            ? { ...run, status: result.status, day: result.day, speed: result.speed ?? run.speed }
            : run,
        ),
      })
    } catch (error) {
      set({ error: errorMessage(error) })
    }
  },

  createRun: async (config, note = '') => {
    const run = await api.createRun(config, note)
    set({ runs: [run, ...get().runs.filter((item) => item.id !== run.id)] })
    await get().selectRun(run.id)
    return run
  },

  deleteRun: async (runId) => {
    await api.deleteRun(runId)
    const runs = get().runs.filter((run) => run.id !== runId)
    set({ runs })
    if (get().currentRunId === runId) {
      set({
        currentRunId: null, state: null, world: null, metrics: [], events: [],
        technology: null, snapshots: [], agentDetail: null, settlementDetail: null,
        selectedAgentId: null, selectedSettlementId: null,
      })
      if (runs.length > 0) await get().selectRun(runs[0].id)
    }
  },

  branchRun: async (snapshotId, note) => {
    const runId = get().currentRunId
    if (!runId) throw new Error('No active run')
    const run = await api.branchRun(runId, snapshotId, note)
    set({ runs: [run, ...get().runs.filter((item) => item.id !== run.id)] })
    await get().selectRun(run.id)
    return run
  },

  clearError: () => set({ error: null, simError: null }),
}))

export function agentById(state: FullState | null, id: string | null): AgentSummary | undefined {
  if (!state || !id) return undefined
  return state.agents.find((agent) => agent.id === id)
}
