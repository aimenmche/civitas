export function fmt(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return value.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

export function compact(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  if (Math.abs(value) >= 1000) {
    return `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}k`
  }
  return fmt(value, Math.abs(value) < 10 && value % 1 !== 0 ? 1 : 0)
}

export function pct(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined) return '—'
  return `${value.toFixed(digits)}%`
}

export function needTone(value: number): string {
  if (value < 25) return 'var(--color-danger)'
  if (value < 50) return 'var(--color-amber)'
  if (value < 75) return 'var(--color-teal)'
  return 'var(--color-good)'
}

export function happinessTone(value: number): string {
  if (value < 35) return 'text-danger'
  if (value < 55) return 'text-amber'
  if (value < 75) return 'text-fg'
  return 'text-good'
}

export const PRESETS: Array<{
  id: string
  name: string
  tagline: string
  description: string
}> = [
  {
    id: 'fertile_valley',
    name: 'Fertile Valley',
    tagline: 'Rivers, grain and room to grow',
    description: 'A forgiving temperate world. Good for watching first settlements become towns.',
  },
  {
    id: 'island_civilization',
    name: 'Island Civilization',
    tagline: 'Scattered land, salt water',
    description: 'A fragmented archipelago. Travel and trade matter more than territory.',
  },
  {
    id: 'desert_world',
    name: 'Desert World',
    tagline: 'Water is the whole politics',
    description: 'Scarce water and thin forage. Oases become strategic ground.',
  },
  {
    id: 'frozen_continent',
    name: 'Frozen Continent',
    tagline: 'Survive the winter',
    description: 'Cold, short growing seasons and dangerous exposure. Shelters decide who lives.',
  },
  {
    id: 'random_world',
    name: 'Random World',
    tagline: 'Let the seed decide',
    description: 'A fresh continent generated from the seed. No preset expectations.',
  },
]

export function presetName(id: string): string {
  return PRESETS.find((preset) => preset.id === id)?.name ?? id.replace(/_/g, ' ')
}

export function relativeDay(day: number, currentDay: number): string {
  const delta = currentDay - day
  if (delta <= 0) return 'today'
  if (delta === 1) return 'yesterday'
  if (delta < 10) return `${delta} days ago`
  return `day ${day}`
}

export function titleCase(input: string): string {
  return input.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())
}

export function eventCategoryTone(category: string): string {
  switch (category) {
    case 'milestone':
      return 'text-amber border-amber/30 bg-amber/10'
    case 'settlement':
      return 'text-teal border-teal/30 bg-teal/10'
    case 'technology':
      return 'text-violet border-violet/30 bg-violet/10'
    case 'conflict':
    case 'death':
    case 'demography':
    case 'disaster':
      return 'text-danger border-danger/30 bg-danger/10'
    case 'culture':
      return 'text-[#dba9ff] border-[#dba9ff]/30 bg-[#dba9ff]/10'
    case 'social':
      return 'text-[#7fcfe0] border-[#7fcfe0]/30 bg-[#7fcfe0]/10'
    case 'world':
      return 'text-dim border-edge bg-panel2/70'
    case 'survival':
      return 'text-[#e0a86b] border-[#e0a86b]/30 bg-[#e0a86b]/10'
    case 'economy':
      return 'text-[#8fbf7a] border-[#8fbf7a]/30 bg-[#8fbf7a]/10'
    case 'politics':
      return 'text-[#f0d45a] border-[#f0d45a]/30 bg-[#f0d45a]/10'
    default:
      return 'text-muted border-edge bg-panel2/70'
  }
}
