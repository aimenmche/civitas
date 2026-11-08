import { useEffect, useState } from 'react'
import { Settings2, Database, Cpu, Trash2, Server, BookOpen, ExternalLink, CheckCircle2, XCircle, Loader2 } from 'lucide-react'
import { useStore } from '../store'
import { api } from '../api'
import { Badge, EmptyState, Panel } from '../components/ui'
import { fmt, presetName, titleCase } from '../lib/format'

export function SettingsPage() {
  const state = useStore((s) => s.state)
  const runs = useStore((s) => s.runs)
  const deleteRun = useStore((s) => s.deleteRun)
  const refreshRuns = useStore((s) => s.refreshRuns)
  const [health, setHealth] = useState<{ status: string; app: string; runs: number; database: string; llm: boolean } | null>(null)
  const [llm, setLlm] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [confirm, setConfirm] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    void Promise.all([api.health(), api.llmStatus()])
      .then(([healthResult, llmResult]) => { if (!cancelled) { setHealth(healthResult); setLlm(llmResult) } })
      .catch((err) => { if (!cancelled) setError(err instanceof Error ? err.message : 'Could not reach the API') })
    return () => { cancelled = true }
  }, [])

  const remove = async (runId: string) => {
    setBusy(true)
    try {
      await deleteRun(runId)
      setConfirm(null)
      await refreshRuns()
    } finally {
      setBusy(false)
    }
  }

  if (!state) {
    return <EmptyState icon={<Settings2 size={22} />} title="No run selected">The observatory settings are available once a world exists.</EmptyState>
  }

  const config = state.run.config

  return (
    <div className="scroll-area h-full">
      <div className="mx-auto max-w-[1200px] space-y-4 px-5 py-4">
        {error && <div className="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger">{error}</div>}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Panel title="API" eyebrow="connection" action={<Server size={13} className="text-dim" />} bodyClassName="px-4 py-3">
            <div className="space-y-2 font-mono text-[10.5px]">
              <Row label="status" value={health ? <span className="flex items-center gap-1 text-good"><CheckCircle2 size={11} /> {health.status}</span> : <span className="text-muted">checking…</span>} />
              <Row label="app" value={health?.app ?? 'CIVITAS'} />
              <Row label="live runs" value={health ? fmt(health.runs) : '—'} />
              <Row label="database" value={health?.database ?? '—'} />
              <Row label="websocket" value={<span className={state.run.status === 'error' ? 'text-danger' : 'text-good'}>{state.run.status === 'error' ? 'degraded' : 'streaming'}</span>} />
            </div>
          </Panel>

          <Panel title="Narrative model" eyebrow="optional" action={<Cpu size={13} className="text-dim" />} bodyClassName="px-4 py-3">
            <div className="space-y-2 font-mono text-[10.5px]">
              <Row label="enabled" value={llm?.enabled ? <span className="text-good">yes</span> : <span className="text-muted">no</span>} />
              <Row label="configured" value={llm?.configured ? <span className="text-good">yes</span> : <span className="flex items-center gap-1 text-muted"><XCircle size={10} /> no key</span>} />
              <Row label="model" value={String(llm?.model ?? '—')} />
              <Row label="affects simulation" value={<span className="text-good">never</span>} />
              <Row label="rate of use" value={String(llm?.calls_last_minute ?? 0) + ' calls/min'} />
            </div>
            <p className="mt-2 text-[10px] leading-relaxed text-dim">
              Set <code className="text-muted">CIVITAS_LLM_ENABLED=true</code>, a base URL, key and model in the backend environment to enable the manual chronicler. The simulation itself never calls it.
            </p>
          </Panel>

          <Panel title="Storage" eyebrow="persistence" action={<Database size={13} className="text-dim" />} bodyClassName="px-4 py-3">
            <div className="space-y-2 font-mono text-[10.5px]">
              <Row label="active run" value={state.run.id} />
              <Row label="archived runs" value={fmt(runs.length)} />
              <Row label="snapshots" value={fmt(useStore.getState().snapshots.length)} />
              <Row label="events" value={fmt(state.events.length)} />
              <Row label="data directory" value="backend/data" />
            </div>
            <p className="mt-2 text-[10px] leading-relaxed text-dim">SQLite by default. Set <code className="text-muted">CIVITAS_DATABASE_URL</code> for PostgreSQL.</p>
          </Panel>
        </div>

        <Panel title="Active world configuration" eyebrow="the rules of this run">
          <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 px-4 py-4 font-mono text-[10.5px] sm:grid-cols-3 lg:grid-cols-4">
            <Row label="name" value={state.run.world_name} />
            <Row label="preset" value={presetName(config.preset)} />
            <Row label="seed" value={String(state.run.seed)} />
            <Row label="size" value={`${config.width} × ${config.height}`} />
            <Row label="population cap" value={String(config.initial_population)} />
            <Row label="starting groups" value={String(config.starting_groups)} />
            <Row label="climate" value={titleCase(config.climate)} />
            <Row label="difficulty" value={fmt(config.environmental_difficulty, 2)} />
            <Row label="abundance" value={fmt(config.resource_abundance, 2)} />
            <Row label="personality" value={titleCase(config.personality_distribution)} />
            <Row label="starting tech" value={titleCase(config.starting_technology)} />
            <Row label="currency" value={config.no_currency ? 'disabled' : 'enabled'} />
            <Row label="leadership" value={config.no_leader ? 'assembly only' : 'permitted'} />
            <Row label="asymmetry" value={config.asymmetric_groups ? 'yes' : 'no'} />
            <Row label="max population" value={String(config.max_population)} />
            <Row label="notation" value={config.notation || '—'} />
          </div>
        </Panel>

        <Panel title="Run archive" eyebrow="every world in this database">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left">
              <thead>
                <tr className="border-b border-edge-soft font-mono text-[9px] uppercase tracking-wider text-dim">
                  <th className="px-4 py-2 font-normal">world</th>
                  <th className="px-3 py-2 font-normal">preset</th>
                  <th className="px-3 py-2 text-right font-normal">seed</th>
                  <th className="px-3 py-2 text-right font-normal">day</th>
                  <th className="px-3 py-2 text-right font-normal">people</th>
                  <th className="px-3 py-2 font-normal">status</th>
                  <th className="px-3 py-2 font-normal">origin</th>
                  <th className="px-3 py-2 text-right font-normal">remove</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id} className="table-row">
                    <td className="px-4 py-2.5 text-[11.5px] text-fg">{run.world_name}</td>
                    <td className="px-3 py-2.5 text-[10.5px] text-muted">{presetName(run.preset)}</td>
                    <td className="num px-3 py-2.5 text-right text-[10.5px] text-muted">{run.seed}</td>
                    <td className="num px-3 py-2.5 text-right text-[10.5px] text-fg">{run.day}</td>
                    <td className="num px-3 py-2.5 text-right text-[10.5px] text-teal">{run.population}</td>
                    <td className="px-3 py-2.5"><Badge tone={run.status === 'running' ? 'good' : run.status === 'error' ? 'danger' : 'muted'}>{run.status}</Badge></td>
                    <td className="px-3 py-2.5 font-mono text-[9px] text-dim">{run.parent_run_id ? `branch · ${run.parent_run_id.slice(-6)}` : 'original'}</td>
                    <td className="px-3 py-2.5 text-right">
                      {confirm === run.id ? (
                        <div className="flex justify-end gap-1">
                          <button type="button" className="btn-ghost px-1.5 py-1 text-danger" disabled={busy} onClick={() => void remove(run.id)}>
                            {busy ? <Loader2 size={11} className="animate-spin" /> : 'confirm'}
                          </button>
                          <button type="button" className="btn-ghost px-1.5 py-1" onClick={() => setConfirm(null)}>cancel</button>
                        </div>
                      ) : (
                        <button type="button" className="btn-ghost px-1.5 py-1 text-muted hover:text-danger" onClick={() => setConfirm(run.id)} title="Delete this run and all its history">
                          <Trash2 size={12} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Panel title="How this works" eyebrow="architecture" action={<BookOpen size={13} className="text-dim" />}>
            <div className="space-y-2 px-4 py-3 text-[11px] leading-relaxed text-muted">
              <p><span className="text-fg">Deterministic core.</span> Rust-free, pure-Python simulation with its own seeded PRNG. Every tick is a day. One run at seed 123 always produces the same history.</p>
              <p><span className="text-fg">Autonomous agents.</span> Each person scores actions against needs, skills, personality, relationships and the settlement's state. The highest-scoring action is executed; alternatives are recorded in the dossier.</p>
              <p><span className="text-fg">Emergent society.</span> Settlements, governments, laws, factions, languages, traditions, families and technologies are outputs of the rules, not authored content.</p>
              <p><span className="text-fg">Persistence.</span> Events and per-day metrics are written as they happen. Full state snapshots power restore, branching and the time machine.</p>
            </div>
          </Panel>

          <Panel title="Running locally" eyebrow="commands" action={<ExternalLink size={13} className="text-dim" />}>
            <div className="space-y-2 px-4 py-3 font-mono text-[10px] leading-relaxed text-muted">
              <div className="rounded border border-edge-soft bg-bg2/50 px-2.5 py-2">
                <div className="text-dim"># backend</div>
                <div className="text-fg">cd backend</div>
                <div className="text-fg">.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000</div>
              </div>
              <div className="rounded border border-edge-soft bg-bg2/50 px-2.5 py-2">
                <div className="text-dim"># frontend</div>
                <div className="text-fg">cd frontend</div>
                <div className="text-fg">npm run dev</div>
              </div>
              <p className="text-[10px] text-dim">Vite proxies <code>/api</code> and websockets to port 8000. Open http://localhost:5173.</p>
            </div>
          </Panel>
        </div>

        <div className="pb-2 text-center font-mono text-[9px] uppercase tracking-[0.2em] text-dim">
          CIVITAS · deterministic civilization observatory · engine v0.2.1
        </div>
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-muted">{label}</span>
      <span className="truncate text-right text-fg">{value}</span>
    </div>
  )
}
