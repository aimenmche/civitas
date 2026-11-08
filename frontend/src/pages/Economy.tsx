import { useMemo, useState } from 'react'
import { Coins, Wheat, Droplets, TrendingUp, ArrowLeftRight, Scale } from 'lucide-react'
import clsx from 'clsx'
import { useStore } from '../store'
import { api } from '../api'
import { MetricChart } from '../components/Charts'
import { Badge, EmptyState, Meter, Panel, StatCard } from '../components/ui'
import { fmt, pct, titleCase } from '../lib/format'
import type { SettlementDetail } from '../types'
import { useThrottledEffect } from '../lib/useThrottledEffect'

export function EconomyPage() {
  const state = useStore((s) => s.state)
  const metrics = useStore((s) => s.metrics)
  const selectSettlement = useStore((s) => s.selectSettlement)
  const [details, setDetails] = useState<Record<string, SettlementDetail>>({})

  const settlements = state?.settlements ?? []
  const history = metrics.length ? metrics : state?.metrics_history ?? []

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
    })
    return () => { cancelled = true }
  }, [state?.run.id, settlements.length, state?.run.day])

  const transactions = state?.transactions ?? []
  const markets = useMemo(
    () => Object.values(details).filter((detail) => Object.keys(detail.market_prices ?? {}).length > 0),
    [details],
  )

  if (!state) return <EmptyState icon={<Coins size={22} />} title="No run loaded" />
  const m = state.metrics
  const totalWealth = settlements.reduce((sum, item) => sum + item.wealth, 0)
  const totalFood = settlements.reduce((sum, item) => sum + item.food, 0)
  const tradeCount = m?.trades ?? 0

  return (
    <div className="scroll-area h-full">
      <div className="mx-auto max-w-[1500px] space-y-4 px-5 py-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard label="food stores" value={fmt(totalFood, 0)} hint={`${fmt(m?.food ?? 0, 0)} food in the world`} icon={<Wheat size={14} />} tone="good" />
          <StatCard label="wealth" value={fmt(totalWealth, 0)} hint={`max ${fmt(m?.wealth_max ?? 0, 0)} · median ${fmt(m?.wealth_median ?? 0, 0)}`} icon={<Coins size={14} />} tone="amber" />
          <StatCard label="trades" value={fmt(tradeCount)} hint={`${m?.trades_today ?? 0} exchanges today`} icon={<ArrowLeftRight size={14} />} tone="teal" />
          <StatCard label="inequality" value={pct((m?.inequality ?? 0) * 100)} hint="Gini coefficient of personal wealth" icon={<Scale size={14} />} tone="violet" />
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <Panel title="Food & water" eyebrow="material basis" className="xl:col-span-2" bodyClassName="px-2 pb-2 pt-3">
            <MetricChart
              data={history as unknown as Array<Record<string, number | string | undefined>>}
              series={[
                { key: 'food_stores', name: 'Food stores', color: '#7ed491' },
                { key: 'water', name: 'Water', color: '#58d6c5' },
                { key: 'food', name: 'Food produced', color: '#f0b35a' },
              ]}
              height={200}
            />
          </Panel>
          <Panel title="Wealth" eyebrow="distribution over time" bodyClassName="px-2 pb-2 pt-3">
            <MetricChart
              data={history as unknown as Array<Record<string, number | string | undefined>>}
              series={[
                { key: 'inequality', name: 'Inequality', color: '#9d8cf5' },
                { key: 'wealth_median', name: 'Median wealth', color: '#f0b35a' },
                { key: 'wealth_max', name: 'Richest', color: '#58d6c5' },
              ]}
              height={200}
            />
          </Panel>
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <Panel title="Settlement economies" eyebrow="stores and exchange">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[460px] text-left">
                <thead>
                  <tr className="border-b border-edge-soft font-mono text-[9px] uppercase tracking-wider text-dim">
                    <th className="px-4 py-2 font-normal">settlement</th>
                    <th className="px-3 py-2 text-right font-normal">food</th>
                    <th className="px-3 py-2 text-right font-normal">wealth</th>
                    <th className="px-3 py-2 text-right font-normal">trade</th>
                    <th className="px-3 py-2 font-normal">system</th>
                  </tr>
                </thead>
                <tbody>
                  {settlements.map((settlement) => {
                    const detail = details[settlement.id]
                    return (
                      <tr key={settlement.id} className="table-row cursor-pointer" onClick={() => void selectSettlement(settlement.id)}>
                        <td className="px-4 py-2.5 text-[12px] text-fg">{settlement.name}</td>
                        <td className="num px-3 py-2.5 text-right text-[11px] text-good">{fmt(settlement.food, 1)}</td>
                        <td className="num px-3 py-2.5 text-right text-[11px] text-amber">{fmt(settlement.wealth, 1)}</td>
                        <td className="num px-3 py-2.5 text-right text-[11px] text-muted">{fmt(detail?.trade_volume ?? 0, 1)}</td>
                        <td className="px-3 py-2.5">
                          <Badge tone={settlement.uses_currency ? 'amber' : 'muted'}>{settlement.uses_currency ? 'currency' : 'barter'}</Badge>
                          <span className="ml-1.5 font-mono text-[9px] text-dim">{titleCase(settlement.government_label)}</span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              {!settlements.length && <div className="px-4 py-8 text-center text-[11.5px] text-muted">No settlements have formed yet. Barter happens between individuals in the meantime.</div>}
            </div>
          </Panel>

          <Panel title="Markets" eyebrow="prices set by settlement custom">
            <div className="scroll-area max-h-[300px] px-4 py-3">
              {!markets.length && (
                <div className="py-6 text-center text-[11.5px] leading-relaxed text-muted">
                  No formal markets yet. Markets appear when a settlement knows Trade and grows large enough to build one.
                  {' '}Until then, people exchange goods directly through barter.
                </div>
              )}
              {markets.map((detail) => (
                <div key={detail.id} className="mb-4 last:mb-0">
                  <div className="mb-1.5 flex items-center justify-between">
                    <span className="text-[12px] font-medium text-fg">{detail.name}</span>
                    <Badge tone="teal">{fmt(detail.trade_volume, 0)} traded</Badge>
                  </div>
                  <div className="space-y-1">
                    {Object.entries(detail.market_prices).map(([item, price]) => (
                      <div key={item} className="flex items-center justify-between text-[11px]">
                        <span className="capitalize text-muted">{item}</span>
                        <span className="num text-fg">{fmt(price, 2)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <Panel title="Recent exchange" eyebrow={`${transactions.length} recorded`} bodyClassName="scroll-area max-h-[320px]">
            {!transactions.length && <div className="px-4 py-8 text-center text-[11.5px] text-muted">No trades recorded yet.</div>}
            {[...transactions].reverse().map((transaction, index) => {
              const from = state.agents.find((agent) => agent.id === transaction.from)
              const to = state.agents.find((agent) => agent.id === transaction.to)
              return (
                <div key={index} className="flex items-start gap-3 border-b border-edge-soft/60 px-4 py-2 last:border-0">
                  <span className="num w-10 shrink-0 text-[10px] text-dim">d{transaction.day}</span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1 text-[11px] text-fg">
                      <span className="truncate">{from?.name ?? transaction.from ?? 'settlement'}</span>
                      <ArrowLeftRight size={10} className="shrink-0 text-dim" />
                      <span className="truncate">{to?.name ?? transaction.to ?? 'settlement'}</span>
                      <span className="ml-auto shrink-0 text-[10px] text-dim">{titleCase(transaction.kind)}</span>
                    </div>
                    {transaction.items && (
                      <div className="mt-0.5 flex flex-wrap gap-1">
                        {Object.entries(transaction.items).map(([item, amount]) => (
                          <span key={item} className="font-mono text-[9px] text-muted">{item} {fmt(amount, 1)}</span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </Panel>

          <Panel title="Production & need" eyebrow="where the calories go">
            <div className="space-y-3 px-4 py-3">
              {settlements.map((settlement) => {
                const detail = details[settlement.id]
                const storage = detail ? Object.values(detail.storage).reduce((a, b) => a + b, 0) : 0
                return (
                  <div key={settlement.id}>
                    <div className="mb-1 flex justify-between text-[10.5px]">
                      <span className="text-fg">{settlement.name}</span>
                      <span className="num text-muted">{settlement.food_production ? `${fmt(settlement.food_production, 1)} / day` : 'no farms yet'}</span>
                    </div>
                    {detail && (
                      <>
                        <Meter value={storage} max={Math.max(1, detail.storage_capacity)} tone="var(--color-amber)" />
                        <div className="mt-0.5 flex justify-between font-mono text-[8.5px] text-dim">
                          <span>storage</span><span>{fmt(storage, 0)} / {fmt(detail.storage_capacity, 0)}</span>
                        </div>
                      </>
                    )}
                  </div>
                )
              })}
              <div className="flex items-center gap-2 border-t border-edge-soft pt-2 font-mono text-[9px] text-dim">
                <Droplets size={11} /> Food is deposited to settlement stores, then eaten by members who lack personal supplies.
              </div>
              <div className="flex items-center gap-2 font-mono text-[9px] text-dim">
                <TrendingUp size={11} /> Taxes only apply once a settlement adopts a formal government with a tax rate above zero.
              </div>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  )
}
