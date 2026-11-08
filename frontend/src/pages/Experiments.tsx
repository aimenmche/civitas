import { useMemo, useState } from 'react'
import { FlaskConical, GitCompare, Loader2, GitBranch, ArrowRight, Layers } from 'lucide-react'
import clsx from 'clsx'
import { useStore } from '../store'
import { api } from '../api'
import { MetricChart } from '../components/Charts'
import { Badge, EmptyState, Panel } from '../components/ui'
import { fmt, presetName } from '../lib/format'
import type { MetricsPoint } from '../types'

const COLORS = ['#f0b35a', '#58d6c5', '#9d8cf5', '#ef6b78', '#7ed491', '#e98cbb']

export function ExperimentsPage() {
  const runs = useStore((s) => s.runs)
  const state = useStore((s) => s.state)
  const branchRun = useStore((s) => s.branchRun)
  const refreshRuns = useStore((s) => s.refreshRuns)
  const setPage = useStore((s) => s.setPage)
  const selectRun = useStore((s) => s.selectRun)
  const [selected, setSelected] = useState<string[]>(state ? [state.run.id] : [])
  const [comparison, setComparison] = useState<Awaited<ReturnType<typeof api.compare>> | null>(null)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)

  const toggle = (id: string) => {
    setSelected((current) => current.includes(id) ? current.filter((item) => item !== id) : current.length >= 6 ? current : [...current, id])
  }

  const compare = async () => {
    if (selected.length < 2) return
    setBusy(true)
    setError(null)
    try {
      setComparison(await api.compare(selected))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Comparison failed')
    } finally {
      setBusy(false)
    }
  }

  const branchNow = async () => {
    setBusy(true)
    try {
      const branch = await branchRun(null, note.trim() || 'Experiment branch')
      setNote('')
      await refreshRuns()
      setSelected((current) => [...current, branch.id].slice(-6))
      setPage('overview')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create branch')
    } finally {
      setBusy(false)
    }
  }

  const series = useMemo(() => {
    if (!comparison) return []
    return comparison.series.map((run, index) => ({
      run_id: run.run_id,
      name: run.name,
      color: COLORS[index % COLORS.length],
      points: run.points.length ? run.points : [{ day: 1 } as MetricsPoint],
    }))
  }, [comparison])

  if (!state) return <EmptyState icon={<FlaskConical size={22} />} title="No run loaded">Create a world before designing experiments.</EmptyState>

  return (
    <div className="scroll-area h-full">
      <div className="mx-auto max-w-[1500px] space-y-4 px-5 py-4">
        <section className="panel px-5 py-4">
          <div className="eyebrow mb-1 flex items-center gap-1.5"><FlaskConical size={12} /> controlled comparison</div>
          <h2 className="text-[18px] font-semibold text-fg">Experiments</h2>
          <p className="mt-1 max-w-3xl text-[12px] leading-relaxed text-muted">
            Branching preserves the full state at a moment in time. Change nothing but the seed, population, scarcity or constraints, then compare where the histories diverge.
            {' '}This is not a scripted scenario system: each branch is a real simulation run forward by the same rules.
          </p>
        </section>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <Panel title="Select worlds" eyebrow="up to six runs" action={<Badge tone={selected.length >= 2 ? 'good' : 'muted'}>{selected.length} selected</Badge>}>
            <div className="scroll-area max-h-[420px]">
              {runs.map((run) => {
                const checked = selected.includes(run.id)
                return (
                  <button
                    key={run.id}
                    type="button"
                    onClick={() => toggle(run.id)}
                    className={clsx('flex w-full items-start justify-between gap-3 border-b border-edge-soft/60 px-4 py-2.5 text-left last:border-0 hover:bg-white/[0.025]', checked && 'bg-teal/[0.05]')}
                  >
                    <div className="flex min-w-0 items-start gap-2">
                      <span className={clsx('mt-0.5 flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded border text-[9px]', checked ? 'border-teal bg-teal/20 text-teal' : 'border-edge text-transparent')}>✓</span>
                      <div className="min-w-0">
                        <div className="truncate text-[12px] text-fg">{run.world_name}</div>
                        <div className="font-mono text-[9px] text-dim">day {run.day} · {run.population} alive · seed {run.seed}</div>
                        <div className="font-mono text-[8.5px] text-dim">{presetName(run.preset)}{run.parent_run_id ? ` · branch of ${run.parent_run_id.slice(-6)}` : ''}</div>
                      </div>
                    </div>
                    <button
                      type="button"
                      className="btn-ghost shrink-0 px-1.5 py-1 text-[9px]"
                      onClick={(event) => { event.stopPropagation(); void selectRun(run.id) }}
                    >
                      open
                    </button>
                  </button>
                )
              })}
              {!runs.length && <div className="px-4 py-8 text-[11.5px] text-muted">No runs yet.</div>}
            </div>
            <div className="border-t border-edge-soft px-4 py-3">
              <button type="button" className="btn-primary w-full" disabled={busy || selected.length < 2} onClick={() => void compare()}>
                {busy ? <Loader2 size={12} className="animate-spin" /> : <GitCompare size={12} />} Compare selected
              </button>
            </div>
          </Panel>

          <Panel title="Create a branch" eyebrow="fork the current run" className="xl:col-span-2">
            <div className="grid grid-cols-1 gap-4 px-4 py-4 md:grid-cols-2">
              <div>
                <p className="text-[11.5px] leading-relaxed text-muted">
                  The current run is <span className="text-fg">{state.run.world_name}</span> at day <span className="text-fg">{state.run.day}</span>.
                  Branching copies every agent, memory, relationship and building into a new run. The original is untouched.
                </p>
                <div className="mt-3 space-y-2">
                  <input className="input" placeholder="Optional label, e.g. 'No currency experiment'" value={note} onChange={(event) => setNote(event.target.value)} />
                  <button type="button" className="btn w-full" disabled={busy} onClick={() => void branchNow()}>
                    {busy ? <Loader2 size={12} className="animate-spin" /> : <GitBranch size={12} />} Branch from day {state.run.day}
                  </button>
                </div>
              </div>
              <div className="space-y-2 rounded-lg border border-edge-soft bg-bg2/40 px-3 py-3 font-mono text-[10px]">
                <div className="mb-1 flex items-center gap-1 text-[9px] uppercase tracking-wider text-dim"><Layers size={10} /> current state</div>
                <div className="flex justify-between"><span className="text-muted">preset</span><span className="text-fg">{presetName(state.run.config.preset)}</span></div>
                <div className="flex justify-between"><span className="text-muted">population</span><span className="text-teal">{state.run.population}</span></div>
                <div className="flex justify-between"><span className="text-muted">settlements</span><span className="text-amber">{state.run.settlements}</span></div>
                <div className="flex justify-between"><span className="text-muted">technologies</span><span className="text-violet">{state.run.techs.length}</span></div>
                <div className="flex justify-between"><span className="text-muted">constraints</span><span className="text-fg">{state.run.config.no_currency ? 'no currency' : state.run.config.no_leader ? 'no leader' : 'none'}</span></div>
                <div className="flex justify-between"><span className="text-muted">seed</span><span className="text-fg">{state.run.seed}</span></div>
              </div>
            </div>
            {error && <div className="mx-4 mb-3 rounded border border-danger/30 bg-danger/10 px-2.5 py-2 text-[10.5px] text-danger">{error}</div>}
          </Panel>
        </div>

        {comparison && (
          <Panel title="Comparison" eyebrow={`${comparison.runs.length} runs`} action={<span className="font-mono text-[9px] text-dim">metrics sampled once per simulated day</span>}>
            <div className="flex flex-wrap gap-2 border-b border-edge-soft px-4 py-2">
              {series.map((item) => (
                <span key={item.run_id} className="flex items-center gap-1.5 font-mono text-[9.5px] text-muted">
                  <span className="h-2 w-2 rounded-full" style={{ background: item.color }} /> {item.name}
                </span>
              ))}
            </div>
            <div className="grid grid-cols-1 gap-4 p-4 xl:grid-cols-2">
              {[
                { title: 'Population', keys: ['population'] },
                { title: 'Settlements', keys: ['settlements'] },
                { title: 'Food', keys: ['food'] },
                { title: 'Technology count', keys: ['tech_count'] },
                { title: 'Happiness', keys: ['avg_happiness'] },
                { title: 'Inequality', keys: ['inequality'] },
              ].map((metric) => (
                <div key={metric.title} className="rounded-lg border border-edge-soft p-3">
                  <div className="mb-2 font-mono text-[10px] uppercase tracking-wider text-muted">{metric.title}</div>
                  <MetricChart
                    data={mergeSeries(series)}
                    series={series.map((item, index) => ({ key: `${item.run_id}__${metric.keys[0]}`, name: item.name, color: COLORS[index % COLORS.length] }))}
                    height={160}
                    area={false}
                  />
                </div>
              ))}
            </div>
            <div className="px-4 pb-4">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[600px] text-left">
                  <thead>
                    <tr className="border-b border-edge-soft font-mono text-[9px] uppercase tracking-wider text-dim">
                      <th className="px-3 py-2 font-normal">run</th>
                      <th className="px-3 py-2 font-normal">preset</th>
                      <th className="px-3 py-2 text-right font-normal">seed</th>
                      <th className="px-3 py-2 text-right font-normal">day</th>
                      <th className="px-3 py-2 text-right font-normal">population</th>
                      <th className="px-3 py-2 text-right font-normal">settlements</th>
                      <th className="px-3 py-2 text-right font-normal">status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparison.runs.map((run, index) => (
                      <tr key={run.id} className="table-row">
                        <td className="px-3 py-2 text-[11.5px] text-fg"><span className="mr-1.5 inline-block h-2 w-2 rounded-full" style={{ background: COLORS[index % COLORS.length] }} />{run.world_name}</td>
                        <td className="px-3 py-2 text-[10.5px] text-muted">{presetName(run.preset)}</td>
                        <td className="num px-3 py-2 text-right text-[10.5px] text-muted">{run.seed}</td>
                        <td className="num px-3 py-2 text-right text-[10.5px] text-fg">{run.day}</td>
                        <td className="num px-3 py-2 text-right text-[10.5px] text-teal">{run.population}</td>
                        <td className="num px-3 py-2 text-right text-[10.5px] text-amber">{run.settlements}</td>
                        <td className="px-3 py-2 text-right text-[10.5px] text-muted">{run.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </Panel>
        )}

        <div className="flex items-center gap-2 pb-2 font-mono text-[9px] text-dim">
          <ArrowRight size={11} /> Branching does not copy the UI, only the simulation state. Every branch continues to persist events and metrics independently.
        </div>
      </div>
    </div>
  )
}

function mergeSeries(series: Array<{ run_id: string; points: MetricsPoint[] }>): Array<Record<string, number | string | undefined>> {
  const byDay = new Map<number, Record<string, number | string | undefined>>()
  for (const run of series) {
    for (const point of run.points) {
      const row = byDay.get(point.day) ?? { day: point.day }
      for (const [key, value] of Object.entries(point)) {
        if (key === 'day') continue
        if (typeof value === 'number') row[`${run.run_id}__${key}`] = value
      }
      byDay.set(point.day, row)
    }
  }
  return Array.from(byDay.values()).sort((a, b) => Number(a.day) - Number(b.day))
}
