import { useMemo, useState } from 'react'
import { Sparkles, FlaskConical, Check, Lock, Loader2, ArrowRight } from 'lucide-react'
import clsx from 'clsx'
import { useStore } from '../store'
import { Badge, EmptyState, Meter, Panel, StatCard } from '../components/ui'
import { fmt, titleCase } from '../lib/format'
import type { TechNode } from '../types'

const ERA_TONE: Record<string, string> = {
  Survival: 'text-[#9aa7b4]',
  Neolithic: 'text-good',
  Bronze: 'text-amber',
  Classical: 'text-teal',
  Medieval: 'text-violet',
}

export function TechnologyPage() {
  const state = useStore((s) => s.state)
  const technology = useStore((s) => s.technology)
  const selectAgent = useStore((s) => s.selectAgent)
  const [filter, setFilter] = useState<'all' | 'discovered' | 'available' | 'locked'>('all')

  const tree = technology?.tree ?? []
  const known = useMemo(() => new Set(technology?.known ?? state?.run.techs ?? []), [technology, state])
  const eras = useMemo(() => {
    const map = new Map<string, TechNode[]>()
    for (const node of tree) {
      const list = map.get(node.era) ?? []
      list.push(node)
      map.set(node.era, list)
    }
    return Array.from(map.entries())
  }, [tree])
  const filteredEras = useMemo(
    () => eras.map(([era, nodes]) => [era, nodes.filter((node) => filter === 'all' || node.status === filter)] as const)
      .filter(([, nodes]) => nodes.length > 0),
    [eras, filter],
  )

  if (!state) return <EmptyState icon={<Sparkles size={22} />} title="No run loaded" />
  const discoveries = technology?.discoveries ?? state.technology?.discoveries ?? {}
  const researching = technology?.researching ?? []
  const available = tree.filter((node) => node.status === 'available').length
  const discovered = known.size

  return (
    <div className="scroll-area h-full">
      <div className="mx-auto max-w-[1500px] space-y-4 px-5 py-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard label="era" value={state.run.era} hint={`${discovered} technologies known`} icon={<Sparkles size={14} />} tone="amber" />
          <StatCard label="discovered" value={fmt(discovered)} hint={`${available} available to research`} icon={<Check size={14} />} tone="good" />
          <StatCard label="researching" value={fmt(researching.length)} hint="named people at work" icon={<FlaskConical size={14} />} tone="teal" />
          <StatCard label="locked" value={fmt(tree.filter((node) => node.status === 'locked').length)} hint="prerequisites unmet" icon={<Lock size={14} />} tone="violet" />
        </div>

        {researching.length > 0 && (
          <Panel title="Research in progress" eyebrow="who is working on what">
            <div className="grid grid-cols-1 gap-2 px-4 py-3 sm:grid-cols-2 lg:grid-cols-3">
              {researching.map((item) => {
                const node = tree.find((candidate) => candidate.key === item.tech)
                return (
                  <button key={item.agent_id} type="button" onClick={() => void selectAgent(item.agent_id)} className="rounded border border-edge-soft bg-bg2/40 px-3 py-2 text-left hover:border-dim">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-[11.5px] text-fg">{item.name}</span>
                      <span className="num text-[10px] text-violet">{fmt(item.progress, 0)} / {node?.cost ?? '?'}</span>
                    </div>
                    <div className="mt-0.5 text-[10.5px] text-muted">{node?.name ?? titleCase(item.tech ?? 'research')}</div>
                    <Meter className="mt-1.5" value={item.progress} max={node?.cost ?? 100} tone="var(--color-violet)" />
                  </button>
                )
              })}
            </div>
          </Panel>
        )}

        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-1 rounded-lg border border-edge bg-panel/80 p-1">
            {(['all', 'discovered', 'available', 'locked'] as const).map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setFilter(item)}
                className={clsx('rounded px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-wider transition-colors', filter === item ? 'bg-teal/15 text-teal' : 'text-muted hover:bg-white/5 hover:text-fg')}
              >
                {item}
              </button>
            ))}
          </div>
          <span className="font-mono text-[10px] text-dim">knowledge is discovered by agents, not granted by the interface</span>
        </div>

        <div className="space-y-4">
          {filteredEras.map(([era, nodes]) => (
            <Panel key={era} title={era} eyebrow={`${nodes.length} technologies`}>
              <div className="grid grid-cols-1 gap-2 px-4 py-3 md:grid-cols-2 xl:grid-cols-3">
                {nodes.map((node) => {
                  const discovery = discoveries[node.key]
                  return (
                    <div
                      key={node.key}
                      className={clsx(
                        'rounded-lg border px-3 py-2.5 transition-colors',
                        node.status === 'discovered' ? 'border-good/25 bg-good/[0.04]' : node.status === 'available' ? 'border-edge bg-panel2/40' : 'border-edge-soft bg-bg2/30 opacity-70',
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className={clsx('text-[12.5px] font-medium', ERA_TONE[era] ?? 'text-fg')}>{node.name}</div>
                          <div className="font-mono text-[8.5px] uppercase tracking-wider text-dim">cost {node.cost} · {node.status}</div>
                        </div>
                        {node.status === 'discovered' ? <Check size={13} className="mt-0.5 shrink-0 text-good" /> : node.status === 'locked' ? <Lock size={12} className="mt-0.5 shrink-0 text-dim" /> : <Sparkles size={12} className="mt-0.5 shrink-0 text-amber" />}
                      </div>
                      <p className="mt-1 text-[10.5px] leading-relaxed text-muted">{node.effect}</p>
                      {node.prereq.length > 0 && (
                        <div className="mt-1.5 flex flex-wrap items-center gap-1">
                          <span className="font-mono text-[8.5px] uppercase tracking-wider text-dim">needs</span>
                          {node.prereq.map((prereq) => (
                            <span key={prereq} className={clsx('rounded border px-1 py-0.5 font-mono text-[8.5px]', known.has(prereq) ? 'border-good/30 text-good' : 'border-edge text-dim')}>{titleCase(prereq)}</span>
                          ))}
                        </div>
                      )}
                      {node.status !== 'discovered' && node.progress > 0 && (
                        <div className="mt-2">
                          <Meter value={node.progress} max={node.cost} tone="var(--color-violet)" />
                          <div className="mt-0.5 text-right font-mono text-[8.5px] text-dim">{fmt(node.progress, 1)} / {node.cost}</div>
                        </div>
                      )}
                      {discovery && (
                        <div className="mt-1.5 font-mono text-[8.5px] text-dim">
                          day {discovery.day} · {discovery.initial ? 'initial knowledge' : `by ${discovery.agent_name}`}{discovery.settlement_name ? ` · ${discovery.settlement_name}` : ''}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </Panel>
          ))}
          {!filteredEras.length && (
            <Panel title="Nothing matches" eyebrow="technology tree">
              <div className="px-4 py-10 text-center text-[11.5px] text-muted">No technologies match this filter.</div>
            </Panel>
          )}
        </div>

        <Panel title="Discovery log" eyebrow="in order">
          <div className="scroll-area max-h-[260px]">
            {Object.entries(discoveries).sort((a, b) => a[1].day - b[1].day).map(([key, discovery]) => (
              <div key={key} className="flex items-center justify-between gap-3 border-b border-edge-soft/60 px-4 py-2 last:border-0">
                <div className="flex items-center gap-2">
                  <span className="num w-10 text-[10px] text-dim">D{discovery.day}</span>
                  <span className="text-[11.5px] text-fg">{titleCase(key)}</span>
                </div>
                <div className="text-right font-mono text-[9px] text-dim">
                  {discovery.initial ? 'starting knowledge' : discovery.agent_name}
                  {discovery.settlement_name ? ` · ${discovery.settlement_name}` : ''}
                </div>
              </div>
            ))}
            {!Object.keys(discoveries).length && (
              <div className="px-4 py-8 text-[11.5px] text-muted">No discoveries recorded yet. Research begins when people have their survival needs met.</div>
            )}
          </div>
        </Panel>

        <div className="flex items-center gap-2 pb-2 font-mono text-[9px] text-dim">
          <ArrowRight size={11} /> Technology affects gathering yields, building speed, farming, trade, governance and health. It is not decorative.
        </div>
      </div>
    </div>
  )
}
