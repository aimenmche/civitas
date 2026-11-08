import { useMemo, useState } from 'react'
import { FlaskConical, Loader2, X } from 'lucide-react'
import clsx from 'clsx'
import { useStore } from '../store'
import { PRESETS } from '../lib/format'
import type { WorldConfig } from '../types'

const CLIMATES = ['temperate', 'warm', 'cold', 'arid']
const PERSONALITIES = ['balanced', 'cooperative', 'competitive', 'ambitious']
const TECHNOLOGIES = ['none', 'fire', 'basic_tools', 'early_agriculture']

export function CreateRunModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const createRun = useStore((state) => state.createRun)
  const setPage = useStore((state) => state.setPage)
  const [preset, setPreset] = useState('fertile_valley')
  const [name, setName] = useState('Aureth')
  const [seed, setSeed] = useState('')
  const [population, setPopulation] = useState(30)
  const [groups, setGroups] = useState(3)
  const [climate, setClimate] = useState('temperate')
  const [difficulty, setDifficulty] = useState(1)
  const [abundance, setAbundance] = useState(1)
  const [technology, setTechnology] = useState('none')
  const [personality, setPersonality] = useState('balanced')
  const [noCurrency, setNoCurrency] = useState(false)
  const [noLeader, setNoLeader] = useState(false)
  const [asymmetric, setAsymmetric] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const presetMeta = useMemo(() => PRESETS.find((item) => item.id === preset), [preset])

  if (!open) return null

  const submit = async () => {
    setBusy(true)
    setError(null)
    const config: Partial<WorldConfig> = {
      world_name: name.trim() || 'Aureth',
      preset,
      seed: seed.trim() === '' ? null : Math.max(0, Math.min(2147483647, Number.parseInt(seed, 10) || 0)),
      initial_population: population,
      starting_groups: groups,
      climate: climate as WorldConfig['climate'],
      environmental_difficulty: difficulty,
      resource_abundance: abundance,
      starting_technology: technology as WorldConfig['starting_technology'],
      personality_distribution: personality as WorldConfig['personality_distribution'],
      no_currency: noCurrency,
      no_leader: noLeader,
      asymmetric_groups: asymmetric,
    }
    try {
      await createRun(config, `Created from the observatory (${presetMeta?.name ?? preset})`)
      setPage('world')
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create the world')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4" onMouseDown={onClose}>
      <div
        className="panel flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden fade-in"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-edge px-5 py-4">
          <div>
            <div className="eyebrow mb-1 flex items-center gap-1.5"><FlaskConical size={12} /> genesis chamber</div>
            <h2 className="text-lg font-semibold text-fg">Create a new world</h2>
            <p className="mt-0.5 text-xs text-muted">Seed a continent, place thirty lives on it, and see what they make of each other.</p>
          </div>
          <button type="button" className="btn-ghost p-2" onClick={onClose}><X size={16} /></button>
        </header>

        <div className="scroll-area flex-1 px-5 py-4">
          <div className="mb-5">
            <div className="label">world template</div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {PRESETS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setPreset(item.id)}
                  className={clsx(
                    'rounded-lg border px-3 py-2.5 text-left transition-colors',
                    preset === item.id ? 'border-amber/50 bg-amber/10' : 'border-edge bg-panel2/50 hover:border-dim',
                  )}
                >
                  <div className={clsx('text-[12.5px] font-semibold', preset === item.id ? 'text-amber' : 'text-fg')}>{item.name}</div>
                  <div className="mt-0.5 font-mono text-[9px] uppercase tracking-wider text-dim">{item.tagline}</div>
                  <div className="mt-1 text-[10.5px] leading-relaxed text-muted">{item.description}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <label className="label" htmlFor="world-name">world name</label>
              <input id="world-name" className="input" value={name} onChange={(event) => setName(event.target.value)} maxLength={64} />
            </div>
            <div>
              <label className="label" htmlFor="world-seed">seed (blank = random)</label>
              <input id="world-seed" className="input" value={seed} onChange={(event) => setSeed(event.target.value.replace(/[^0-9]/g, ''))} placeholder="e.g. 12345" />
            </div>
            <div>
              <label className="label" htmlFor="world-climate">climate</label>
              <select id="world-climate" className="input" value={climate} onChange={(event) => setClimate(event.target.value)}>
                {CLIMATES.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="world-tech">starting knowledge</label>
              <select id="world-tech" className="input" value={technology} onChange={(event) => setTechnology(event.target.value)}>
                {TECHNOLOGIES.map((item) => <option key={item} value={item}>{item.replace(/_/g, ' ')}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="world-pop">initial population · {population}</label>
              <input id="world-pop" type="range" min={8} max={80} step={1} value={population} className="w-full accent-[var(--color-amber)]" onChange={(event) => setPopulation(Number(event.target.value))} />
            </div>
            <div>
              <label className="label" htmlFor="world-groups">starting groups · {groups}</label>
              <input id="world-groups" type="range" min={1} max={6} step={1} value={groups} className="w-full accent-[var(--color-teal)]" onChange={(event) => setGroups(Number(event.target.value))} />
            </div>
            <div>
              <label className="label" htmlFor="world-difficulty">environmental difficulty · {difficulty.toFixed(1)}</label>
              <input id="world-difficulty" type="range" min={0.5} max={1.8} step={0.1} value={difficulty} className="w-full accent-[var(--color-danger)]" onChange={(event) => setDifficulty(Number(event.target.value))} />
            </div>
            <div>
              <label className="label" htmlFor="world-abundance">resource abundance · {abundance.toFixed(1)}</label>
              <input id="world-abundance" type="range" min={0.4} max={1.8} step={0.1} value={abundance} className="w-full accent-[var(--color-good)]" onChange={(event) => setAbundance(Number(event.target.value))} />
            </div>
            <div>
              <label className="label" htmlFor="world-personality">personality mix</label>
              <select id="world-personality" className="input" value={personality} onChange={(event) => setPersonality(event.target.value)}>
                {PERSONALITIES.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </div>
            <div className="sm:col-span-2 lg:col-span-3">
              <div className="label">social constraints</div>
              <div className="flex flex-wrap gap-2">
                <Toggle label="No currency" value={noCurrency} onChange={setNoCurrency} hint="All exchange is barter." />
                <Toggle label="No central leader" value={noLeader} onChange={setNoLeader} hint="Settlements run by assembly." />
                <Toggle label="Asymmetric groups" value={asymmetric} onChange={setAsymmetric} hint="Unequal starting resources and skills." />
              </div>
            </div>
          </div>

          {error && <div className="mt-4 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger">{error}</div>}
        </div>

        <footer className="flex items-center justify-between gap-3 border-t border-edge px-5 py-3.5">
          <div className="font-mono text-[10px] text-dim">
            deterministic · same seed + same rules = same history
          </div>
          <div className="flex gap-2">
            <button type="button" className="btn" onClick={onClose}>Cancel</button>
            <button type="button" className="btn-primary" disabled={busy} onClick={() => void submit()}>
              {busy ? <Loader2 size={13} className="animate-spin" /> : <FlaskConical size={13} />}
              {busy ? 'Generating…' : 'Begin simulation'}
            </button>
          </div>
        </footer>
      </div>
    </div>
  )
}

function Toggle({ label, value, onChange, hint }: { label: string; value: boolean; onChange: (value: boolean) => void; hint: string }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!value)}
      className={clsx(
        'flex items-center gap-2 rounded-lg border px-3 py-2 text-left transition-colors',
        value ? 'border-teal/40 bg-teal/10' : 'border-edge bg-panel2/50 hover:border-dim',
      )}
      title={hint}
    >
      <span className={clsx('flex h-3.5 w-6 items-center rounded-full p-0.5 transition-colors', value ? 'bg-teal/60' : 'bg-edge')}>
        <span className={clsx('h-2.5 w-2.5 rounded-full bg-white transition-transform', value && 'translate-x-2.5')} />
      </span>
      <span className="text-[11px] text-fg">{label}</span>
    </button>
  )
}
