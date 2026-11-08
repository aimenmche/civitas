import { useMemo, useState } from 'react'
import { Globe2, Palette, Languages, Users, Music, BookOpen, Sparkles } from 'lucide-react'
import clsx from 'clsx'
import { useStore } from '../store'
import { Badge, EmptyState, Meter, Panel, StatCard } from '../components/ui'
import { fmt, titleCase } from '../lib/format'
import type { Culture, Language } from '../types'

export function CulturePage() {
  const state = useStore((s) => s.state)
  const [tab, setTab] = useState<'cultures' | 'languages' | 'families'>('cultures')
  const [activeCulture, setActiveCulture] = useState<string | null>(null)

  const cultures = state?.cultures ?? []
  const languages = state?.languages ?? []
  const families = state?.families ?? []
  const selectedCulture = useMemo(
    () => cultures.find((culture) => culture.id === activeCulture) ?? cultures[0],
    [cultures, activeCulture],
  )

  if (!state) return <EmptyState icon={<Globe2 size={22} />} title="No run loaded" />
  const traditionCount = cultures.reduce((sum, culture) => sum + (culture.traditions?.length ?? 0), 0)
  const artCount = cultures.reduce((sum, culture) => sum + (Array.isArray(culture.art_forms) ? culture.art_forms.length : 0), 0)
  const values = selectedCulture?.values ?? {}

  return (
    <div className="scroll-area h-full">
      <div className="mx-auto max-w-[1500px] space-y-4 px-5 py-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard label="cultures" value={fmt(cultures.length)} hint={`${traditionCount} living traditions`} icon={<Globe2 size={14} />} tone="violet" />
          <StatCard label="languages" value={fmt(languages.length)} hint="with real lexicons and loans" icon={<Languages size={14} />} tone="teal" />
          <StatCard label="families" value={fmt(families.length)} hint="kinship houses" icon={<Users size={14} />} tone="amber" />
          <StatCard label="artworks" value={fmt(artCount)} hint="songs, carvings, weavings" icon={<Music size={14} />} tone="good" />
        </div>

        <div className="flex items-center gap-1 rounded-lg border border-edge bg-panel/80 p-1 w-fit">
          {(['cultures', 'languages', 'families'] as const).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setTab(item)}
              className={clsx('rounded px-3 py-1.5 font-mono text-[10px] uppercase tracking-wider transition-colors', tab === item ? 'bg-violet/15 text-violet' : 'text-muted hover:bg-white/5 hover:text-fg')}
            >
              {item}
            </button>
          ))}
        </div>

        {tab === 'cultures' && (
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            <Panel title="Traditions" eyebrow="cultural record" bodyClassName="scroll-area max-h-[520px]">
              {!cultures.length && <div className="px-4 py-8 text-[11.5px] text-muted">No distinct culture has formed yet. Shared practices appear once a settlement endures.</div>}
              {cultures.map((culture) => (
                <button
                  key={culture.id}
                  type="button"
                  onClick={() => setActiveCulture(culture.id)}
                  className={clsx('w-full border-b border-edge-soft/60 px-4 py-3 text-left last:border-0 hover:bg-white/[0.025]', selectedCulture?.id === culture.id && 'bg-violet/[0.06]')}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[12.5px] font-medium text-fg">{culture.name}</span>
                    <Badge tone="violet">{culture.traditions?.length ?? 0} traditions</Badge>
                  </div>
                  <div className="mt-0.5 truncate font-mono text-[9px] text-dim">
                    {culture.settlement_id ? state.settlements.find((item) => item.id === culture.settlement_id)?.name ?? culture.settlement_id : 'wandering tradition'}
                  </div>
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {(culture.symbols ?? []).slice(0, 3).map((symbol) => <span key={symbol} className="font-mono text-[9px] text-muted">{symbol}</span>)}
                  </div>
                </button>
              ))}
            </Panel>

            <div className="xl:col-span-2">
              {!selectedCulture && <Panel title="No culture selected" eyebrow="dossier"><div className="px-4 py-10 text-center text-[11.5px] text-muted">Nothing to show yet.</div></Panel>}
              {selectedCulture && (
                <div className="space-y-4">
                  <Panel
                    title={selectedCulture.name}
                    eyebrow="culture dossier"
                    action={<Badge tone="violet">{selectedCulture.traditions?.length ?? 0} traditions</Badge>}
                  >
                    <div className="grid grid-cols-2 gap-x-5 gap-y-3 px-4 py-4 sm:grid-cols-3">
                      {Object.entries(values).map(([value, amount]) => (
                        <div key={value}>
                          <div className="mb-1 flex justify-between font-mono text-[9px] text-dim"><span className="capitalize">{value}</span><span>{fmt(amount * 100)}</span></div>
                          <Meter value={amount * 100} tone={value === 'innovation' ? 'var(--color-teal)' : value === 'martial' ? 'var(--color-danger)' : 'var(--color-violet)'} />
                        </div>
                      ))}
                    </div>
                    {(selectedCulture.symbols ?? []).length > 0 && (
                      <div className="flex flex-wrap gap-1.5 border-t border-edge-soft px-4 py-2.5">
                        <span className="font-mono text-[9px] uppercase tracking-wider text-dim">symbols</span>
                        {(selectedCulture.symbols ?? []).map((symbol) => <Badge key={symbol} tone="muted">{symbol}</Badge>)}
                      </div>
                    )}
                  </Panel>

                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <Panel title="Traditions" eyebrow="what is remembered together">
                      {!(selectedCulture.traditions ?? []).length && <div className="px-4 py-6 text-[11.5px] text-muted">No traditions yet.</div>}
                      {(selectedCulture.traditions ?? []).map((tradition) => (
                        <div key={`${tradition.name}-${tradition.since_day}`} className="border-b border-edge-soft/60 px-4 py-2.5 last:border-0">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-[11.5px] font-medium text-fg">{tradition.name}</span>
                            <Badge tone="muted">{tradition.category ?? 'custom'}</Badge>
                          </div>
                          <div className="mt-0.5 text-[10.5px] leading-relaxed text-muted">{tradition.description}</div>
                          <div className="mt-1 font-mono text-[8.5px] text-dim">since day {tradition.since_day} · {tradition.origin}</div>
                        </div>
                      ))}
                    </Panel>

                    <Panel title="Art & craft" eyebrow="made by named people">
                      {!(selectedCulture.art_forms ?? []).length && <div className="px-4 py-6 text-[11.5px] text-muted">No artworks recorded yet.</div>}
                      {(selectedCulture.art_forms ?? []).map((item, index) => (
                        <div key={index} className="border-b border-edge-soft/60 px-4 py-2.5 last:border-0">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-[11.5px] text-fg">{item.name ?? 'Untitled work'}</span>
                            <span className="font-mono text-[9px] text-dim">day {item.day ?? '—'}</span>
                          </div>
                          <div className="mt-0.5 font-mono text-[9px] text-muted">{item.form}{item.by ? ` · ${item.by}` : ''}</div>
                        </div>
                      ))}
                    </Panel>
                  </div>

                  {((selectedCulture.taboos ?? []).length > 0 || (selectedCulture.cuisine ?? []).length > 0) && (
                    <Panel title="Customs" eyebrow="taboos and tastes">
                      <div className="space-y-2 px-4 py-3">
                        {(selectedCulture.taboos ?? []).length > 0 && (
                          <div className="flex flex-wrap gap-1.5"><span className="font-mono text-[9px] uppercase tracking-wider text-dim">taboos</span>{selectedCulture.taboos!.map((item) => <Badge key={String(item)} tone="danger">{String(item)}</Badge>)}</div>
                        )}
                        {(selectedCulture.cuisine ?? []).length > 0 && (
                          <div className="flex flex-wrap gap-1.5"><span className="font-mono text-[9px] uppercase tracking-wider text-dim">cuisine</span>{selectedCulture.cuisine!.map((item) => <Badge key={String(item)} tone="good">{String(item)}</Badge>)}</div>
                        )}
                      </div>
                    </Panel>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {tab === 'languages' && (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {languages.map((language) => <LanguageCard key={language.id} language={language} />)}
            {!languages.length && (
              <Panel title="No languages yet" eyebrow="speech"><div className="px-4 py-8 text-[11.5px] text-muted">Language emerges as people live and speak together.</div></Panel>
            )}
          </div>
        )}

        {tab === 'families' && (
          <Panel title="Houses and kin" eyebrow="family formation">
            <div className="grid grid-cols-1 gap-0 md:grid-cols-2 xl:grid-cols-3">
              {families.map((family) => {
                const memberIds = (family.member_ids as string[]) ?? []
                const members = memberIds.map((id) => state.agents.find((agent) => agent.id === id)).filter(Boolean)
                return (
                  <div key={String(family.id)} className="border-b border-edge-soft/60 px-4 py-3 md:border-r">
                    <div className="flex items-center justify-between">
                      <span className="text-[12.5px] font-medium text-fg">{String(family.name ?? family.id)}</span>
                      <Badge tone="amber">{members.length} members</Badge>
                    </div>
                    <div className="mt-0.5 font-mono text-[9px] text-dim">
                      formed day {String(family.created_day ?? '—')} · {state.settlements.find((settlement) => settlement.id === family.home_settlement_id)?.name ?? 'no home'}
                    </div>
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {members.map((member) => member && (
                        <span key={member.id} className={clsx('rounded border border-edge-soft px-1.5 py-0.5 text-[10px]', member.alive ? 'text-fg' : 'text-dim line-through')}>{member.name}</span>
                      ))}
                    </div>
                  </div>
                )
              })}
              {!families.length && <div className="px-4 py-8 text-[11.5px] text-muted">No families have formed yet. Partnerships create houses over time.</div>}
            </div>
          </Panel>
        )}

        <Panel title="The cultural record" eyebrow="recent cultural events">
          <div className="scroll-area max-h-[260px]">
            {[...state.events].filter((event) => ['culture', 'milestone', 'politics'].includes(event.category)).reverse().slice(0, 20).map((event) => (
              <div key={event.id} className="flex gap-3 border-b border-edge-soft/60 px-4 py-2 last:border-0">
                <span className="num w-10 shrink-0 text-[10px] text-dim">D{event.day}</span>
                <div className="min-w-0">
                  <div className="text-[11.5px] text-fg">{event.title}</div>
                  <div className="line-clamp-1 text-[10.5px] text-muted">{event.description}</div>
                </div>
              </div>
            ))}
            {!state.events.some((event) => ['culture', 'milestone', 'politics'].includes(event.category)) && (
              <div className="px-4 py-8 text-[11.5px] text-muted">No cultural milestones recorded yet.</div>
            )}
          </div>
        </Panel>
      </div>
    </div>
  )
}

function LanguageCard({ language }: { language: Language }) {
  const entries = Object.entries(language.lexicon ?? {})
  return (
    <Panel
      title={language.name}
      eyebrow={`${entries.length} recorded words`}
      action={<Badge tone="teal"><Languages size={10} /> {language.origins?.[0] ?? 'origin unknown'}</Badge>}
      bodyClassName="px-4 py-3"
    >
      <div className="flex flex-wrap gap-1.5">
        {entries.slice(0, 18).map(([concept, word]) => (
          <span key={concept} className="rounded border border-edge-soft bg-bg2/50 px-1.5 py-0.5 font-mono text-[10px] text-muted">
            {concept} <span className="text-teal">{String(word)}</span>
          </span>
        ))}
      </div>
      {entries.length === 0 && <div className="text-[11px] text-muted">No vocabulary recorded.</div>}
      {(language.loans?.length ?? 0) > 0 && (
        <div className="mt-3 border-t border-edge-soft pt-2">
          <div className="mb-1 flex items-center gap-1 font-mono text-[9px] uppercase tracking-wider text-dim"><BookOpen size={10} /> borrowed words</div>
          {(language.loans as Array<Record<string, unknown>>).slice(0, 3).map((loan, index) => (
            <div key={index} className="font-mono text-[9.5px] text-muted">
              {String(loan.concept)} · <span className="text-teal">{String(loan.word)}</span> from {String(loan.from)} (day {String(loan.day)})
            </div>
          ))}
        </div>
      )}
      {(language.speakers ?? 0) > 0 && (
        <div className="mt-2 flex items-center gap-1 font-mono text-[9px] text-dim"><Users size={10} /> {language.speakers} speakers</div>
      )}
    </Panel>
  )
}
