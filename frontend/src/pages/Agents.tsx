import { useMemo, useState } from 'react'
import { Search, Users, Skull, Baby, UserRound, ChevronDown } from 'lucide-react'
import clsx from 'clsx'
import { useStore } from '../store'
import { Badge, EmptyState, Meter, Panel, StatCard } from '../components/ui'
import { fmt, happinessTone, needTone, titleCase } from '../lib/format'

type SortKey = 'name' | 'age' | 'happiness' | 'health' | 'generation'

export function AgentsPage() {
  const state = useStore((s) => s.state)
  const selectAgent = useStore((s) => s.selectAgent)
  const selectedAgentId = useStore((s) => s.selectedAgentId)
  const [query, setQuery] = useState('')
  const [settlementFilter, setSettlementFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'alive' | 'dead'>('alive')
  const [sort, setSort] = useState<SortKey>('age')

  const agents = state?.agents ?? []
  const settlements = state?.settlements ?? []

  const filtered = useMemo(() => {
    const list = agents.filter((agent) => {
      if (statusFilter !== 'all' && agent.alive !== (statusFilter === 'alive')) return false
      if (settlementFilter !== 'all') {
        if (settlementFilter === 'unsettled' ? agent.settlement_id !== null : agent.settlement_id !== settlementFilter) return false
      }
      if (query.trim()) {
        const haystack = `${agent.name} ${agent.occupation} ${agent.state} ${agent.goal}`.toLowerCase()
        if (!haystack.includes(query.toLowerCase().trim())) return false
      }
      return true
    })
    return list.sort((a, b) => {
      switch (sort) {
        case 'name': return a.name.localeCompare(b.name)
        case 'happiness': return b.happiness - a.happiness
        case 'health': return b.health - a.health
        case 'generation': return b.generation - a.generation || b.age - a.age
        default: return b.age - a.age
      }
    })
  }, [agents, statusFilter, settlementFilter, query, sort])

  if (!state) return <EmptyState icon={<Users size={22} />} title="No run loaded" />

  const alive = agents.filter((agent) => agent.alive)
  const children = alive.filter((agent) => agent.age < 16)
  const elders = alive.filter((agent) => agent.age >= 55)
  const avgHappiness = alive.length ? alive.reduce((sum, agent) => sum + agent.happiness, 0) / alive.length : 0

  return (
    <div className="scroll-area h-full">
      <div className="mx-auto max-w-[1500px] space-y-4 px-5 py-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          <StatCard label="living" value={fmt(alive.length)} hint={`${agents.length} ever born`} icon={<Users size={14} />} tone="teal" />
          <StatCard label="children" value={fmt(children.length)} hint="under 16" icon={<Baby size={14} />} tone="violet" />
          <StatCard label="elders" value={fmt(elders.length)} hint="55 and older" icon={<UserRound size={14} />} tone="amber" />
          <StatCard label="dead" value={fmt(state.run.deaths)} hint="recorded deaths" icon={<Skull size={14} />} tone="danger" />
          <StatCard label="avg happiness" value={fmt(avgHappiness)} hint={`${state.run.family_count} families`} icon={<Users size={14} />} tone="amber" />
        </div>

        <Panel
          title="People of this world"
          eyebrow={`${filtered.length} shown`}
          action={
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search size={12} className="pointer-events-none absolute left-2.5 top-2.5 text-dim" />
                <input
                  className="input w-52 py-1.5 pl-7 text-[11px]"
                  placeholder="Search name, role, action…"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </div>
              <select className="input w-auto py-1.5 text-[11px]" value={settlementFilter} onChange={(event) => setSettlementFilter(event.target.value)}>
                <option value="all">All settlements</option>
                <option value="unsettled">Unsettled</option>
                {settlements.map((settlement) => <option key={settlement.id} value={settlement.id}>{settlement.name}</option>)}
              </select>
              <select className="input w-auto py-1.5 text-[11px]" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}>
                <option value="alive">Living</option>
                <option value="all">Everyone</option>
                <option value="dead">Dead</option>
              </select>
              <select className="input w-auto py-1.5 text-[11px]" value={sort} onChange={(event) => setSort(event.target.value as SortKey)}>
                <option value="age">Sort by age</option>
                <option value="name">Sort by name</option>
                <option value="happiness">Sort by happiness</option>
                <option value="health">Sort by health</option>
                <option value="generation">Sort by generation</option>
              </select>
            </div>
          }
          bodyClassName="min-h-0"
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[960px] text-left">
              <thead className="sticky top-0 z-10 bg-panel">
                <tr className="border-b border-edge-soft font-mono text-[9px] uppercase tracking-wider text-dim">
                  <th className="px-4 py-2 font-normal">name</th>
                  <th className="px-3 py-2 font-normal">role · settlement</th>
                  <th className="px-3 py-2 text-right font-normal">age</th>
                  <th className="px-3 py-2 text-right font-normal">health</th>
                  <th className="px-3 py-2 text-right font-normal">hunger</th>
                  <th className="px-3 py-2 text-right font-normal">thirst</th>
                  <th className="px-3 py-2 font-normal">current action</th>
                  <th className="px-3 py-2 text-right font-normal">happy</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((agent) => {
                  const settlement = settlements.find((item) => item.id === agent.settlement_id)
                  const selected = agent.id === selectedAgentId
                  return (
                    <tr
                      key={agent.id}
                      onClick={() => void selectAgent(agent.id)}
                      className={clsx('table-row cursor-pointer', selected && 'bg-amber/[0.06]')}
                    >
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2">
                          <span className={clsx('h-1.5 w-1.5 rounded-full', agent.alive ? 'bg-teal' : 'bg-danger')} />
                          <span className={clsx('text-[12px] font-medium', agent.alive ? 'text-fg' : 'text-dim line-through')}>{agent.name}</span>
                          {agent.generation > 0 && <span className="font-mono text-[8.5px] uppercase tracking-wider text-violet">gen {agent.generation}</span>}
                        </div>
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="text-[11px] text-muted">{agent.occupation}</div>
                        <div className="font-mono text-[9px] text-dim">{settlement?.name ?? 'unsettled'}</div>
                      </td>
                      <td className="num px-3 py-2.5 text-right text-[11px] text-muted">{agent.age}</td>
                      <td className="px-3 py-2.5 text-right">
                        <span className="num text-[11px]" style={{ color: needTone(agent.health) }}>{fmt(agent.health)}</span>
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        <span className="num text-[11px]" style={{ color: needTone(agent.hunger) }}>{fmt(agent.hunger)}</span>
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        <span className="num text-[11px]" style={{ color: needTone(agent.thirst) }}>{fmt(agent.thirst)}</span>
                      </td>
                      <td className="max-w-[280px] px-3 py-2.5">
                        <div className="truncate text-[11px] text-fg/80">{agent.state}</div>
                        <div className="truncate font-mono text-[9px] text-dim">{agent.action?.label ?? agent.goal}</div>
                      </td>
                      <td className={clsx('num px-3 py-2.5 text-right text-[11px]', happinessTone(agent.happiness))}>{fmt(agent.happiness)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {!filtered.length && <div className="px-4 py-10 text-center text-[12px] text-muted">Nobody matches those filters.</div>}
          </div>
        </Panel>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <Panel title="Roles in this world" eyebrow="occupations">
            <div className="flex flex-wrap gap-1.5 px-4 py-3">
              {Object.entries(
                alive.reduce<Record<string, number>>((acc, agent) => {
                  acc[agent.occupation] = (acc[agent.occupation] ?? 0) + 1
                  return acc
                }, {}),
              ).sort((a, b) => b[1] - a[1]).map(([role, count]) => (
                <Badge key={role} tone="muted">{titleCase(role)} <span className="num text-fg">{count}</span></Badge>
              ))}
            </div>
          </Panel>
          <Panel title="Generations" eyebrow="who was born here">
            <div className="space-y-2 px-4 py-3">
              {Object.entries(
                alive.reduce<Record<string, number>>((acc, agent) => {
                  const key = String(agent.generation)
                  acc[key] = (acc[key] ?? 0) + 1
                  return acc
                }, {}),
              ).sort((a, b) => Number(a[0]) - Number(b[0])).map(([generation, count]) => (
                <div key={generation}>
                  <div className="mb-1 flex justify-between text-[10.5px]"><span className="text-muted">Generation {generation}</span><span className="num text-fg">{count} alive</span></div>
                  <Meter value={count} max={Math.max(1, alive.length)} tone="var(--color-violet)" />
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  )
}
