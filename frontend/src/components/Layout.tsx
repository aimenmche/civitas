import { useEffect, useMemo, useState } from 'react'
import { ChevronRight, FlaskConical, Play, Pause, SkipForward, Plus, Circle, Settings2 } from 'lucide-react'
import clsx from 'clsx'
import type { Page } from '../types'
import { useStore } from '../store'
import { fmt, pct, happinessTone, presetName } from '../lib/format'
import { Badge } from './ui'

const NAV: Array<{ id: Page; label: string; icon: typeof Circle }> = [
  { id: 'overview', label: 'Overview', icon: Circle },
  { id: 'world', label: 'World map', icon: Circle },
  { id: 'agents', label: 'Agents', icon: Circle },
  { id: 'settlements', label: 'Settlements', icon: Circle },
  { id: 'economy', label: 'Economy', icon: Circle },
  { id: 'politics', label: 'Politics', icon: Circle },
  { id: 'culture', label: 'Culture', icon: Circle },
  { id: 'technology', label: 'Technology', icon: Circle },
  { id: 'diplomacy', label: 'Diplomacy', icon: Circle },
  { id: 'history', label: 'History', icon: Circle },
  { id: 'emergence', label: 'Emergence', icon: Circle },
  { id: 'experiments', label: 'Experiments', icon: Circle },
  { id: 'multiverse', label: 'Multiverse', icon: Circle },
  { id: 'settings', label: 'Settings', icon: Circle },
]

const PAGE_TITLES: Record<Page, string> = {
  overview: 'Overview',
  world: 'World map',
  agents: 'Agents',
  settlements: 'Settlements',
  economy: 'Economy',
  politics: 'Politics',
  culture: 'Culture',
  technology: 'Technology',
  diplomacy: 'Diplomacy',
  history: 'History',
  emergence: 'Emergence',
  experiments: 'Experiments',
  multiverse: 'Multiverse',
  settings: 'Settings',
}

export function Sidebar({ onCreate }: { onCreate: () => void }) {
  const page = useStore((state) => state.page)
  const setPage = useStore((state) => state.setPage)
  const state = useStore((state) => state.state)
  const runs = useStore((state) => state.runs)
  const currentRunId = useStore((state) => state.currentRunId)
  const selectRun = useStore((state) => state.selectRun)

  return (
    <aside className="relative z-10 flex w-[214px] shrink-0 flex-col border-r border-edge bg-bg2">
      <div className="flex h-[62px] items-center gap-3 border-b border-edge px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-md border border-amber/40 bg-amber/10 font-mono text-[13px] font-bold text-amber">
          C
        </div>
        <div>
          <div className="font-mono text-[13px] font-semibold tracking-[0.24em] text-fg">CIVITAS</div>
          <div className="font-mono text-[9px] uppercase tracking-[0.18em] text-dim">civilization observatory</div>
        </div>
      </div>

      <div className="border-b border-edge px-3 py-3">
        <div className="eyebrow mb-1.5 px-1">Active world</div>
        <select
          className="input py-1.5 text-[12px]"
          value={currentRunId ?? ''}
          onChange={(event) => void selectRun(event.target.value)}
        >
          {runs.length === 0 && <option value="">No worlds yet</option>}
          {runs.map((run) => (
            <option key={run.id} value={run.id}>
              {run.world_name} · day {run.day}{run.status === 'ended' ? ' · ended' : ''}
            </option>
          ))}
        </select>
        <div className="mt-2 flex items-center justify-between px-1">
          <span className="font-mono text-[10px] text-dim">{state ? `seed ${state.run.seed}` : '—'}</span>
          <span className="font-mono text-[10px] text-dim">{runs.length} run{runs.length === 1 ? '' : 's'}</span>
        </div>
      </div>

      <nav className="scroll-area flex-1 space-y-0.5 px-2 py-3">
        {NAV.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setPage(item.id)}
            className={clsx('nav-item', page === item.id && 'nav-item-active')}
          >
            <span className={clsx('h-1.5 w-1.5 rounded-full', page === item.id ? 'bg-amber' : 'bg-dim/50')} />
            <span className="flex-1">{item.label}</span>
            {page === item.id && <ChevronRight size={12} className="text-amber" />}
          </button>
        ))}
      </nav>

      <div className="border-t border-edge p-3">
        <button type="button" onClick={onCreate} className="btn-primary w-full">
          <Plus size={13} /> New world
        </button>
        <div className="mt-3 flex items-center justify-between px-1">
          <span className="font-mono text-[9px] uppercase tracking-wider text-dim">engine v0.3.0</span>
          <span className="font-mono text-[9px] uppercase tracking-wider text-dim">deterministic</span>
        </div>
      </div>
    </aside>
  )
}

export function Topbar({ onCreate }: { onCreate: () => void }) {
  const page = useStore((state) => state.page)
  const state = useStore((state) => state.state)
  const runs = useStore((state) => state.runs)
  const currentRunId = useStore((state) => state.currentRunId)
  const socketStatus = useStore((state) => state.socketStatus)
  const control = useStore((state) => state.control)
  const [speedOpen, setSpeedOpen] = useState(false)
  const run = runs.find((item) => item.id === currentRunId)

  useEffect(() => {
    setSpeedOpen(false)
  }, [currentRunId])

  const status = state?.run.status ?? run?.status ?? 'paused'
  const speed = run?.speed ?? 1
  const weather = state?.run.weather
  const disaster = state?.run.disaster

  return (
    <header className="relative z-20 flex h-[62px] shrink-0 items-center justify-between gap-4 border-b border-edge bg-bg2 px-5">
      <div className="flex min-w-0 items-center gap-4">
        <div>
          <div className="font-mono text-[9px] uppercase tracking-[0.22em] text-dim">observatory / {page}</div>
          <div className="flex items-center gap-2">
            <h1 className="truncate text-[15px] font-semibold tracking-wide text-fg">{PAGE_TITLES[page]}</h1>
            {state && (
              <span className="hidden font-mono text-[10px] text-dim md:inline">
                {state.run.world_name} · seed {state.run.seed} · {presetName(state.run.config.preset)}
              </span>
            )}
          </div>
        </div>
        {disaster && (
          <Badge tone="danger" className="hidden lg:inline-flex">
            {disaster.kind} · severity {fmt(disaster.severity, 1)}
          </Badge>
        )}
      </div>

      <div className="flex items-center gap-3">
        {state && (
          <div className="hidden items-center gap-2 lg:flex">
            <Badge tone="muted">{weather ?? 'clear'}</Badge>
            <Badge tone="teal">{state.run.season}</Badge>
            <Badge tone="violet">year {state.run.year}</Badge>
          </div>
        )}
        <div className="hidden items-center gap-2 border-l border-edge pl-3 md:flex">
          <span className="font-mono text-[10px] uppercase tracking-wider text-muted">day</span>
          <span className="num text-[18px] font-semibold text-fg">{state ? fmt(state.run.day) : '—'}</span>
          <span className="font-mono text-[10px] text-dim">/ {state ? fmt(state.run.population) : '—'} alive</span>
          {status === 'ended' && <Badge tone="danger">ended</Badge>}
        </div>

        <div className="flex items-center gap-1 rounded-md border border-edge bg-panel/80 p-0.5">
          <button
            type="button"
            title={status === 'ended' ? 'This world has ended — no living agents remain' : status === 'running' ? 'Pause' : 'Resume'}
            className="btn-ghost px-2 text-fg"
            disabled={!state || status === 'ended'}
            onClick={() => void control(status === 'running' ? 'pause' : 'resume')}
          >
            {status === 'running' ? <Pause size={14} /> : <Play size={14} />}
          </button>
          <button
            type="button"
            title={status === 'ended' ? 'This world has ended — step is disabled' : 'Step one day'}
            className="btn-ghost px-2 text-fg"
            disabled={!state || status === 'ended'}
            onClick={() => void control('step')}
          >
            <SkipForward size={14} />
          </button>
          <div className="relative">
            <button
              type="button"
              className="btn-ghost px-2 font-mono text-[10px] text-fg"
              disabled={!state}
              onClick={() => setSpeedOpen((open) => !open)}
            >
              {speed}×
            </button>
            {speedOpen && (
              <div className="absolute right-0 top-8 z-30 w-24 rounded-md border border-edge bg-panel p-1 shadow-2xl">
                {[0.25, 0.5, 1, 2, 4].map((value) => (
                  <button
                    key={value}
                    type="button"
                    className={clsx('block w-full rounded px-2 py-1.5 text-left font-mono text-[11px] hover:bg-white/5', value === speed ? 'text-amber' : 'text-muted')}
                    onClick={() => {
                      void control('speed', value)
                      setSpeedOpen(false)
                    }}
                  >
                    {value}× speed
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <span
            className={clsx(
              'h-1.5 w-1.5 rounded-full',
              socketStatus === 'live' ? 'bg-good pulse-dot' : socketStatus === 'connecting' ? 'bg-amber' : 'bg-danger',
            )}
          />
          <span className="hidden font-mono text-[9px] uppercase tracking-wider text-dim xl:inline">{socketStatus}</span>
        </div>

        <button type="button" onClick={onCreate} className="btn hidden xl:inline-flex">
          <FlaskConical size={13} /> New run
        </button>
        {run && (
          <span className={clsx('hidden items-center gap-1 font-mono text-[10px] uppercase tracking-wider 2xl:flex', happinessTone(state?.metrics?.avg_happiness ?? 0))}>
            <Settings2 size={11} /> {status}
          </span>
        )}
        {state && <span className="hidden font-mono text-[10px] text-dim xl:inline">{pct(state.metrics.avg_happiness ?? 0)} happy</span>}
      </div>
    </header>
  )
}
