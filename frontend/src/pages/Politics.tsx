import { useState } from 'react'
import { Crown, Scale, Gavel, Users2, Handshake } from 'lucide-react'
import clsx from 'clsx'
import { useStore } from '../store'
import { api } from '../api'
import { Badge, EmptyState, Meter, Panel, StatCard } from '../components/ui'
import { fmt, pct, titleCase } from '../lib/format'
import type { SettlementDetail } from '../types'
import { useThrottledEffect } from '../lib/useThrottledEffect'

export function PoliticsPage() {
  const state = useStore((s) => s.state)
  const selectSettlement = useStore((s) => s.selectSettlement)
  const [details, setDetails] = useState<Record<string, SettlementDetail>>({})
  const [activeId, setActiveId] = useState<string | null>(null)

  const settlements = state?.settlements ?? []

  useThrottledEffect(() => {
    if (!state) return
    let cancelled = false
    void Promise.all(state.settlements.map(async (settlement) => {
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
      setActiveId((current) => current && next[current] ? current : Object.keys(next)[0] ?? null)
    })
    return () => { cancelled = true }
  }, [state?.run.id, settlements.length, state?.run.day])

  if (!state) return <EmptyState icon={<Crown size={22} />} title="No run loaded" />
  const active = activeId ? details[activeId] : null
  const laws = Object.values(details).reduce((sum, detail) => sum + detail.laws.length, 0)
  const factions = Object.values(details).reduce((sum, detail) => sum + detail.factions.length, 0)
  const leaders = settlements.filter((settlement) => settlement.leader_id && !settlement.ruins)
  const avgLegitimacy = Object.values(details).length
    ? Object.values(details).reduce((sum, detail) => sum + Number(detail.government.legitimacy ?? 0), 0) / Object.values(details).length
    : 0
  const wars = Object.values(details).flatMap((detail) => Object.entries(detail.diplomacy ?? {})).filter(([, value]) => value.status === 'war').length

  return (
    <div className="scroll-area h-full">
      <div className="mx-auto max-w-[1500px] space-y-4 px-5 py-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard label="governed" value={fmt(settlements.length)} hint={`${leaders.length} with a named leader`} icon={<Crown size={14} />} tone="amber" />
          <StatCard label="legitimacy" value={fmt(avgLegitimacy)} hint="mean across settlements" icon={<Scale size={14} />} tone="teal" />
          <StatCard label="laws" value={fmt(laws)} hint={`${factions} organized factions`} icon={<Gavel size={14} />} tone="violet" />
          <StatCard label="open wars" value={fmt(wars)} hint="declared diplomacy states" icon={<Handshake size={14} />} tone={wars ? 'danger' : 'good'} />
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <Panel title="Powers" eyebrow="settlement governments" bodyClassName="scroll-area max-h-[460px]">
            {!settlements.length && <div className="px-4 py-8 text-center text-[11.5px] text-muted">No polities have formed yet.</div>}
            {settlements.map((settlement) => {
              const detail = details[settlement.id]
              return (
                <button
                  key={settlement.id}
                  type="button"
                  onClick={() => setActiveId(settlement.id)}
                  className={clsx(
                    'flex w-full items-center justify-between gap-3 border-b border-edge-soft/60 px-4 py-3 text-left last:border-0 hover:bg-white/[0.025]',
                    activeId === settlement.id && 'bg-amber/[0.05]',
                  )}
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[12px] font-medium text-fg">{settlement.name}</span>
                      {settlement.leader_id && <Crown size={10} className="text-amber" />}
                    </div>
                    <div className="font-mono text-[9px] text-dim">
                      {detail?.government_label ?? settlement.government_label} · pop {settlement.population}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="num text-[11px] text-teal">{fmt(Number(detail?.government.legitimacy ?? 0))}</div>
                    <div className="font-mono text-[8px] uppercase tracking-wider text-dim">legitimacy</div>
                  </div>
                </button>
              )
            })}
          </Panel>

          <div className="xl:col-span-2">
            {!active && <Panel title="No polity selected" eyebrow="government dossier"><div className="px-4 py-10 text-center text-[11.5px] text-muted">Settlements will appear here once founded.</div></Panel>}
            {active && (
              <div className="space-y-4">
                <Panel
                  title={active.name}
                  eyebrow="government dossier"
                  action={<button type="button" className="btn-ghost" onClick={() => void selectSettlement(active.id)}>Open full record</button>}
                >
                  <div className="grid grid-cols-2 gap-3 px-4 py-3 sm:grid-cols-4">
                    <Fact label="system" value={active.government_label ?? titleCase(String(active.government.system ?? 'tribal'))} />
                    <Fact label="leader" value={active.leader_name ?? 'none'} />
                    <Fact label="since day" value={String(active.government.since_day ?? active.founded_day)} />
                    <Fact label="tax rate" value={pct(Number(active.government.tax_rate ?? 0) * 100)} />
                  </div>
                  <div className="px-4 pb-4">
                    <div className="mb-1 flex justify-between font-mono text-[9px] text-dim"><span>legitimacy</span><span>{fmt(Number(active.government.legitimacy ?? 0))}</span></div>
                    <Meter value={Number(active.government.legitimacy ?? 0)} tone="var(--color-amber)" />
                  </div>
                </Panel>

                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <Panel title="Laws" eyebrow="enacted by this settlement">
                    {active.laws.length === 0 && <div className="px-4 py-6 text-[11.5px] leading-relaxed text-muted">No formal laws yet. Custom and kinship govern most conduct.</div>}
                    {active.laws.map((law) => (
                      <div key={law.key} className="border-b border-edge-soft/60 px-4 py-2.5 last:border-0">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[11.5px] font-medium text-fg">{law.title}</span>
                          <Badge tone="muted">support {fmt(law.support)}</Badge>
                        </div>
                        <div className="mt-0.5 text-[10.5px] leading-relaxed text-muted">{law.description}</div>
                        <div className="mt-1 font-mono text-[8.5px] text-dim">enacted day {law.enacted_day}</div>
                      </div>
                    ))}
                  </Panel>

                  <Panel title="Factions" eyebrow="organized interests">
                    {active.factions.length === 0 && <div className="px-4 py-6 text-[11.5px] text-muted">No organized factions have formed.</div>}
                    {active.factions.map((faction) => (
                      <div key={faction.id} className="border-b border-edge-soft/60 px-4 py-2.5 last:border-0">
                        <div className="flex items-center justify-between">
                          <span className="text-[11.5px] font-medium text-fg">{faction.name}</span>
                          <span className="num text-[10px] text-teal">{fmt(faction.share * 100)}%</span>
                        </div>
                        <div className="mt-0.5 text-[10.5px] text-muted">{faction.description}</div>
                        <div className="mt-1 flex items-center gap-1 font-mono text-[8.5px] text-dim"><Users2 size={9} /> {faction.members.length} members · {faction.value}</div>
                      </div>
                    ))}
                  </Panel>
                </div>

                <Panel title="Diplomacy" eyebrow="relations with neighbours">
                  {Object.keys(active.diplomacy ?? {}).length === 0 ? (
                    <div className="px-4 py-6 text-[11.5px] text-muted">No formal relations recorded. Neighbouring settlements remain strangers for now.</div>
                  ) : (
                    <div className="grid grid-cols-1 gap-2 px-4 py-3 sm:grid-cols-2">
                      {Object.entries(active.diplomacy).map(([otherId, relation]) => {
                        const other = state.settlements.find((item) => item.id === otherId)
                        return (
                          <div key={otherId} className="rounded border border-edge-soft px-3 py-2">
                            <div className="flex items-center justify-between">
                              <span className="text-[11.5px] text-fg">{other?.name ?? otherId}</span>
                              <Badge tone={relation.status === 'war' || relation.status === 'hostile' ? 'danger' : relation.status === 'alliance' ? 'good' : relation.status === 'trade' ? 'teal' : 'muted'}>{relation.status}</Badge>
                            </div>
                            <div className="mt-1 font-mono text-[9px] text-dim">trust {fmt(relation.trust)} · since day {relation.since_day ?? '—'}</div>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </Panel>
              </div>
            )}
          </div>
        </div>

        <Panel title="Civic record" eyebrow="leaders in this world">
          <div className="grid grid-cols-1 gap-0 sm:grid-cols-2 lg:grid-cols-3">
            {Object.values(details).flatMap((detail) => detail.members.filter((member) => member.role === 'leader').map((member) => (
              <div key={`${detail.id}-${member.id}`} className="flex items-center justify-between border-b border-edge-soft/60 px-4 py-2.5">
                <div>
                  <div className="flex items-center gap-1.5 text-[11.5px] text-fg"><Crown size={11} className="text-amber" /> {member.name}</div>
                  <div className="font-mono text-[9px] text-dim">{detail.name} · {detail.government_label}</div>
                </div>
                <span className="num text-[10px] text-muted">age {member.age}</span>
              </div>
            )))}
            {!Object.values(details).some((detail) => detail.members.some((member) => member.role === 'leader')) && (
              <div className="px-4 py-6 text-[11.5px] text-muted">No leaders have been recorded yet.</div>
            )}
          </div>
        </Panel>
      </div>
    </div>
  )
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="panel-soft px-2.5 py-2">
      <div className="stat-label">{label}</div>
      <div className="mt-1 truncate text-[12px] text-fg">{value}</div>
    </div>
  )
}
