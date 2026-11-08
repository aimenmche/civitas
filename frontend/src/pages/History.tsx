import { useEffect, useMemo, useState } from 'react'
import { ScrollText, Camera, GitBranch, Loader2, Download, Filter, Search, BookOpen, Sparkles } from 'lucide-react'
import clsx from 'clsx'
import { useStore } from '../store'
import { api } from '../api'
import { Badge, EmptyState, Panel } from '../components/ui'
import { eventCategoryTone, fmt, titleCase } from '../lib/format'
import type { SimEvent } from '../types'

// Must match the categories the engine actually writes, or a chip filters to nothing.
const CATEGORIES = ['all', 'milestone', 'demography', 'settlement', 'technology', 'culture', 'politics', 'economy', 'conflict', 'disaster', 'social', 'survival', 'world']

export function HistoryPage() {
  const state = useStore((s) => s.state)
  const snapshots = useStore((s) => s.snapshots)
  const refreshSnapshots = useStore((s) => s.refreshSnapshots)
  const branchRun = useStore((s) => s.branchRun)
  const setPage = useStore((s) => s.setPage)
  const [history, setHistory] = useState<SimEvent[]>([])
  const [category, setCategory] = useState('all')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [snapshotLabel, setSnapshotLabel] = useState('')
  const [branchNote, setBranchNote] = useState('')
  const [busySnapshot, setBusySnapshot] = useState(false)
  const [busyBranch, setBusyBranch] = useState<string | null>(null)
  const [chronicle, setChronicle] = useState<string | null>(null)
  const [chronicleError, setChronicleError] = useState<string | null>(null)
  const [chronicleBusy, setChronicleBusy] = useState(false)
  const [chronicleKind, setChronicleKind] = useState<'summary' | 'dramatic' | 'neutral'>('summary')

  const runId = state?.run.id

  useEffect(() => {
    if (!runId) return
    let cancelled = false
    setLoading(true)
    void api.getHistory(runId, category === 'all' ? undefined : category, 500)
      .then((events) => { if (!cancelled) setHistory(events) })
      .catch(() => { if (!cancelled) setHistory(state?.events ?? []) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [runId, category, state?.run.day])

  useEffect(() => {
    if (runId) void refreshSnapshots()
  }, [runId, refreshSnapshots, state?.run.day])

  const filtered = useMemo(() => {
    const list = history.filter((event) => !query.trim() || `${event.title} ${event.description} ${event.category}`.toLowerCase().includes(query.toLowerCase().trim()))
    return [...list].sort((a, b) => b.day - a.day || b.id.localeCompare(a.id))
  }, [history, query])

  if (!state) return <EmptyState icon={<ScrollText size={22} />} title="No run loaded" />

  const createSnapshot = async () => {
    setBusySnapshot(true)
    try {
      await api.createSnapshot(state.run.id, snapshotLabel.trim() || `Day ${state.run.day} bookmark`)
      setSnapshotLabel('')
      await refreshSnapshots()
    } finally {
      setBusySnapshot(false)
    }
  }

  const branch = async (snapshotId: string | null) => {
    setBusyBranch(snapshotId ?? 'current')
    try {
      await branchRun(snapshotId, branchNote.trim() || 'Alternate history')
      setBranchNote('')
      setPage('overview')
    } finally {
      setBusyBranch(null)
    }
  }

  const runChronicle = async () => {
    setChronicleBusy(true)
    setChronicleError(null)
    setChronicle(null)
    try {
      const result = await api.chronicle(state.run.id, chronicleKind, 120)
      setChronicle(result.text)
    } catch (error) {
      setChronicleError(error instanceof Error ? error.message : 'The chronicler is unavailable.')
    } finally {
      setChronicleBusy(false)
    }
  }

  const exportHistory = () => {
    const rows = filtered.map((event) => ({ day: event.day, year: event.year, category: event.category, title: event.title, description: event.description }))
    const blob = new Blob([JSON.stringify(rows, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${state.run.world_name.replace(/\W+/g, '-')}-history.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="scroll-area h-full">
      <div className="mx-auto max-w-[1500px] space-y-4 px-5 py-4">
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <div className="xl:col-span-2">
            <Panel
              title="The chronicle"
              eyebrow={`${filtered.length} of ${history.length} recorded events`}
              action={
                <div className="flex flex-wrap items-center gap-2">
                  <div className="relative">
                    <Search size={12} className="pointer-events-none absolute left-2.5 top-2.5 text-dim" />
                    <input className="input w-44 py-1.5 pl-7 text-[11px]" placeholder="Search the record…" value={query} onChange={(event) => setQuery(event.target.value)} />
                  </div>
                  <button type="button" className="btn-ghost" onClick={exportHistory} title="Export the filtered record as JSON"><Download size={13} /></button>
                </div>
              }
              bodyClassName="min-h-0"
            >
              <div className="flex flex-wrap items-center gap-1 border-b border-edge-soft px-3 py-2">
                <Filter size={11} className="mr-1 text-dim" />
                {CATEGORIES.map((item) => (
                  <button
                    key={item}
                    type="button"
                    onClick={() => setCategory(item)}
                    className={clsx('rounded px-2 py-1 font-mono text-[9px] uppercase tracking-wider transition-colors', category === item ? 'bg-amber/15 text-amber' : 'text-muted hover:bg-white/5 hover:text-fg')}
                  >
                    {item}
                  </button>
                ))}
              </div>
              <div className="scroll-area max-h-[600px]">
                {loading && <div className="flex items-center justify-center gap-2 px-4 py-6 font-mono text-[10px] uppercase tracking-wider text-dim"><Loader2 size={12} className="animate-spin" /> reading the archive</div>}
                {!loading && filtered.length === 0 && <div className="px-4 py-10 text-center text-[11.5px] text-muted">No events match this filter.</div>}
                {!loading && filtered.map((event) => (
                  <article key={event.id} className="border-b border-edge-soft/60 px-4 py-3 last:border-0">
                    <div className="flex items-start gap-3">
                      <div className="flex w-12 shrink-0 flex-col items-end">
                        <span className="num text-[11px] text-muted">D{event.day}</span>
                        <span className="font-mono text-[8.5px] text-dim">Y{event.year} · {event.season.slice(0, 3)}</span>
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="mb-1 flex flex-wrap items-center gap-1.5">
                          <span className={clsx('rounded border px-1.5 py-0.5 font-mono text-[8.5px] uppercase tracking-wider', eventCategoryTone(event.category))}>{event.category}</span>
                          {event.importance >= 4 && <Badge tone="amber">major</Badge>}
                          {event.location_name && <span className="font-mono text-[9px] text-dim">{event.location_name}</span>}
                        </div>
                        <h3 className="text-[12.5px] font-medium leading-snug text-fg">{event.title}</h3>
                        <p className="mt-0.5 text-[11.5px] leading-relaxed text-muted">{event.description}</p>
                        {(event.consequences?.length ?? 0) > 0 && (
                          <div className="mt-1.5 space-y-0.5">
                            {event.consequences.map((consequence, index) => (
                              <div key={index} className="font-mono text-[9.5px] text-dim">→ {consequence}</div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            </Panel>
          </div>

          <div className="space-y-4">
            <Panel title="Time machine" eyebrow="snapshot & branch" action={<Camera size={13} className="text-dim" />}>
              <div className="space-y-3 px-4 py-3">
                <p className="text-[11px] leading-relaxed text-muted">
                  A snapshot freezes the entire world: every person, relationship, memory, store and building. Branch it to run a different history from that exact moment.
                </p>
                <div className="flex gap-2">
                  <input className="input py-1.5 text-[11px]" placeholder={`Bookmark day ${state.run.day}…`} value={snapshotLabel} onChange={(event) => setSnapshotLabel(event.target.value)} />
                  <button type="button" className="btn-primary shrink-0" disabled={busySnapshot} onClick={() => void createSnapshot()}>
                    {busySnapshot ? <Loader2 size={12} className="animate-spin" /> : <Camera size={12} />} Save
                  </button>
                </div>
                <div className="scroll-area max-h-52 space-y-1.5">
                  {snapshots.map((snapshot) => (
                    <div key={snapshot.id} className="flex items-center justify-between gap-2 rounded border border-edge-soft px-2.5 py-1.5">
                      <div className="min-w-0">
                        <div className="truncate text-[11px] text-fg">{snapshot.label}</div>
                        <div className="font-mono text-[8.5px] text-dim">day {snapshot.day} · {snapshot.created_at ? new Date(snapshot.created_at).toLocaleString() : '—'}</div>
                      </div>
                      <button type="button" className="btn-ghost shrink-0 px-1.5 py-1" disabled={busyBranch !== null} onClick={() => void branch(snapshot.id)} title="Branch from this snapshot">
                        {busyBranch === snapshot.id ? <Loader2 size={12} className="animate-spin" /> : <GitBranch size={12} />}
                      </button>
                    </div>
                  ))}
                  {!snapshots.length && <div className="py-3 text-center text-[10.5px] text-muted">No snapshots yet. Autosaves appear every {10} days.</div>}
                </div>
                <div className="border-t border-edge-soft pt-2">
                  <div className="label">branch from now</div>
                  <div className="flex gap-2">
                    <input className="input py-1.5 text-[11px]" placeholder="Name this alternate history…" value={branchNote} onChange={(event) => setBranchNote(event.target.value)} />
                    <button type="button" className="btn shrink-0" disabled={busyBranch !== null} onClick={() => void branch(null)}>
                      {busyBranch === 'current' ? <Loader2 size={12} className="animate-spin" /> : <GitBranch size={12} />} Branch
                    </button>
                  </div>
                </div>
              </div>
            </Panel>

            <Panel title="Chronicler" eyebrow="optional narrative enrichment" action={<BookOpen size={13} className="text-dim" />}>
              <div className="space-y-2.5 px-4 py-3">
                <p className="text-[11px] leading-relaxed text-muted">
                  An optional language model can retell the recorded facts as prose. It never runs during simulation ticks and cannot change the world. Without a configured provider the simulation continues untouched.
                </p>
                <div className="flex items-center gap-2">
                  <select className="input py-1.5 text-[11px]" value={chronicleKind} onChange={(event) => setChronicleKind(event.target.value as typeof chronicleKind)}>
                    <option value="summary">Historical summary</option>
                    <option value="dramatic">Dramatic chronicle</option>
                    <option value="neutral">Neutral report</option>
                  </select>
                  <button type="button" className="btn-primary shrink-0" disabled={chronicleBusy} onClick={() => void runChronicle()}>
                    {chronicleBusy ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />} Write
                  </button>
                </div>
                {chronicleError && <div className="rounded border border-danger/30 bg-danger/10 px-2.5 py-2 text-[10.5px] leading-relaxed text-danger">{chronicleError}</div>}
                {chronicle && (
                  <div className="scroll-area max-h-52 rounded border border-edge-soft bg-bg2/40 px-3 py-2 text-[11px] leading-relaxed text-fg/90">
                    {chronicle.split('\n').filter(Boolean).map((paragraph, index) => <p key={index} className="mb-2 last:mb-0">{paragraph}</p>)}
                  </div>
                )}
              </div>
            </Panel>

            <Panel title="Eras" eyebrow="technology as history">
              <div className="space-y-1.5 px-4 py-3 font-mono text-[10px]">
                <div className="flex justify-between"><span className="text-muted">current era</span><span className="text-amber">{state.run.era}</span></div>
                <div className="flex justify-between"><span className="text-muted">known technologies</span><span className="text-fg">{state.run.techs.length}</span></div>
                <div className="flex justify-between"><span className="text-muted">births</span><span className="text-good">{state.run.births}</span></div>
                <div className="flex justify-between"><span className="text-muted">deaths</span><span className="text-danger">{state.run.deaths}</span></div>
                <div className="flex justify-between"><span className="text-muted">generations</span><span className="text-fg">{state.metrics.generations ?? 1}</span></div>
              </div>
            </Panel>
          </div>
        </div>

        <Panel title="Category index" eyebrow="event counts in this archive">
          <div className="flex flex-wrap gap-1.5 px-4 py-3">
            {Object.entries(
              history.reduce<Record<string, number>>((acc, event) => {
                acc[event.category] = (acc[event.category] ?? 0) + 1
                return acc
              }, {}),
            ).sort((a, b) => b[1] - a[1]).map(([name, count]) => (
              <button key={name} type="button" onClick={() => setCategory(name)} className={clsx('rounded border px-2 py-1 font-mono text-[9.5px] uppercase tracking-wider transition-colors', category === name ? 'border-amber/40 bg-amber/10 text-amber' : 'border-edge text-muted hover:text-fg')}>
                {titleCase(name)} <span className="text-dim">{fmt(count)}</span>
              </button>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  )
}
