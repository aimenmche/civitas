import { useMemo, useState } from 'react'
import { Layers, MapPin, Crosshair, MousePointerClick } from 'lucide-react'
import clsx from 'clsx'
import { useStore } from '../store'
import { WorldMap, type MapOverlay } from '../components/WorldMap'
import { Badge, EmptyState, Panel } from '../components/ui'
import { fmt, titleCase } from '../lib/format'

const OVERLAYS: Array<{ id: MapOverlay; label: string; hint: string }> = [
  { id: 'terrain', label: 'Terrain', hint: 'Biomes as generated' },
  { id: 'fertility', label: 'Fertility', hint: 'Where crops and forage grow' },
  { id: 'water', label: 'Water', hint: 'Fresh water and coastlines' },
  { id: 'resources', label: 'Resources', hint: 'Wood, stone, game, fish' },
  { id: 'territory', label: 'Territory', hint: 'Settlement claims' },
]

const TERRAIN_SWATCH: Record<string, string> = {
  deep_ocean: '#0a1d2e', ocean: '#0f2940', coast: '#1a4059', lake: '#123a52', river: '#2a6b84',
  mountain: '#616776', tundra: '#93a1ac', desert: '#c4a56f', swamp: '#405446', forest: '#2f624a',
  fertile: '#537f4c', plains: '#647d4b',
}

export function WorldPage() {
  const state = useStore((s) => s.state)
  const world = useStore((s) => s.world)
  const selectAgent = useStore((s) => s.selectAgent)
  const selectSettlement = useStore((s) => s.selectSettlement)
  const selectedAgentId = useStore((s) => s.selectedAgentId)
  const selectedSettlementId = useStore((s) => s.selectedSettlementId)
  const [overlay, setOverlay] = useState<MapOverlay>('terrain')
  const [tile, setTile] = useState<{ x: number; y: number } | null>(null)

  const agents = state?.agents ?? []
  const settlements = state?.settlements ?? []
  const tileInfo = useMemo(() => {
    if (!world || !tile) return null
    const index = tile.y * world.width + tile.x
    const nearbyAgents = agents.filter((agent) => agent.alive && Math.abs(agent.x - tile.x) <= 2 && Math.abs(agent.y - tile.y) <= 2)
    const owner = world.tiles.owner[index]
    return {
      terrain: world.tiles.terrain[index],
      elevation: world.tiles.elevation[index],
      water: world.tiles.water[index],
      fertility: world.tiles.fertility[index],
      buildable: world.tiles.buildable[index],
      passable: world.tiles.passable[index],
      freshwater: world.tiles.freshwater[index],
      resources: world.tiles.resources[index] ?? {},
      owner: owner ? settlements.find((settlement) => settlement.id === owner) : null,
      nearbyAgents,
    }
  }, [world, tile, agents, settlements])

  if (!world || !state) {
    return <EmptyState icon={<MapPin size={22} />} title="No world loaded">Select or create a run to see its continent.</EmptyState>
  }

  return (
    <div className="flex h-full min-h-0 gap-4 px-5 py-4">
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-1 rounded-lg border border-edge bg-panel/80 p-1">
            {OVERLAYS.map((item) => (
              <button
                key={item.id}
                type="button"
                title={item.hint}
                onClick={() => setOverlay(item.id)}
                className={clsx(
                  'rounded px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-wider transition-colors',
                  overlay === item.id ? 'bg-amber/15 text-amber' : 'text-muted hover:bg-white/5 hover:text-fg',
                )}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge>{world.width} × {world.height} tiles</Badge>
            <Badge>land {fmt(world.land_ratio * 100, 0)}%</Badge>
            <Badge tone="teal">{world.rivers} rivers</Badge>
            <Badge tone="violet">seed {world.seed}</Badge>
          </div>
        </div>

        <div className="panel relative min-h-0 flex-1 overflow-hidden" style={{ backdropFilter: 'none' }}>
          <WorldMap
            world={world}
            agents={agents}
            settlements={settlements}
            overlay={overlay}
            selectedAgentId={selectedAgentId}
            selectedSettlementId={selectedSettlementId}
            onSelectAgent={(id) => void selectAgent(id)}
            onSelectSettlement={(id) => void selectSettlement(id)}
            onSelectTile={setTile}
          />
          <div className="pointer-events-none absolute bottom-3 left-3 flex items-center gap-2 rounded-md border border-edge bg-bg px-2.5 py-1.5 font-mono text-[9px] uppercase tracking-wider text-dim">
            <MousePointerClick size={11} /> click a tile or marker · drag to pan · scroll to zoom
          </div>
          <div className="pointer-events-none absolute bottom-3 right-3 rounded-md border border-edge bg-bg px-2.5 py-1.5 font-mono text-[9px] uppercase tracking-wider text-dim">
            {state.run.season} · day {state.run.day} · {state.run.weather}
          </div>
        </div>
      </div>

      <aside className="flex w-[290px] shrink-0 flex-col gap-3">
        <Panel title={tile ? `Tile ${tile.x}, ${tile.y}` : 'Tile inspector'} eyebrow="survey" action={<Crosshair size={13} className="text-dim" />}>
          {!tileInfo && (
            <div className="px-4 py-6 text-center text-[11.5px] leading-relaxed text-muted">
              Click the map to read a tile: terrain, fertility, fresh water, resources and who claims it.
            </div>
          )}
          {tileInfo && (
            <div className="space-y-2 px-4 py-3">
              <div className="flex items-center gap-2">
                <span className="h-4 w-4 rounded border border-black/40" style={{ background: TERRAIN_SWATCH[tileInfo.terrain] ?? '#334155' }} />
                <span className="text-[13px] font-medium text-fg">{titleCase(tileInfo.terrain)}</span>
                {tileInfo.freshwater && <Badge tone="teal">fresh water</Badge>}
              </div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 pt-1 font-mono text-[10px]">
                <span className="text-muted">elevation <span className="text-fg">{fmt(tileInfo.elevation, 2)}</span></span>
                <span className="text-muted">water <span className="text-fg">{fmt(tileInfo.water, 2)}</span></span>
                <span className="text-muted">fertility <span className="text-fg">{fmt(tileInfo.fertility, 2)}</span></span>
                <span className="text-muted">buildable <span className="text-fg">{tileInfo.buildable ? 'yes' : 'no'}</span></span>
              </div>
              {Object.keys(tileInfo.resources).length > 0 && (
                <div className="flex flex-wrap gap-1 pt-1">
                  {Object.entries(tileInfo.resources).map(([item, amount]) => (
                    <Badge key={item} tone="amber">{item} {fmt(amount, 1)}</Badge>
                  ))}
                </div>
              )}
              {tileInfo.owner && (
                <button type="button" className="flex w-full items-center gap-1 rounded border border-edge-soft px-2.5 py-1.5 text-left text-[11px] text-teal hover:bg-white/5" onClick={() => void selectSettlement(tileInfo.owner!.id)}>
                  <Layers size={11} /> claimed by {tileInfo.owner.name}
                </button>
              )}
              <div className="pt-1">
                <div className="mb-1 font-mono text-[9px] uppercase tracking-wider text-dim">within two tiles · {tileInfo.nearbyAgents.length}</div>
                <div className="space-y-1">
                  {tileInfo.nearbyAgents.slice(0, 6).map((agent) => (
                    <button key={agent.id} type="button" className="flex w-full justify-between gap-2 rounded border border-edge-soft px-2 py-1 text-left hover:bg-white/5" onClick={() => void selectAgent(agent.id)}>
                      <span className="truncate text-[11px] text-fg">{agent.name}</span>
                      <span className="font-mono text-[9px] text-dim">{agent.occupation}</span>
                    </button>
                  ))}
                  {!tileInfo.nearbyAgents.length && <div className="text-[10.5px] text-muted">Nobody nearby.</div>}
                </div>
              </div>
            </div>
          )}
        </Panel>

        <Panel title="Legend" eyebrow={overlay} className="flex-1" bodyClassName="scroll-area">
          {overlay === 'terrain' ? (
            <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 px-4 py-3">
              {Object.entries(TERRAIN_SWATCH).map(([name, color]) => (
                <div key={name} className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-sm" style={{ background: color }} />
                  <span className="text-[10.5px] text-muted">{titleCase(name)}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-2 px-4 py-3 text-[11px] leading-relaxed text-muted">
              {overlay === 'fertility' && <p>Brighter green marks tiles where forage and crops are productive. Darker ground is infertile or unbuildable.</p>}
              {overlay === 'water' && <p>Blue intensity shows water availability. Pale blue tiles are fresh water; deep blue is salt water.</p>}
              {overlay === 'resources' && <p>Coloured dots mark resource deposits. Hover the map tile inspector for exact amounts.</p>}
              {overlay === 'territory' && <p>Tiles are tinted by the settlement that claims them. Territory follows population and buildings.</p>}
              <div className="flex flex-wrap gap-1.5 pt-1">
                <Badge tone="teal">agent marker</Badge>
                <Badge tone="amber">◆ settlement</Badge>
              </div>
            </div>
          )}
        </Panel>
      </aside>
    </div>
  )
}
