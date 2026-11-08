import { useMemo, useState } from 'react'
import { Camera, GitBranch, GitCompare, Globe2, Layers, Loader2, Play, Plus, Clock } from 'lucide-react'
import clsx from 'clsx'
import { useStore } from '../store'
import { api } from '../api'
import { Badge, EmptyState, Panel, StatCard } from '../components/ui'
import { fmt, presetName } from '../lib/format'
import type { RunSummary } from '../types'

function lineageDepth(run: RunSummary, byId: Map<string, RunSummary>): number {
  let depth = 0
  let current = run
  const seen = new Set<string>()
  while (current.parent_run_id && depth < 12) {
    if (seen.has(current.id)) break
    seen.add(current.id)
    const parent = byId.get(current.parent_run_id)
    if (!parent) break
    current = parent
    depth += 1
  }
  return depth
}

function statusTone(status: string): 'good' | 'amber' | 'danger' | 'muted' {
  if (status === 'running') return 'good'
  if (status === 'paused') return 'amber'
  if (status === 'ended') return 'danger'
  return 'muted'
}

export function MultiversePage() {
  const runs = useStore((s) => s.runs)
  const state = useStore((s) => s.state)
  const snapshots = useStore((s) => s.snapshots)
  const currentRunId = useStore((s) => s.currentRunId)
  const selectRun = useStore((s) => s.selectRun)
  const branchRun = useStore((s) => s.branchRun)
  const refreshSnapshots = useStore((s) => s.refreshSnapshots)
  const setPage = useStore((s) => s.setPage)
  const [busy, setBusy] = useState<string | null>(null)
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)

  const byId = useMemo(() => new Map(runs.map((run) => [run.id, run])), [runs])
  const ordered = useMemo(
    () => [...runs].sort((a, b) => {
      const depth = lineageDepth(a, byId) - lineageDepth(b, byId)
      if (depth !== 0) return depth
      return (a.created_at ?? '').localeCompare(b.created_at ?? '')
    }),
    [runs, byId],
  )

  const branches = runs.filter((run) => run.parent_run_id).length
  const live = runs.filter((run) => run.status === 'running').length
  const totalDays = runs.reduce((sum, run) => sum + run.day, 0)

  const branchFrom = async (snapshotId: string | null, label: string) => {
    setBusy(snapshotId ?? 'now')
    setError(null)
    try {
      await branchRun(snapshotId, note.trim() || label)
      setNote('')
      setPage('overview')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not branch this world')
    } finally {
      setBusy(null)
    }
  }

  const capture = async () => {
    if (!state) return
    setBusy('capture')
    setError(null)
    try {
      await api.createSnapshot(state.run.id, `${state.run.world_name} · day ${state.run.day}`)
      await refreshSnapshots()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not capture a snapshot')
    } finally {
      setBusy(null)
    }
  }

  if (!runs.length) return <EmptyState icon={<Globe2 size={22} />} title="No worlds exist" />

  return (
    <div className="scroll-area h-full">
      <div className="mx-auto max-w-[1500px] space-y-4 px-5 py-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard label="worlds" value={fmt(runs.length)} hint={`${live} running now`} icon={<Globe2 size={14} />} tone="amber" />
          <StatCard label="branches" value={fmt(branches)} hint="forked from an earlier day" icon={<GitBranch size={14} />} tone="violet" />
          <StatCard label="simulated days" value={fmt(totalDays)} hint="summed across every world" icon={<Clock size={14} />} tone="teal" />
          <StatCard label="snapshots here" value={fmt(snapshots.length)} hint={state ? `world ${state.run.world_name}` : 'no active world'} icon={<Camera size={14} />} tone="default" />
        </div>

        <Panel
          title="Worlds"
          eyebrow="independent state, independent history"
          action={
            <button type="button" className="btn-ghost" onClick={() => setPage('experiments')}>
              <GitCompare size={12} /> Compare
            </button>
          }
        >
          <div className="grid grid-cols-1 gap-3 p-4 md:grid-cols-2 xl:grid-cols-3">
            {ordered.map((run) => {
              const active = run.id === currentRunId
              const depth = lineageDepth(run, byId)
              const parent = run.parent_run_id ? byId.get(run.parent_run_id) : null
              return (
                <div
                  key={run.id}
                  className={clsx(
                    'rounded-lg border p-3 transition-colors',
                    active ? 'border-amber/40 bg-amber/[0.045]' : 'border-edge-soft bg-panel2/40 hover:border-edge',
                  )}
                  style={{ marginLeft: `${Math.min(depth, 4) * 10}px` }}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        {depth > 0 && <GitBranch size={10} className="shrink-0 text-violet" />}
                        <span className="truncate text-[13px] font-semibold text-fg">{run.world_name}</span>
                        {active && <Badge tone="amber">observing</Badge>}
                      </div>
                      <div className="mt-0.5 font-mono text-[9px] uppercase tracking-wider text-dim">
                        seed {run.seed} · {presetName(run.preset)}
                      </div>
                    </div>
                    <Badge tone={statusTone(run.status)}>{run.status}</Badge>
                  </div>

                  <div className="mt-3 grid grid-cols-3 gap-2">
                    <Number label="day" value={fmt(run.day)} />
                    <Number label="alive" value={fmt(run.population)} />
                    <Number label="politics" value={fmt(run.settlements)} />
                  </div>

                  <div className="mt-2 min-h-[28px] text-[10px] leading-relaxed text-muted">
                    {parent && (
                      <span>
                        branched from <span className="text-violet/90">{parent.world_name}</span>
                        {run.branch_day ? ` at day ${run.branch_day}` : ''}
                      </span>
                    )}
                    {!parent && run.note && <span className="text-dim">{run.note}</span>}
                    {!parent && !run.note && <span className="text-dim">original timeline</span>}
                  </div>

                  <div className="mt-2 flex items-center gap-1.5">
                    <button
                      type="button"
                      className={clsx('btn flex-1 justify-center py-1 text-[10.5px]', active && 'border-amber/40 text-amber')}
                      onClick={() => { void selectRun(run.id); setPage('overview') }}
                    >
                      <Play size={11} /> {active ? 'Current' : 'Observe'}
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        </Panel>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <Panel title="Timeline" eyebrow="branch order in this multiverse">
            <div className="px-4 py-3">
              {ordered.map((run) => {
                const depth = lineageDepth(run, byId)
                return (
                  <button
                    key={run.id}
                    type="button"
                    onClick={() => void selectRun(run.id)}
                    className={clsx(
                      'flex w-full items-center gap-2 border-l py-1.5 pl-2 text-left',
                      depth === 0 ? 'border-amber/50' : 'border-violet/40',
                      run.id === currentRunId ? 'text-fg' : 'text-muted hover:text-fg',
                    )}
                    style={{ marginLeft: `${Math.min(depth, 6) * 14}px` }}
                  >
                    <span className="font-mono text-[9px] text-dim">{depth === 0 ? '●' : '└'}</span>
                    <span className="min-w-0 flex-1 truncate text-[11.5px]">{run.world_name}</span>
                    <span className="font-mono text-[9px] text-dim">day {run.day}</span>
                    <Badge tone={statusTone(run.status)}>{run.status}</Badge>
                  </button>
                )
              })}
            </div>
            <div className="border-t border-edge-soft/60 px-4 py-2.5 text-[10px] leading-relaxed text-dim">
              A branch copies the entire world at the chosen day: agents, memories, relationships, buildings, stores, beliefs and knowledge.
              Divergence after that point is genuinely independent.
            </div>
          </Panel>

          <Panel
            title="Snapshots & branches"
            eyebrow={state ? `${state.run.world_name} · day ${state.run.day}` : 'no active world'}
            action={
              <button type="button" className="btn-ghost" disabled={!state || busy !== null} onClick={() => void capture()}>
                {busy === 'capture' ? <Loader2 size={12} className="animate-spin" /> : <Camera size={12} />} Capture
              </button>
            }
            bodyClassName="scroll-area max-h-[420px]"
          >
            {!state && <div className="px-4 py-8 text-center text-[11.5px] text-muted">Select a world to see its snapshots.</div>}
            {state && snapshots.length === 0 && (
              <div className="px-4 py-8 text-center text-[11.5px] leading-relaxed text-muted">
                No snapshots yet. The engine also autosaves every 25 days, keeping the newest 20.
              </div>
            )}
            {state && snapshots.map((snapshot) => (
              <div key={snapshot.id} className="flex items-center justify-between gap-3 border-b border-edge-soft/60 px-4 py-2.5 last:border-0">
                <div className="min-w-0">
                  <div className="truncate text-[11.5px] text-fg">{snapshot.label || `day ${snapshot.day}`}</div>
                  <div className="font-mono text-[9px] text-dim">day {snapshot.day}{snapshot.created_at ? ` · ${new Date(snapshot.created_at).toLocaleString()}` : ''}</div>
                </div>
                <button
                  type="button"
                  className="btn-ghost shrink-0 text-[10.5px]"
                  disabled={busy !== null}
                  onClick={() => void branchFrom(snapshot.id, `Branch of ${state.run.world_name} at day ${snapshot.day}`)}
                >
                  {busy === snapshot.id ? <Loader2 size={11} className="animate-spin" /> : <GitBranch size={11} />} Branch
                </button>
              </div>
            ))}

            <div className="space-y-2 border-t border-edge-soft/60 px-4 py-3">
              <div className="eyebrow">branch from today</div>
              <input
                className="input text-[11px]"
                placeholder="Optional label for the new timeline"
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
              <button
                type="button"
                className="btn w-full justify-center py-1.5 text-[11px]"
                disabled={!state || busy !== null}
                onClick={() => void branchFrom(null, `Fork of ${state?.run.world_name ?? 'world'} from day ${state?.run.day ?? 0}`)}
              >
                {busy === 'now' ? <Loader2 size={12} className="animate-spin" /> : <Layers size={12} />} Fork this world now
              </button>
              {error && <div className="text-[10.5px] leading-relaxed text-danger">{error}</div>}
            </div>
          </Panel>
        </div>

        <Panel title="Creating a controlled comparison" eyebrow="how to use this page">
          <div className="flex flex-wrap items-start gap-4 px-4 py-4 text-[11px] leading-relaxed text-muted">
            <div className="flex items-start gap-2">
              <span className="mt-0.5 font-mono text-[10px] text-amber">01</span>
              <span>Fork a world at the day you want to test a hypothesis.</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="mt-0.5 font-mono text-[10px] text-amber">02</span>
              <span>Let each branch run independently — different seeds of chance, same starting state.</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="mt-0.5 font-mono text-[10px] text-amber">03</span>
              <span><button type="button" className="text-teal hover:underline" onClick={() => setPage('experiments')}>Compare them</button> on measured outcomes, not narrative.</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="mt-0.5 font-mono text-[10px] text-amber">04</span>
              <span>
                <button type="button" className="inline-flex items-center gap-1 text-teal hover:underline" onClick={() => setPage('settings')}>
                  <Plus size={10} /> New world
                </button>{' '}
                for a fresh seed rather than a fork.
              </span>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  )
}

function Number({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-edge-soft/60 px-2 py-1.5">
      <div className="font-mono text-[8px] uppercase tracking-wider text-dim">{label}</div>
      <div className="num text-[12px] text-fg">{value}</div>
    </div>
  )
}
