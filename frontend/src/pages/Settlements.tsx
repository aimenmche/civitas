import { useMemo, useState } from 'react'
import { Landmark, Crown, Wheat, Hammer, Users2, Search } from 'lucide-react'
import clsx from 'clsx'
import { useStore } from '../store'
import { Badge, Meter, Panel, StatCard, EmptyState } from '../components/ui'
import { fmt, happinessTone, titleCase } from '../lib/format'

type SortKey = 'population' | 'wealth' | 'happiness' | 'founded'

export function SettlementsPage() {
  const state = useStore((s) => s.state)
  const selectSettlement = useStore((s) => s.selectSettlement)
  const selectedSettlementId = useStore((s) => s.selectedSettlementId)
  const [sort, setSort] = useState<SortKey>('population')
  const [query, setQuery] = useState('')

  const settlements = state?.settlements ?? []
  const agents = state?.agents ?? []
  const filtered = useMemo(() => {
    const list = settlements.filter((item) => !query.trim() || item.name.toLowerCase().includes(query.toLowerCase().trim()))
    return [...list].sort((a, b) => {
      switch (sort) {
        case 'wealth': return b.wealth - a.wealth
        case 'happiness': return b.happiness - a.happiness
        case 'founded': return a.founded_day - b.founded_day
        default: return b.population - a.population
      }
    })
  }, [settlements, query, sort])

  if (!state) return <EmptyState icon={<Landmark size={22} />} title="No run loaded" />
  const totalPop = settlements.reduce((sum, item) => sum + item.population, 0)
  const totalBuildings = settlements.reduce((sum, item) => sum + item.buildings, 0)
  const totalHousing = settlements.reduce((sum, item) => sum + item.housing_capacity, 0)
  const avgStability = settlements.length ? settlements.reduce((sum, item) => sum + item.stability, 0) / settlements.length : 0

  return (
    <div className="scroll-area h-full">
      <div className="mx-auto max-w-[1500px] space-y-4 px-5 py-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard label="settlements" value={fmt(settlements.length)} hint={`${state.run.settlements} standing`} icon={<Landmark size={14} />} tone="amber" />
          <StatCard label="urban population" value={fmt(totalPop)} hint={`${agents.filter((a) => a.alive && !a.settlement_id).length} living unsettled`} icon={<Users2 size={14} />} tone="teal" />
          <StatCard label="structures" value={fmt(totalBuildings)} hint={`${totalHousing} housing capacity`} icon={<Hammer size={14} />} tone="violet" />
          <StatCard label="mean stability" value={fmt(avgStability)} hint={`${state.run.era} era`} icon={<Crown size={14} />} tone="good" />
        </div>

        <Panel
          title="Known settlements"
          eyebrow="founded by the living"
          action={
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search size={12} className="pointer-events-none absolute left-2.5 top-2.5 text-dim" />
                <input className="input w-40 py-1.5 pl-7 text-[11px]" placeholder="Find a settlement…" value={query} onChange={(event) => setQuery(event.target.value)} />
              </div>
              <select className="input w-auto py-1.5 text-[11px]" value={sort} onChange={(event) => setSort(event.target.value as SortKey)}>
                <option value="population">Largest first</option>
                <option value="wealth">Wealthiest first</option>
                <option value="happiness">Happiest first</option>
                <option value="founded">Oldest first</option>
              </select>
            </div>
          }
          bodyClassName="p-4"
        >
          {!filtered.length && (
            <div className="py-10 text-center">
              <div className="text-[13px] text-fg">No settlements yet</div>
              <div className="mt-1 text-[11.5px] text-muted">Founding requires a group with enough food and wood. Watch for the first claim on the map.</div>
            </div>
          )}
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {filtered.map((settlement) => {
              const selected = settlement.id === selectedSettlementId
              return (
                <button
                  key={settlement.id}
                  type="button"
                  onClick={() => void selectSettlement(settlement.id)}
                  className={clsx(
                    'panel-soft group relative flex flex-col gap-3 p-3.5 text-left transition-colors hover:border-dim',
                    selected && 'border-amber/40 bg-amber/[0.05]',
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-1.5">
                        <Landmark size={13} className="text-amber" />
                        <span className="text-[14px] font-semibold text-fg">{settlement.name}</span>
                        {settlement.ruins && <Badge tone="danger">ruins</Badge>}
                      </div>
                      <div className="mt-0.5 font-mono text-[9px] text-dim">
                        founded day {settlement.founded_day} · ({settlement.x}, {settlement.y}) · radius {settlement.territory_radius}
                      </div>
                    </div>
                    <Badge tone="teal">{settlement.population} pop</Badge>
                  </div>

                  <div className="grid grid-cols-4 gap-1.5 text-center">
                    <MiniStat label="housing" value={fmt(settlement.housing_capacity)} />
                    <MiniStat label="buildings" value={fmt(settlement.buildings)} />
                    <MiniStat label="food" value={fmt(settlement.food, 0)} />
                    <MiniStat label="wealth" value={fmt(settlement.wealth, 0)} />
                  </div>

                  <div className="space-y-1.5">
                    <div>
                      <div className="mb-1 flex justify-between font-mono text-[9px] text-dim"><span>happiness</span><span>{fmt(settlement.happiness)}</span></div>
                      <Meter value={settlement.happiness} tone="var(--color-amber)" />
                    </div>
                    <div>
                      <div className="mb-1 flex justify-between font-mono text-[9px] text-dim"><span>stability</span><span>{fmt(settlement.stability)}</span></div>
                      <Meter value={settlement.stability} tone="var(--color-teal)" />
                    </div>
                  </div>

                  <div className="flex items-center justify-between gap-2 border-t border-edge-soft pt-2">
                    <div className="min-w-0">
                      <div className="truncate text-[10.5px] text-muted">{titleCase(settlement.government_label)}</div>
                      <div className="truncate font-mono text-[9px] text-dim">{settlement.leader_name ? `leader: ${settlement.leader_name}` : 'no leader'}</div>
                    </div>
                    <div className="flex flex-wrap justify-end gap-1">
                      {settlement.uses_currency ? <Badge tone="amber">currency</Badge> : <Badge>barter</Badge>}
                      {settlement.stability >= 65 && <Badge tone="teal">stable</Badge>}
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        </Panel>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <Panel title="Where people live" eyebrow="population by settlement">
            <div className="space-y-2.5 px-4 py-3">
              {settlements.map((settlement) => (
                <div key={settlement.id}>
                  <div className="mb-1 flex justify-between text-[10.5px]"><span className="text-fg">{settlement.name}</span><span className="num text-muted">{settlement.population} residents</span></div>
                  <Meter value={settlement.population} max={Math.max(1, ...settlements.map((item) => item.population))} tone="var(--color-teal)" />
                </div>
              ))}
            </div>
          </Panel>
          <Panel title="Food security" eyebrow="stores vs population">
            <div className="px-4 py-3">
              {settlements.length === 0 && <div className="text-[11.5px] text-muted">No data yet.</div>}
              {settlements.map((settlement) => {
                const perPerson = settlement.food / Math.max(1, settlement.population)
                return (
                  <div key={settlement.id} className="mb-3 last:mb-0">
                    <div className="mb-1 flex justify-between text-[10.5px]">
                      <span className="flex items-center gap-1 text-fg"><Wheat size={10} className="text-good" /> {settlement.name}</span>
                      <span className={clsx('num', perPerson >= 3 ? 'text-good' : perPerson >= 1 ? 'text-amber' : 'text-danger')}>{fmt(perPerson, 1)} food / person</span>
                    </div>
                    <Meter value={Math.min(100, perPerson * 12)} tone={perPerson >= 3 ? 'var(--color-good)' : perPerson >= 1 ? 'var(--color-amber)' : 'var(--color-danger)'} />
                  </div>
                )
              })}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  )
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-edge-soft bg-bg2/40 px-1 py-1.5">
      <div className="font-mono text-[8px] uppercase tracking-wider text-dim">{label}</div>
      <div className="num text-[11px] text-fg">{value}</div>
    </div>
  )
}
