import { useMemo, useState } from 'react'
import { Globe2, Handshake, ScrollText, Swords, ArrowLeftRight } from 'lucide-react'
import clsx from 'clsx'
import { useStore } from '../store'
import { api } from '../api'
import { Badge, EmptyState, Panel, StatCard } from '../components/ui'
import { fmt } from '../lib/format'
import type { SettlementDetail, SettlementSummary } from '../types'
import { useThrottledEffect } from '../lib/useThrottledEffect'

type Status = 'neutral' | 'trade' | 'alliance' | 'hostile' | 'war' | 'peace'

const STATUS_ORDER: Status[] = ['war', 'hostile', 'alliance', 'trade', 'peace', 'neutral']

const STATUS_LABEL: Record<string, string> = {
  neutral: 'no contact',
  trade: 'trade',
  alliance: 'alliance',
  hostile: 'hostile',
  war: 'war',
  peace: 'peace',
}

const STATUS_TONE: Record<string, 'muted' | 'good' | 'danger' | 'amber' | 'teal' | 'violet'> = {
  neutral: 'muted',
  trade: 'teal',
  alliance: 'good',
  hostile: 'amber',
  war: 'danger',
  peace: 'violet',
}

const STATUS_CELL: Record<string, string> = {
  neutral: 'bg-white/[0.015] text-dim',
  trade: 'bg-teal/10 text-teal',
  alliance: 'bg-good/10 text-good',
  hostile: 'bg-amber/10 text-amber',
  war: 'bg-danger/15 text-danger',
  peace: 'bg-violet/10 text-violet',
}

function pairKey(a: string, b: string) {
  return a < b ? `${a}|${b}` : `${b}|${a}`
}

export function DiplomacyPage() {
  const state = useStore((s) => s.state)
  const selectSettlement = useStore((s) => s.selectSettlement)
  const [details, setDetails] = useState<Record<string, SettlementDetail>>({})
  const [selected, setSelected] = useState<string | null>(null)

  const settlements = state?.settlements ?? []
  const polities = useMemo(
    () => settlements.filter((settlement) => !settlement.ruins && settlement.population > 0),
    [settlements],
  )

  useThrottledEffect(() => {
    if (!state) return
    let cancelled = false
    void Promise.all(polities.map(async (settlement) => {
      try {
        return [settlement.id, await api.getSettlement(state.run.id, settlement.id)] as const
      } catch {
        return null
      }
    })).then((rows) => {
      if (cancelled) return
      const next: Record<string, SettlementDetail> = {}
      for (const row of rows) if (row) next[row[0]] = row[1]
      setDetails(next)
    })
    return () => { cancelled = true }
  }, [state?.run.id, polities.length, state?.run.day])

  const pairs = useMemo(() => {
    const rows: Array<{ a: SettlementSummary; b: SettlementSummary; status: string; trust: number; since?: number; key: string }> = []
    for (let i = 0; i < polities.length; i += 1) {
      for (let j = i + 1; j < polities.length; j += 1) {
        const a = polities[i]
        const b = polities[j]
        const relation = details[a.id]?.diplomacy?.[b.id]
        rows.push({
          a,
          b,
          status: relation?.status ?? 'neutral',
          trust: Number(relation?.trust ?? 0),
          since: relation?.since_day,
          key: pairKey(a.id, b.id),
        })
      }
    }
    return rows
  }, [polities, details])

  const counts = useMemo(() => {
    const tally: Record<string, number> = {}
    for (const pair of pairs) tally[pair.status] = (tally[pair.status] ?? 0) + 1
    return tally
  }, [pairs])

  const meanTrust = pairs.length
    ? pairs.reduce((sum, pair) => sum + pair.trust, 0) / pairs.length
    : 0

  const active = pairs.find((pair) => pair.key === selected)
    ?? pairs.filter((pair) => pair.status !== 'neutral').sort((l, r) => STATUS_ORDER.indexOf(l.status as Status) - STATUS_ORDER.indexOf(r.status as Status))[0]
    ?? pairs[0]
    ?? null

  const relatedEvents = useMemo(() => {
    if (!state || !active) return []
    const ids = new Set([active.a.id, active.b.id])
    return state.events
      .filter((event) => {
        const linked = event.related?.settlements
        return Array.isArray(linked) && linked.some((id) => ids.has(String(id)))
      })
      .slice(-8)
      .reverse()
  }, [state, active])

  if (!state) return <EmptyState icon={<Globe2 size={22} />} title="No run loaded" />

  const matrix = polities.slice(0, 10)

  return (
    <div className="scroll-area h-full">
      <div className="mx-auto max-w-[1500px] space-y-4 px-5 py-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard label="polities" value={fmt(polities.length)} hint={`${settlements.length - polities.length} ruin${settlements.length - polities.length === 1 ? '' : 's'} / abandoned`} icon={<Globe2 size={14} />} tone="amber" />
          <StatCard label="alliances" value={fmt(counts.alliance ?? 0)} hint={`${counts.trade ?? 0} trade agreements`} icon={<Handshake size={14} />} tone="good" />
          <StatCard label="mean trust" value={fmt(meanTrust)} hint={`${pairs.length} recorded relationship${pairs.length === 1 ? '' : 's'}`} icon={<ArrowLeftRight size={14} />} tone="teal" />
          <StatCard label="armed conflict" value={fmt((counts.war ?? 0) + (counts.hostile ?? 0))} hint={`${counts.war ?? 0} open wars`} icon={<Swords size={14} />} tone={counts.war ? 'danger' : 'default'} />
        </div>

        {polities.length < 2 && (
          <Panel title="No neighbours yet" eyebrow="diplomatic record">
            <div className="px-4 py-10 text-center text-[11.5px] leading-relaxed text-muted">
              A settlement has no one to negotiate with until another is founded. Relations appear here the day a second polity exists.
            </div>
          </Panel>
        )}

        {polities.length >= 2 && (
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            <div className="space-y-4 xl:col-span-2">
              <Panel
                title="Relations matrix"
                eyebrow="row → column · trust shown"
                action={<span className="font-mono text-[9px] uppercase tracking-wider text-dim">{matrix.length} × {matrix.length}</span>}
                bodyClassName="overflow-x-auto"
              >
                <table className="w-full border-collapse text-left">
                  <thead>
                    <tr>
                      <th className="sticky left-0 z-10 bg-panel px-3 py-2 font-mono text-[9px] uppercase tracking-wider text-dim">from</th>
                      {matrix.map((settlement) => (
                        <th key={settlement.id} className="px-2 py-2 text-center font-mono text-[9px] uppercase tracking-wider text-dim">
                          <span className="block max-w-[74px] truncate" title={settlement.name}>{settlement.name}</span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {matrix.map((row) => (
                      <tr key={row.id} className="border-t border-edge-soft/60">
                        <th className="sticky left-0 z-10 max-w-[120px] truncate bg-panel px-3 py-1.5 text-[11px] font-medium text-fg">{row.name}</th>
                        {matrix.map((column) => {
                          if (column.id === row.id) {
                            return (
                              <td key={column.id} className="px-1 py-1.5">
                                <div className="flex h-8 items-center justify-center rounded border border-edge-soft/50 bg-white/[0.01]">
                                  <span className="h-px w-4 bg-edge" />
                                </div>
                              </td>
                            )
                          }
                          const relation = details[row.id]?.diplomacy?.[column.id]
                          const status = relation?.status ?? 'neutral'
                          const trust = Number(relation?.trust ?? 0)
                          const key = pairKey(row.id, column.id)
                          return (
                            <td key={column.id} className="px-1 py-1.5">
                              <button
                                type="button"
                                onClick={() => setSelected(key)}
                                title={`${row.name} → ${column.name}: ${STATUS_LABEL[status] ?? status}, trust ${fmt(trust, 1)}`}
                                className={clsx(
                                  'flex h-8 w-full min-w-[62px] flex-col items-center justify-center rounded border border-transparent transition-colors hover:border-edge',
                                  STATUS_CELL[status] ?? STATUS_CELL.neutral,
                                  selected === key && 'border-edge',
                                )}
                              >
                                <span className="num text-[10px] leading-none">{fmt(trust)}</span>
                                <span className="mt-0.5 font-mono text-[7.5px] uppercase tracking-wider opacity-80">{(STATUS_LABEL[status] ?? status).slice(0, 10)}</span>
                              </button>
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="flex flex-wrap gap-2 border-t border-edge-soft/60 px-3 py-2">
                  {(['alliance', 'trade', 'peace', 'neutral', 'hostile', 'war'] as Status[]).map((status) => (
                    <span key={status} className={clsx('inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[8px] uppercase tracking-wider', STATUS_CELL[status])}>
                      <span className="h-1 w-1 rounded-full bg-current" /> {STATUS_LABEL[status]}
                    </span>
                  ))}
                </div>
              </Panel>

              <Panel title="Agreements & conflicts" eyebrow="every pair that is not neutral" bodyClassName="scroll-area max-h-[360px]">
                {pairs.filter((pair) => pair.status !== 'neutral').length === 0 && (
                  <div className="px-4 py-8 text-center text-[11.5px] leading-relaxed text-muted">
                    Every polity is a stranger to every other. Contact begins with proximity, trade knowledge and shared trust.
                  </div>
                )}
                {pairs
                  .filter((pair) => pair.status !== 'neutral')
                  .sort((l, r) => STATUS_ORDER.indexOf(l.status as Status) - STATUS_ORDER.indexOf(r.status as Status))
                  .map((pair) => (
                    <button
                      key={pair.key}
                      type="button"
                      onClick={() => setSelected(pair.key)}
                      className={clsx(
                        'flex w-full items-center justify-between gap-3 border-b border-edge-soft/60 px-4 py-2.5 text-left last:border-0 hover:bg-white/[0.025]',
                        active?.key === pair.key && 'bg-amber/[0.05]',
                      )}
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5 text-[11.5px] text-fg">
                          <span className="truncate">{pair.a.name}</span>
                          <ArrowLeftRight size={10} className="shrink-0 text-dim" />
                          <span className="truncate">{pair.b.name}</span>
                        </div>
                        <div className="font-mono text-[9px] text-dim">
                          since day {pair.since ?? '—'} · trust {fmt(pair.trust, 1)}
                        </div>
                      </div>
                      <Badge tone={STATUS_TONE[pair.status] ?? 'muted'}>{STATUS_LABEL[pair.status] ?? pair.status}</Badge>
                    </button>
                  ))}
              </Panel>
            </div>

            <div className="space-y-4">
              {!active && (
                <Panel title="No relationship selected" eyebrow="dossier">
                  <div className="px-4 py-8 text-center text-[11.5px] text-muted">Select a cell in the matrix.</div>
                </Panel>
              )}
              {active && (
                <Panel
                  title={`${active.a.name} ↔ ${active.b.name}`}
                  eyebrow="relationship dossier"
                  action={<Badge tone={STATUS_TONE[active.status] ?? 'muted'}>{STATUS_LABEL[active.status] ?? active.status}</Badge>}
                >
                  <div className="grid grid-cols-2 gap-3 px-4 py-3">
                    <div>
                      <div className="stat-label">trust</div>
                      <div className="num mt-1 text-[20px] text-teal">{fmt(active.trust, 1)}</div>
                    </div>
                    <div>
                      <div className="stat-label">standing since</div>
                      <div className="num mt-1 text-[20px] text-fg">{active.since ? `day ${active.since}` : '—'}</div>
                    </div>
                  </div>
                  <div className="space-y-2 px-4 pb-4">
                    {[active.a, active.b].map((settlement) => (
                      <button
                        key={settlement.id}
                        type="button"
                        onClick={() => void selectSettlement(settlement.id)}
                        className="flex w-full items-center justify-between rounded border border-edge-soft px-3 py-2 text-left hover:border-edge"
                      >
                        <span className="min-w-0">
                          <span className="block truncate text-[11.5px] text-fg">{settlement.name}</span>
                          <span className="font-mono text-[9px] text-dim">
                            pop {settlement.population} · {settlement.government_label}
                          </span>
                        </span>
                        <span className="num text-[10px] text-muted">{fmt(details[settlement.id]?.trade_volume ?? 0)} traded</span>
                      </button>
                    ))}
                  </div>
                </Panel>
              )}

              <Panel title="Recorded contact" eyebrow="events linking both polities" bodyClassName="scroll-area max-h-[300px]">
                {relatedEvents.length === 0 && (
                  <div className="px-4 py-8 text-center text-[11.5px] leading-relaxed text-muted">
                    No recorded event links these two polities yet. Nothing is shown that did not happen in the log.
                  </div>
                )}
                {relatedEvents.map((event) => (
                  <div key={event.id} className="border-b border-edge-soft/60 px-4 py-2.5 last:border-0">
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-[11px] font-medium leading-snug text-fg">{event.title}</span>
                      <span className="shrink-0 font-mono text-[8.5px] uppercase tracking-wider text-dim">d{event.day}</span>
                    </div>
                    <div className="mt-0.5 line-clamp-2 text-[10.5px] leading-relaxed text-muted">{event.description}</div>
                  </div>
                ))}
              </Panel>

              <Panel title="Reading this page" eyebrow="what is measured">
                <div className="flex gap-2 px-4 py-3 text-[10.5px] leading-relaxed text-muted">
                  <ScrollText size={13} className="mt-0.5 shrink-0 text-dim" />
                  <span>
                    Every cell is the diplomacy record the engine stores for that pair on the current day: status, trust and the day the
                    standing began. Nothing is inferred, and neutral pairs are genuinely uncontacted.
                  </span>
                </div>
              </Panel>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
