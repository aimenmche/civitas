import { useEffect, useState } from 'react'
import { Loader2, Plus, AlertTriangle, RefreshCw, X } from 'lucide-react'
import { useStore } from './store'
import { useSimulationSocket } from './hooks/useSimulationSocket'
import { Sidebar, Topbar } from './components/Layout'
import { Inspector } from './components/Inspector'
import { CreateRunModal } from './components/CreateRunModal'
import { OverviewPage } from './pages/Overview'
import { WorldPage } from './pages/World'
import { AgentsPage } from './pages/Agents'
import { SettlementsPage } from './pages/Settlements'
import { EconomyPage } from './pages/Economy'
import { PoliticsPage } from './pages/Politics'
import { CulturePage } from './pages/Culture'
import { TechnologyPage } from './pages/Technology'
import { DiplomacyPage } from './pages/Diplomacy'
import { HistoryPage } from './pages/History'
import { EmergencePage } from './pages/Emergence'
import { ExperimentsPage } from './pages/Experiments'
import { MultiversePage } from './pages/Multiverse'
import { SettingsPage } from './pages/Settings'

export default function App() {
  const page = useStore((s) => s.page)
  const bootstrap = useStore((s) => s.bootstrap)
  const bootstrapped = useStore((s) => s.bootstrapped)
  const loading = useStore((s) => s.loading)
  const state = useStore((s) => s.state)
  const runs = useStore((s) => s.runs)
  const error = useStore((s) => s.error)
  const simError = useStore((s) => s.simError)
  const clearError = useStore((s) => s.clearError)
  const [createOpen, setCreateOpen] = useState(false)

  useSimulationSocket()

  useEffect(() => {
    void bootstrap()
  }, [bootstrap])

  useEffect(() => {
    if (runs.length === 0 && bootstrapped && !loading) setCreateOpen(true)
  }, [runs.length, bootstrapped, loading])

  return (
    <div className="relative z-10 flex h-full flex-col overflow-hidden">
      <div className="flex min-h-0 flex-1">
        <Sidebar onCreate={() => setCreateOpen(true)} />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar onCreate={() => setCreateOpen(true)} />
          {state?.run.status === 'ended' && (
            <div className="flex shrink-0 items-center justify-between gap-3 border-b border-danger/30 bg-[#1a0f14] px-5 py-2">
              <div className="flex min-w-0 items-center gap-2 text-[11px]">
                <AlertTriangle size={13} className="shrink-0 text-danger" />
                <span className="font-mono uppercase tracking-[0.18em] text-danger">simulation ended</span>
                <span className="truncate text-dim">
                  · no living agents remain · world stopped on day {state.run.day}
                </span>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <button type="button" className="btn" onClick={() => setCreateOpen(true)}>
                  <Plus size={12} /> New world
                </button>
              </div>
            </div>
          )}
          <main className="relative min-h-0 flex-1">
            {!bootstrapped && loading && (
              <div className="flex h-full items-center justify-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em] text-dim">
                <Loader2 size={14} className="animate-spin" /> opening the observatory
              </div>
            )}
            {bootstrapped && !state && !loading && (
              <div className="flex h-full items-center justify-center p-6">
                <div className="panel max-w-lg px-8 py-10 text-center">
                  <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-amber/40 bg-amber/10 font-mono text-lg font-bold text-amber">C</div>
                  <h2 className="text-[20px] font-semibold text-fg">No world exists yet</h2>
                  <p className="mx-auto mt-2 max-w-sm text-[12px] leading-relaxed text-muted">
                    CIVITAS needs a seed, a continent and a handful of people. Everything after that is up to them.
                  </p>
                  <button type="button" className="btn-primary mx-auto mt-5" onClick={() => setCreateOpen(true)}>
                    <Plus size={13} /> Create the first world
                  </button>
                </div>
              </div>
            )}
            {state && (
              <div className="h-full">
                {page === 'overview' && <OverviewPage />}
                {page === 'world' && <WorldPage />}
                {page === 'agents' && <AgentsPage />}
                {page === 'settlements' && <SettlementsPage />}
                {page === 'economy' && <EconomyPage />}
                {page === 'politics' && <PoliticsPage />}
                {page === 'culture' && <CulturePage />}
                {page === 'technology' && <TechnologyPage />}
                {page === 'diplomacy' && <DiplomacyPage />}
                {page === 'history' && <HistoryPage />}
                {page === 'emergence' && <EmergencePage />}
                {page === 'experiments' && <ExperimentsPage />}
                {page === 'multiverse' && <MultiversePage />}
                {page === 'settings' && <SettingsPage />}
              </div>
            )}
          </main>
        </div>
        <Inspector />
      </div>

      {(error || simError) && (
        <div className="absolute bottom-4 left-1/2 z-40 flex max-w-xl -translate-x-1/2 items-start gap-2 rounded-lg border border-danger/35 bg-[#1a0f14] px-3 py-2 shadow-2xl">
          <AlertTriangle size={14} className="mt-0.5 shrink-0 text-danger" />
          <div className="min-w-0">
            <div className="text-[11px] font-medium text-danger">Something went wrong</div>
            <div className="mt-0.5 break-words text-[10.5px] leading-relaxed text-muted">{simError ?? error}</div>
          </div>
          <button type="button" className="btn-ghost shrink-0 p-1" onClick={clearError}><X size={12} /></button>
        </div>
      )}

      <CreateRunModal open={createOpen} onClose={() => setCreateOpen(false)} />
      {loading && bootstrapped && (
        <div className="pointer-events-none fixed right-4 top-16 z-30 flex items-center gap-1.5 rounded border border-edge bg-panel/90 px-2 py-1 font-mono text-[9px] uppercase tracking-wider text-dim">
          <RefreshCw size={10} className="animate-spin" /> syncing
        </div>
      )}
    </div>
  )
}
