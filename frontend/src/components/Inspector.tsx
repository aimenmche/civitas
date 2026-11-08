import { useMemo } from 'react'
import {
  X, User, Users, MapPin, Brain, Package, HeartHandshake, ScrollText, Landmark,
  Hammer, Scale, Wallet, Sparkles, CircleDot, Skull, ChevronRight,
} from 'lucide-react'
import clsx from 'clsx'
import type { AgentSummary, MemoryView, SettlementSummary } from '../types'
import { useStore } from '../store'
import { fmt, needTone, pct, titleCase } from '../lib/format'
import { Badge, Divider, EmptyState, KeyValue, Meter, NeedBar, Panel } from './ui'
import { useThrottledEffect } from '../lib/useThrottledEffect'

export function Inspector() {
  const agentId = useStore((state) => state.selectedAgentId)
  const settlementId = useStore((state) => state.selectedSettlementId)
  if (!agentId && !settlementId) return null
  return (
    <aside className="relative z-10 flex w-[382px] shrink-0 flex-col border-l border-edge bg-bg2">
      {agentId ? <AgentInspector agentId={agentId} /> : settlementId ? <SettlementInspector settlementId={settlementId} /> : null}
    </aside>
  )
}

function AgentInspector({ agentId }: { agentId: string }) {
  const detail = useStore((state) => state.agentDetail)
  const summary = useStore((state) => state.state?.agents.find((agent) => agent.id === agentId))
  const state = useStore((state) => state.state)
  const selectAgent = useStore((state) => state.selectAgent)
  const selectSettlement = useStore((state) => state.selectSettlement)
  const reloadAgent = useStore((state) => state.reloadAgent)
  const day = state?.run.day ?? 0

  useThrottledEffect(() => {
    if (agentId) void reloadAgent()
  }, [agentId, day, reloadAgent])

  const liveNeeds = useMemo(() => {
    if (!summary) return null
    return { hunger: summary.hunger, thirst: summary.thirst, health: summary.health }
  }, [summary])

  if (!summary && !detail) {
    return <EmptyState icon={<User size={20} />} title="Loading agent…" />
  }
  const agent = detail
  const name = summary?.name ?? agent?.name ?? 'Unknown'
  const occupation = summary?.occupation ?? agent?.occupation ?? '—'
  const settlementId = summary?.settlement_id ?? agent?.settlement_id ?? null
  const settlementName = agent?.settlement?.name ?? state?.settlements.find((item) => item.id === settlementId)?.name
  const memories: MemoryView[] = agent
    ? [...(agent.memories?.short_term ?? []), ...(agent.memories?.long_term ?? [])]
        .sort((a, b) => b.day - a.day)
        .slice(0, 8)
    : []

  return (
    <>
      <header className="border-b border-edge px-4 py-3.5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="eyebrow mb-1 flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-teal" /> agent dossier
            </div>
            <h2 className="truncate text-[17px] font-semibold text-fg">{name}</h2>
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              <Badge tone="teal">{occupation}</Badge>
              {summary && <Badge>age {summary.age}</Badge>}
              {summary && <Badge tone="violet">gen {summary.generation}</Badge>}
              {summary && !summary.alive && <Badge tone="danger">dead</Badge>}
              {agent?.pregnant && <Badge tone="amber">expecting</Badge>}
            </div>
          </div>
          <button type="button" className="btn-ghost p-1.5" onClick={() => void selectAgent(null)} title="Close inspector">
            <X size={15} />
          </button>
        </div>
        <div className="mt-3 flex items-center justify-between gap-2 font-mono text-[10px] text-dim">
          <span className="flex items-center gap-1">
            <MapPin size={11} /> ({summary?.x ?? '—'}, {summary?.y ?? '—'})
          </span>
          {settlementName ? (
            <button
              type="button"
              className="flex items-center gap-1 text-teal hover:underline"
              onClick={() => settlementId && void selectSettlement(settlementId)}
            >
              <Landmark size={11} /> {settlementName} <ChevronRight size={10} />
            </button>
          ) : (
            <span>unsettled</span>
          )}
        </div>
      </header>

      <div className="scroll-area flex-1 px-4 py-4">
        <Panel eyebrow="now" title={summary?.state ?? 'Current activity'} className="mb-4">
          <div className="space-y-3 px-4 py-3">
            <div className="flex items-start gap-2 text-[12px] leading-relaxed text-fg">
              <CircleDot size={13} className="mt-0.5 shrink-0 text-amber" />
              <span>{summary?.thought || 'No articulated thought is available for the current action.'}</span>
            </div>
            <div className="rounded-md border border-edge-soft bg-bg2/60 px-3 py-2 font-mono text-[10px] leading-relaxed text-muted">
              goal · {summary?.goal ?? 'none stated'}
            </div>
          </div>
        </Panel>

        <div className="mb-2 flex items-center justify-between">
          <h3 className="eyebrow flex items-center gap-1.5"><HeartHandshake size={12} /> needs</h3>
          {liveNeeds && <span className="font-mono text-[9px] text-dim">live</span>}
        </div>
        <div className="mb-4 grid grid-cols-2 gap-x-4 gap-y-2.5">
          {Object.entries(agent?.needs ?? {
            hunger: summary?.hunger ?? 0, thirst: summary?.thirst ?? 0, health: summary?.health ?? 0,
          }).map(([key, value]) => (
            <NeedBar key={key} label={key} value={value} tone={needTone(value)} compact />
          ))}
        </div>

        {agent && (
          <>
            <div className="mb-4 grid grid-cols-3 gap-2">
              <div className="panel-soft px-2.5 py-2">
                <div className="stat-label">wealth</div>
                <div className="num mt-1 text-[13px] text-amber">{fmt(agent.wealth, 1)}</div>
              </div>
              <div className="panel-soft px-2.5 py-2">
                <div className="stat-label">influence</div>
                <div className="num mt-1 text-[13px] text-teal">{fmt(agent.influence, 0)}</div>
              </div>
              <div className="panel-soft px-2.5 py-2">
                <div className="stat-label">reputation</div>
                <div className="num mt-1 text-[13px] text-violet">{fmt(agent.reputation, 0)}</div>
              </div>
            </div>

            {agent.inventory && Object.keys(agent.inventory).length > 0 && (
              <div className="mb-4">
                <h3 className="eyebrow mb-2 flex items-center gap-1.5"><Package size={12} /> carried</h3>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(agent.inventory).map(([item, amount]) => (
                    <Badge key={item} tone="muted">{item} <span className="num text-fg">{fmt(amount, 1)}</span></Badge>
                  ))}
                </div>
              </div>
            )}

            <Divider className="mb-4" />
            <h3 className="eyebrow mb-2 flex items-center gap-1.5"><Brain size={12} /> traits & skills</h3>
            <div className="mb-4 space-y-2">
              {Object.entries(agent.personality ?? {}).slice(0, 4).map(([key, value]) => (
                <div key={key}>
                  <div className="mb-1 flex justify-between text-[10px]"><span className="text-muted capitalize">{key}</span><span className="num text-fg">{fmt(value * 100, 0)}</span></div>
                  <Meter value={value * 100} tone="var(--color-violet)" />
                </div>
              ))}
              {Object.entries(agent.skills ?? {}).sort((a, b) => b[1] - a[1]).slice(0, 4).map(([key, value]) => (
                <div key={key}>
                  <div className="mb-1 flex justify-between text-[10px]"><span className="text-muted capitalize">{key}</span><span className="num text-fg">{fmt(value * 100, 0)}</span></div>
                  <Meter value={value * 100} tone="var(--color-teal)" />
                </div>
              ))}
            </div>

            {agent.research_target && (
              <div className="panel-soft mb-4 px-3 py-2.5">
                <div className="flex items-center justify-between">
                  <span className="stat-label flex items-center gap-1"><Sparkles size={11} /> researching</span>
                  <span className="num text-[10px] text-violet">{fmt(agent.research_progress[agent.research_target] ?? 0, 0)}</span>
                </div>
                <div className="mt-1 text-[12px] text-fg">{titleCase(agent.research_target)}</div>
              </div>
            )}

            <Divider className="mb-4" />
            <h3 className="eyebrow mb-2 flex items-center gap-1.5"><Users size={12} /> family</h3>
            <div className="mb-4 space-y-1.5 text-[11.5px]">
              {agent.partner && (
                <button type="button" className="flex w-full items-center justify-between rounded border border-edge-soft px-2.5 py-1.5 hover:bg-white/5" onClick={() => void selectAgent(agent.partner!.id)}>
                  <span className="text-muted">Partner</span><span className="text-fg">{agent.partner.name}</span>
                </button>
              )}
              {agent.parents?.map((parent) => (
                <button key={parent.id} type="button" className="flex w-full items-center justify-between rounded border border-edge-soft px-2.5 py-1.5 hover:bg-white/5" onClick={() => void selectAgent(parent.id)}>
                  <span className="text-muted">Parent</span><span className="text-fg">{parent.name}{!parent.alive && ' †'}</span>
                </button>
              ))}
              {agent.children?.map((child) => (
                <button key={child.id} type="button" className="flex w-full items-center justify-between rounded border border-edge-soft px-2.5 py-1.5 hover:bg-white/5" onClick={() => void selectAgent(child.id)}>
                  <span className="text-muted">Child</span><span className="text-fg">{child.name} · {child.age}</span>
                </button>
              ))}
              {!agent.partner && !agent.parents?.length && !agent.children?.length && (
                <div className="text-muted">No recorded kin.</div>
              )}
            </div>

            {agent.relationships?.length > 0 && (
              <>
                <Divider className="mb-4" />
                <h3 className="eyebrow mb-2">strongest bonds</h3>
                <div className="mb-4 space-y-1.5">
                  {agent.relationships.slice(0, 5).map((rel) => (
                    <button key={rel.other_id} type="button" className="w-full rounded border border-edge-soft px-2.5 py-1.5 text-left hover:bg-white/5" onClick={() => void selectAgent(rel.other_id)}>
                      <div className="flex items-center justify-between text-[11.5px]">
                        <span className="text-fg">{rel.other_name ?? rel.other_id}{rel.other_alive === false && ' †'}</span>
                        <span className={clsx('num text-[10px]', rel.affinity >= 0 ? 'text-good' : 'text-danger')}>{rel.affinity >= 0 ? '+' : ''}{fmt(rel.affinity, 0)}</span>
                      </div>
                      <div className="mt-0.5 font-mono text-[9px] text-dim">{rel.type ?? 'acquaintance'} · {rel.interactions} meetings · trust {fmt(rel.trust, 0)}</div>
                    </button>
                  ))}
                </div>
              </>
            )}

            <Divider className="mb-4" />
            <h3 className="eyebrow mb-2 flex items-center gap-1.5"><ScrollText size={12} /> memories</h3>
            <div className="space-y-2.5 pb-4">
              {memories.length === 0 && <div className="text-[11.5px] text-muted">No memories recorded.</div>}
              {memories.map((memory) => (
                <div key={memory.id} className="relative border-l border-edge pl-3">
                  <span className="absolute -left-[3px] top-1 h-1.5 w-1.5 rounded-full bg-amber/70" />
                  <div className="flex items-center gap-2 font-mono text-[9px] text-dim">
                    <span>day {memory.day}</span><span>{memory.kind}</span>
                    <span className={memory.sentiment >= 0 ? 'text-good' : 'text-danger'}>{memory.sentiment >= 0 ? '+' : ''}{fmt(memory.sentiment, 1)}</span>
                  </div>
                  <div className="mt-0.5 text-[11.5px] leading-relaxed text-fg/90">{memory.summary}</div>
                </div>
              ))}
            </div>

            {agent.known_techs?.length > 0 && (
              <>
                <div className="eyebrow mb-2">known knowledge</div>
                <div className="flex flex-wrap gap-1.5 pb-4">
                  {agent.known_techs.map((tech) => <Badge key={tech} tone="violet">{titleCase(tech)}</Badge>)}
                </div>
              </>
            )}
          </>
        )}

        {!agent && (
          <div className="space-y-2 text-[11.5px] text-muted">
            <div className="flex justify-between"><span>health</span><span className="num text-fg">{fmt(summary?.health ?? 0)}</span></div>
            <div className="flex justify-between"><span>happiness</span><span className="num text-fg">{fmt(summary?.happiness ?? 0)}</span></div>
            <div className="flex justify-between"><span>action</span><span className="text-fg">{summary?.action?.label ?? summary?.state}</span></div>
          </div>
        )}
      </div>
    </>
  )
}

function SettlementInspector({ settlementId }: { settlementId: string }) {
  const detail = useStore((state) => state.settlementDetail)
  const summary = useStore((state) => state.state?.settlements.find((item) => item.id === settlementId))
  const day = useStore((state) => state.state?.run.day ?? 0)
  const selectSettlement = useStore((state) => state.selectSettlement)
  const selectAgent = useStore((state) => state.selectAgent)
  const reloadSettlement = useStore((state) => state.reloadSettlement)

  useThrottledEffect(() => {
    if (settlementId) void reloadSettlement()
  }, [settlementId, day, reloadSettlement])

  const settlement: SettlementSummary | undefined = summary
  if (!settlement && !detail) return <EmptyState icon={<Landmark size={20} />} title="Loading settlement…" />

  const name = settlement?.name ?? detail?.name ?? 'Settlement'
  return (
    <>
      <header className="border-b border-edge px-4 py-3.5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="eyebrow mb-1 flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-amber" /> settlement record</div>
            <h2 className="truncate text-[17px] font-semibold text-fg">{name}</h2>
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              <Badge tone="amber">{detail?.government_label ?? settlement?.government_label}</Badge>
              <Badge>pop {settlement?.population}</Badge>
              <Badge tone="teal">housing {settlement?.housing_capacity}</Badge>
              {settlement?.ruins && <Badge tone="danger">ruins</Badge>}
            </div>
          </div>
          <button type="button" className="btn-ghost p-1.5" onClick={() => void selectSettlement(null)} title="Close inspector">
            <X size={15} />
          </button>
        </div>
        <div className="mt-3 flex items-center justify-between font-mono text-[10px] text-dim">
          <span className="flex items-center gap-1"><MapPin size={11} /> ({settlement?.x}, {settlement?.y})</span>
          <span>founded day {settlement?.founded_day}</span>
        </div>
      </header>

      <div className="scroll-area flex-1 px-4 py-4">
        <div className="mb-4 grid grid-cols-3 gap-2">
          <div className="panel-soft px-2.5 py-2"><div className="stat-label">stability</div><div className="num mt-1 text-[13px] text-teal">{fmt(settlement?.stability ?? 0)}</div></div>
          <div className="panel-soft px-2.5 py-2"><div className="stat-label">happiness</div><div className="num mt-1 text-[13px] text-amber">{fmt(settlement?.happiness ?? 0)}</div></div>
          <div className="panel-soft px-2.5 py-2"><div className="stat-label">safety</div><div className="num mt-1 text-[13px] text-violet">{fmt(settlement?.safety ?? 0)}</div></div>
        </div>

        {detail && (
          <>
            <h3 className="eyebrow mb-2 flex items-center gap-1.5"><Package size={12} /> stores & production</h3>
            <div className="mb-4 space-y-2">
              {Object.entries(detail.storage).sort((a, b) => b[1] - a[1]).map(([item, amount]) => (
                <div key={item}>
                  <div className="mb-1 flex justify-between text-[10px]"><span className="text-muted capitalize">{item}</span><span className="num text-fg">{fmt(amount, 1)}</span></div>
                  <Meter value={amount} max={Math.max(12, ...Object.values(detail.storage))} tone={item === 'food' ? 'var(--color-good)' : item === 'wood' ? 'var(--color-amber)' : 'var(--color-teal)'} />
                </div>
              ))}
              <div className="flex justify-between font-mono text-[9px] text-dim"><span>capacity used</span><span>{fmt(Object.values(detail.storage).reduce((a, b) => a + b, 0), 0)} / {fmt(detail.storage_capacity, 0)}</span></div>
            </div>

            <Divider className="mb-3" />
            <h3 className="eyebrow mb-2 flex items-center gap-1.5"><Hammer size={12} /> structures</h3>
            <div className="mb-3 flex flex-wrap gap-1.5">
              {detail.buildings_detail.map((building, index) => (
                <Badge key={`${building.type}-${index}`} tone={building.type.includes('house') || building.type === 'shelter' ? 'teal' : 'muted'}>
                  {building.name}
                </Badge>
              ))}
              {!detail.buildings_detail.length && <span className="text-[11px] text-muted">No structures yet.</span>}
            </div>
            {detail.build_queue.map((project) => (
              <div key={project.id} className="mb-2 rounded border border-edge-soft px-2.5 py-2">
                <div className="flex justify-between text-[11px]"><span className="text-fg">{project.name}</span><span className="num text-[10px] text-amber">{fmt(project.work_done, 0)} / {fmt(project.work_required, 0)}</span></div>
                <Meter className="mt-1.5" value={project.work_done} max={Math.max(1, project.work_required)} tone="var(--color-amber)" />
              </div>
            ))}

            <Divider className="my-3" />
            <h3 className="eyebrow mb-2 flex items-center gap-1.5"><Users size={12} /> citizens · {detail.members.length}</h3>
            <div className="mb-3 max-h-44 space-y-1 overflow-y-auto pr-1">
              {detail.members.map((member) => (
                <button key={member.id} type="button" className="flex w-full items-center justify-between rounded border border-edge-soft px-2.5 py-1.5 text-left hover:bg-white/5" onClick={() => void selectAgent(member.id)}>
                  <span className="text-[11.5px] text-fg">{member.name}</span>
                  <span className="font-mono text-[9px] text-dim">{member.role === 'leader' ? 'leader' : member.occupation} · {member.age}</span>
                </button>
              ))}
            </div>

            <Divider className="mb-3" />
            <h3 className="eyebrow mb-2 flex items-center gap-1.5"><Scale size={12} /> government</h3>
            <div className="mb-3">
              <KeyValue label="system" value={detail.government_label ?? detail.government.system ?? '—'} />
              <KeyValue label="leader" value={detail.leader_name ?? 'none'} />
              <KeyValue label="legitimacy" value={fmt(Number(detail.government.legitimacy ?? 0), 0)} />
              <KeyValue label="tax rate" value={pct(Number(detail.government.tax_rate ?? 0) * 100)} />
            </div>
            {detail.factions.length > 0 && (
              <div className="mb-3 space-y-1.5">
                {detail.factions.map((faction) => (
                  <div key={faction.id} className="rounded border border-edge-soft px-2.5 py-2">
                    <div className="flex justify-between text-[11px]"><span className="text-fg">{faction.name}</span><span className="num text-[10px] text-teal">{fmt(faction.share * 100)}%</span></div>
                    <div className="mt-0.5 text-[10px] text-muted">{faction.description}</div>
                  </div>
                ))}
              </div>
            )}
            {detail.laws.length > 0 && (
              <div className="mb-3">
                <div className="mb-1 font-mono text-[9px] uppercase tracking-wider text-dim">laws</div>
                {detail.laws.map((law) => (
                  <div key={law.key} className="mb-1 rounded border border-edge-soft px-2.5 py-1.5">
                    <div className="text-[11px] text-fg">{law.title}</div>
                    <div className="text-[10px] text-muted">{law.description}</div>
                  </div>
                ))}
              </div>
            )}

            {detail.known_techs.length > 0 && (
              <>
                <div className="eyebrow mb-2">knowledge</div>
                <div className="mb-3 flex flex-wrap gap-1.5">{detail.known_techs.map((tech) => <Badge key={tech} tone="violet">{titleCase(tech)}</Badge>)}</div>
              </>
            )}

            {detail.language && (
              <>
                <div className="eyebrow mb-2 flex items-center gap-1.5"><Wallet size={12} /> language · {detail.language.name}</div>
                <div className="mb-2 flex flex-wrap gap-1.5">
                  {Object.entries(detail.language.lexicon ?? {}).slice(0, 10).map(([concept, word]) => (
                    <span key={concept} className="rounded border border-edge-soft px-2 py-0.5 font-mono text-[10px] text-muted">{concept} <span className="text-teal">{word}</span></span>
                  ))}
                </div>
              </>
            )}

            <Divider className="my-3" />
            <h3 className="eyebrow mb-2">market</h3>
            <div className="mb-3 space-y-1">
              {Object.entries(detail.market_prices ?? {}).map(([item, price]) => (
                <div key={item} className="flex justify-between text-[11px]"><span className="capitalize text-muted">{item}</span><span className="num text-fg">{fmt(price, 2)}</span></div>
              ))}
              {!Object.keys(detail.market_prices ?? {}).length && <div className="text-[11px] text-muted">No money prices yet; exchange is by barter.</div>}
            </div>

            {detail.history.length > 0 && (
              <>
                <div className="eyebrow mb-2">recent history</div>
                <div className="space-y-1.5 pb-4">
                  {[...detail.history].reverse().slice(0, 6).map((entry, index) => (
                    <div key={index} className="flex justify-between font-mono text-[10px] text-muted">
                      <span>day {String(entry.day ?? '—')}</span>
                      <span>pop {String(entry.population ?? '—')} · buildings {String(entry.buildings ?? '—')}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </div>
    </>
  )
}
