import { useMemo } from 'react'
import {
  Users, Landmark, Wheat, Sparkles, HeartPulse, Coins, ArrowUpRight, MapPin,
} from 'lucide-react'
import { useStore } from '../store'
import { MetricChart } from '../components/Charts'
import { EventFeed } from '../components/EventFeed'
import { Badge, EmptyState, Panel, StatCard } from '../components/ui'
import { fmt, pct, presetName, titleCase, happinessTone } from '../lib/format'
import clsx from 'clsx'

export function OverviewPage() {
  const state = useStore((s) => s.state)
  const runs = useStore((s) => s.runs)
  const metrics = useStore((s) => s.metrics)
  const events = useStore((s) => s.events)
  const setPage = useStore((s) => s.setPage)
  const selectAgent = useStore((s) => s.selectAgent)

  const history = metrics.length ? metrics : state?.metrics_history ?? []
  const m = state?.metrics
  const run = state?.run
  const population = state?.agents.filter((agent) => agent.alive).length ?? 0
  const children = state?.agents.filter((agent) => agent.alive && agent.age < 16).length ?? 0
  const settlements = state?.settlements ?? []
  const notable = useMemo(
    () => [...(state?.agents ?? [])]
      .filter((agent) => agent.alive)
      .sort((a, b) => b.generation - a.generation || b.age - a.age)
      .slice(0, 4),
    [state],
  )

  if (!state || !run) {
    return (
      <EmptyState icon={<MapPin size={22} />} title="No world selected">
        Create a world from the sidebar to begin observing.
      </EmptyState>
    )
  }

  const trends = history.length > 8 ? {
    pop: (m?.population ?? 0) - (history[Math.max(0, history.length - 8)]?.population ?? 0),
    happiness: (m?.avg_happiness ?? 0) - (history[Math.max(0, history.length - 8)]?.avg_happiness ?? 0),
  } : { pop: 0, happiness: 0 }

  return (
    <div className="scroll-area h-full">
      <div className="mx-auto max-w-[1500px] space-y-4 px-5 py-4">
        <section className="panel relative overflow-hidden px-5 py-4">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(700px_180px_at_10%_0%,rgba(240,179,90,0.08),transparent_70%)]" />
          <div className="relative flex flex-wrap items-end justify-between gap-4">
            <div>
              <div className="eyebrow mb-1 flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-good pulse-dot" />
                live civilization · {presetName(run.config.preset)}
              </div>
              <h2 className="text-[24px] font-semibold tracking-tight text-fg">{run.world_name}</h2>
              <p className="mt-1 max-w-2xl text-[12.5px] leading-relaxed text-muted">
                Day {fmt(run.day)} · {run.season} · year {run.year}. {population} people are alive across {settlements.length} settlement{settlements.length === 1 ? '' : 's'}.
                {' '}The record currently holds {events.length} events, {run.techs.length} known technologies and {run.language_count} languages.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={run.status === 'running' ? 'good' : run.status === 'error' ? 'danger' : 'amber'}>{run.status}</Badge>
              <Badge tone="violet">{run.era}</Badge>
              <Badge>{run.weather}</Badge>
              <Badge>seed {run.seed}</Badge>
            </div>
          </div>
        </section>

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
          <StatCard label="population" value={fmt(population)} hint={`${children} children · ${run.deaths} deaths total`} icon={<Users size={15} />} trend={trends.pop} tone="teal" />
          <StatCard label="settlements" value={fmt(settlements.length)} hint={`${m?.buildings ?? 0} structures stand`} icon={<Landmark size={15} />} tone="amber" />
          <StatCard label="food stores" value={fmt(m?.food_stores ?? 0, 0)} hint={`${fmt(m?.food ?? 0, 0)} food produced`} icon={<Wheat size={15} />} tone="good" />
          <StatCard label="happiness" value={pct(m?.avg_happiness ?? 0)} hint={`stability ${fmt(m?.stability ?? 0, 0)}`} icon={<HeartPulse size={15} />} trend={trends.happiness} tone="violet" />
          <StatCard label="technology" value={run.era} hint={`${run.techs.length} discoveries`} icon={<Sparkles size={15} />} tone="teal" />
          <StatCard label="trade volume" value={fmt(m?.trades ?? 0)} hint={`inequality ${fmt((m?.inequality ?? 0) * 100, 0)}%`} icon={<Coins size={15} />} tone="amber" />
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <Panel title="Population" eyebrow="demography" className="xl:col-span-2" bodyClassName="px-2 pb-2 pt-3">
            <MetricChart
              data={history as unknown as Array<Record<string, number | string | undefined>>}
              series={[
                { key: 'population', name: 'Population', color: '#58d6c5' },
                { key: 'children', name: 'Children', color: '#9d8cf5' },
                { key: 'elders', name: 'Elders', color: '#f0b35a' },
              ]}
              height={208}
            />
          </Panel>

          <Panel title="The record" eyebrow="recent events" bodyClassName="min-h-0">
            <EventFeed events={events} limit={8} dense className="h-full max-h-[260px]" currentDay={run.day} />
          </Panel>
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <Panel title="Prosperity" eyebrow="economy & wellbeing" className="xl:col-span-2" bodyClassName="px-2 pb-2 pt-3">
            <MetricChart
              data={history as unknown as Array<Record<string, number | string | undefined>>}
              series={[
                { key: 'avg_happiness', name: 'Happiness', color: '#f0b35a' },
                { key: 'stability', name: 'Stability', color: '#58d6c5' },
                { key: 'avg_health', name: 'Health', color: '#9d8cf5' },
              ]}
              height={190}
            />
          </Panel>

          <Panel title="Settlements" eyebrow="the map so far" action={<button type="button" className="btn-ghost" onClick={() => setPage('settlements')}>All <ArrowUpRight size={12} /></button>}>
            <div className="scroll-area max-h-[230px]">
              {settlements.length === 0 && (
                <div className="px-4 py-6 text-center text-[11.5px] text-muted">No settlements yet. People are still wandering.</div>
              )}
              {settlements.map((settlement) => (
                <button
                  key={settlement.id}
                  type="button"
                  className="flex w-full items-center justify-between gap-3 border-b border-edge-soft/60 px-4 py-2.5 text-left last:border-0 hover:bg-white/[0.025]"
                  onClick={() => { setPage('settlements') }}
                >
                  <div className="min-w-0">
                    <div className="truncate text-[12px] font-medium text-fg">{settlement.name}</div>
                    <div className="font-mono text-[9px] text-dim">{settlement.government_label} · founded d{settlement.founded_day}</div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className="num text-[11px] text-teal">{settlement.population} pop</span>
                    <span className="num text-[10px] text-dim">{settlement.buildings} bld</span>
                  </div>
                </button>
              ))}
            </div>
          </Panel>
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <Panel title="Notable people" eyebrow="by generation & age" className="xl:col-span-2">
            <div className="grid grid-cols-1 gap-0 sm:grid-cols-2">
              {notable.length === 0 && <div className="px-4 py-6 text-[11.5px] text-muted">No living agents.</div>}
              {notable.map((agent) => {
                const settlement = settlements.find((item) => item.id === agent.settlement_id)
                return (
                  <button
                    key={agent.id}
                    type="button"
                    onClick={() => void selectAgent(agent.id)}
                    className="flex items-start justify-between gap-3 border-b border-edge-soft/60 px-4 py-3 text-left hover:bg-white/[0.025] sm:odd:border-r"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="truncate text-[12.5px] font-medium text-fg">{agent.name}</span>
                        <span className="font-mono text-[9px] text-dim">gen {agent.generation}</span>
                      </div>
                      <div className="mt-0.5 truncate text-[10.5px] text-muted">{agent.occupation} · {settlement?.name ?? 'unsettled'}</div>
                      <div className="mt-1 line-clamp-1 text-[10.5px] italic text-dim">{agent.thought || agent.state}</div>
                    </div>
                    <div className="shrink-0 text-right">
                      <div className={clsx('num text-[12px]', happinessTone(agent.happiness))}>{fmt(agent.happiness)}</div>
                      <div className="font-mono text-[8.5px] uppercase tracking-wider text-dim">happy</div>
                    </div>
                  </button>
                )
              })}
            </div>
          </Panel>

          <Panel title="Other worlds" eyebrow={`${runs.length} run${runs.length === 1 ? '' : 's'} in this archive`}>
            <div className="scroll-area max-h-[230px]">
              {runs.map((other) => (
                <div key={other.id} className="flex items-center justify-between gap-2 border-b border-edge-soft/60 px-4 py-2.5 last:border-0">
                  <div className="min-w-0">
                    <div className="truncate text-[12px] text-fg">{other.world_name}</div>
                    <div className="font-mono text-[9px] text-dim">day {other.day} · {other.population} alive · {other.preset.replace(/_/g, ' ')}</div>
                  </div>
                  {other.id === run.id ? (
                    <Badge tone="teal">current</Badge>
                  ) : (
                    <span className="num text-[10px] text-dim">{other.status}</span>
                  )}
                </div>
              ))}
            </div>
          </Panel>
        </div>

        {settlements.length > 0 && (
          <Panel title="Settlement comparison" eyebrow="population · happiness · stability">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[700px] text-left">
                <thead>
                  <tr className="border-b border-edge-soft font-mono text-[9px] uppercase tracking-wider text-dim">
                    <th className="px-4 py-2 font-normal">settlement</th>
                    <th className="px-3 py-2 font-normal">government</th>
                    <th className="px-3 py-2 text-right font-normal">pop</th>
                    <th className="px-3 py-2 text-right font-normal">housing</th>
                    <th className="px-3 py-2 text-right font-normal">food</th>
                    <th className="px-3 py-2 text-right font-normal">wealth</th>
                    <th className="px-3 py-2 text-right font-normal">happiness</th>
                  </tr>
                </thead>
                <tbody>
                  {settlements.map((settlement) => (
                    <tr key={settlement.id} className="table-row">
                      <td className="px-4 py-2.5 text-[12px] text-fg">{settlement.name}</td>
                      <td className="px-3 py-2.5 text-[11px] text-muted">{titleCase(settlement.government_label)}</td>
                      <td className="num px-3 py-2.5 text-right text-[11px] text-teal">{settlement.population}</td>
                      <td className="num px-3 py-2.5 text-right text-[11px] text-muted">{settlement.housing_capacity}</td>
                      <td className="num px-3 py-2.5 text-right text-[11px] text-good">{fmt(settlement.food, 0)}</td>
                      <td className="num px-3 py-2.5 text-right text-[11px] text-amber">{fmt(settlement.wealth, 0)}</td>
                      <td className={clsx('num px-3 py-2.5 text-right text-[11px]', happinessTone(settlement.happiness))}>{fmt(settlement.happiness)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        )}
      </div>
    </div>
  )
}
