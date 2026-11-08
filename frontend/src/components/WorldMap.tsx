import { useEffect, useMemo, useRef, useState } from 'react'
import type { AgentSummary, SettlementSummary, WorldData } from '../types'

export type MapOverlay = 'terrain' | 'fertility' | 'water' | 'resources' | 'territory'

const TERRAIN_COLORS: Record<string, string> = {
  deep_ocean: '#0a1d2e',
  ocean: '#0f2940',
  coast: '#1a4059',
  lake: '#123a52',
  river: '#2a6b84',
  mountain: '#616776',
  tundra: '#93a1ac',
  desert: '#c4a56f',
  swamp: '#405446',
  forest: '#2f624a',
  fertile: '#537f4c',
  plains: '#647d4b',
}

const SETTLEMENT_COLORS = ['#f0b35a', '#58d6c5', '#9d8cf5', '#e98cbb', '#9bd66a', '#f28f66']

const RESOURCE_COLORS: Record<string, string> = {
  wood: '#9a7548', stone: '#9aa7b4', berries: '#d46a8e', game: '#c98a55',
  fish: '#6fc7d8', herbs: '#86c97c', ore: '#d9b05a', clay: '#ba8b6a',
}

const WATER = new Set(['deep_ocean', 'ocean', 'coast', 'lake', 'river'])

// Five quantised brightness steps applied per tile from a deterministic hash.
const TILE_SHADES = [-0.09, -0.045, 0, 0.045, 0.09]

// A hard ceiling on the offscreen surface. 4608x3072 is enough to cover a 4K
// panel at 1x and a 1440p panel at 2x without a multi-hundred-megabyte buffer.
const MAX_TILE_PX = 64

function hexToRgb(hex: string): [number, number, number] {
  const value = Number.parseInt(hex.slice(1), 16)
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255]
}

function rgbToHex(r: number, g: number, b: number): string {
  const clamp = (v: number) => Math.max(0, Math.min(255, Math.round(v)))
  return `#${((clamp(r) << 16) | (clamp(g) << 8) | clamp(b)).toString(16).padStart(6, '0')}`
}

function tileColor(tile: {
  terrain: string; fertility: number; water: number; buildable: boolean
}, overlay: MapOverlay): string {
  if (overlay === 'fertility') {
    if (!tile.buildable) return '#101c2b'
    const v = Math.min(1, tile.fertility)
    return rgbToHex(26 + v * 20, 40 + v * 120, 45 + v * 40)
  }
  if (overlay === 'water') {
    const v = Math.min(1, tile.water)
    return rgbToHex(12 + v * 18, 34 + v * 80, 52 + v * 150)
  }
  return TERRAIN_COLORS[tile.terrain] ?? '#334155'
}

function territoryColor(base: string, tint: string): string {
  const [br, bg, bb] = hexToRgb(base)
  const [tr, tg, tb] = hexToRgb(tint)
  return rgbToHex((br + tr) / 2, (bg + tg) / 2, (bb + tb) / 2)
}

function tileShade(seed: number, x: number, y: number): number {
  let h = Math.imul(x + 1, 374761393) ^ Math.imul(y + 1, 668265263) ^ Math.imul(seed + 1, 2246822519)
  h = Math.imul(h ^ (h >>> 13), 1274126177)
  h ^= h >>> 16
  return TILE_SHADES[Math.abs(h) % TILE_SHADES.length]
}

function shadeHex(hex: string, amount: number): string {
  const [r, g, b] = hexToRgb(hex)
  const factor = 1 + amount
  return rgbToHex(r * factor, g * factor, b * factor)
}

function isWater(world: WorldData, x: number, y: number): boolean {
  if (x < 0 || y < 0 || x >= world.width || y >= world.height) return true
  return WATER.has(world.tiles.terrain[y * world.width + x])
}

function poly(
  ctx: CanvasRenderingContext2D,
  points: Array<[number, number]>,
  fill: string,
  alpha: number,
) {
  ctx.globalAlpha = alpha
  ctx.fillStyle = fill
  ctx.beginPath()
  ctx.moveTo(Math.round(points[0][0]), Math.round(points[0][1]))
  for (let i = 1; i < points.length; i += 1) {
    ctx.lineTo(Math.round(points[i][0]), Math.round(points[i][1]))
  }
  ctx.closePath()
  ctx.fill()
  ctx.globalAlpha = 1
}

/**
 * Paint the tile grid at exactly one canvas pixel per device pixel.
 *
 * The old terrain was SVG: 72x48 unit squares stretched by a fractional factor
 * such as 13.9, so every edge fell between physical pixels and the compositor
 * antialiased it into a soft smear. Here tile geometry is integer pixel
 * geometry, no smoothing is enabled, and the surface is sized from the actual
 * device pixel ratio, so a 4K display gets a genuinely 4K terrain.
 */
function drawTerrain(
  canvas: HTMLCanvasElement,
  world: WorldData,
  overlay: MapOverlay,
  owners: string[],
  tilePx: number,
) {
  const ctx = canvas.getContext('2d', { alpha: false })
  if (!ctx) return
  const surfaceW = world.width * tilePx
  const surfaceH = world.height * tilePx
  if (canvas.width !== surfaceW) canvas.width = surfaceW
  if (canvas.height !== surfaceH) canvas.height = surfaceH
  ctx.imageSmoothingEnabled = false

  const t = tilePx
  const half = t / 2

  // Base colours. Integer fillRect => hard edges, no interpolation, ever.
  for (let y = 0; y < world.height; y += 1) {
    for (let x = 0; x < world.width; x += 1) {
      const index = y * world.width + x
      let color = tileColor({
        terrain: world.tiles.terrain[index],
        fertility: world.tiles.fertility[index],
        water: world.tiles.water[index],
        buildable: world.tiles.buildable[index],
      }, overlay)
      const owner = world.tiles.owner[index]
      if (overlay === 'territory' && owner) {
        const ownerIndex = owners.indexOf(owner)
        if (ownerIndex >= 0) color = territoryColor(color, SETTLEMENT_COLORS[ownerIndex % SETTLEMENT_COLORS.length])
      }
      ctx.fillStyle = shadeHex(color, tileShade(world.seed ?? 0, x, y))
      ctx.fillRect(x * t, y * t, t, t)
    }
  }

  // Coastline as solid pixel runs rather than a stroked path.
  const coastPx = Math.max(1, Math.round(t * 0.07))
  ctx.fillStyle = '#d7e6da'
  ctx.globalAlpha = 0.30
  for (let y = 0; y < world.height; y += 1) {
    for (let x = 0; x < world.width; x += 1) {
      const terrainName = world.tiles.terrain[y * world.width + x]
      if (WATER.has(terrainName)) continue
      const ox = x * t
      const oy = y * t
      if (isWater(world, x, y - 1)) ctx.fillRect(ox, oy, t, coastPx)
      if (isWater(world, x, y + 1)) ctx.fillRect(ox, oy + t - coastPx, t, coastPx)
      if (isWater(world, x - 1, y)) ctx.fillRect(ox, oy, coastPx, t)
      if (isWater(world, x + 1, y)) ctx.fillRect(ox + t - coastPx, oy, coastPx, t)
    }
  }
  ctx.globalAlpha = 1

  // Terrain glyphs, drawn from integer coordinates so they stay legible at 4K.
  if (overlay === 'terrain' || overlay === 'territory') {
    const dash = Math.max(1, Math.round(t * 0.06))
    for (let y = 0; y < world.height; y += 1) {
      for (let x = 0; x < world.width; x += 1) {
        const terrainName = world.tiles.terrain[y * world.width + x]
        const ox = x * t
        const oy = y * t
        if (terrainName === 'mountain') {
          poly(ctx, [
            [ox + t * 0.16, oy + t * 0.80],
            [ox + t * 0.42, oy + t * 0.20],
            [ox + t * 0.68, oy + t * 0.80],
          ], '#c8cdd6', 0.32)
          poly(ctx, [
            [ox + t * 0.42, oy + t * 0.20],
            [ox + t * 0.68, oy + t * 0.80],
            [ox + t * 0.54, oy + t * 0.80],
          ], '#202839', 0.22)
          poly(ctx, [
            [ox + t * 0.62, oy + t * 0.84],
            [ox + t * 0.78, oy + t * 0.56],
            [ox + t * 0.94, oy + t * 0.84],
          ], '#c8cdd6', 0.20)
        } else if (terrainName === 'forest') {
          poly(ctx, [
            [ox + t * 0.14, oy + t * 0.74],
            [ox + t * 0.34, oy + t * 0.28],
            [ox + t * 0.54, oy + t * 0.74],
          ], '#14301f', 0.50)
          poly(ctx, [
            [ox + t * 0.46, oy + t * 0.78],
            [ox + t * 0.66, oy + t * 0.40],
            [ox + t * 0.86, oy + t * 0.78],
          ], '#14301f', 0.38)
        } else if (terrainName === 'desert') {
          poly(ctx, [
            [ox + t * 0.50, oy + t * 0.34],
            [ox + t * 0.74, oy + t * 0.50],
            [ox + t * 0.50, oy + t * 0.66],
            [ox + t * 0.26, oy + t * 0.50],
          ], '#ead39b', 0.45)
          poly(ctx, [
            [ox + t * 0.76, oy + t * 0.20],
            [ox + t * 0.86, oy + t * 0.28],
            [ox + t * 0.76, oy + t * 0.36],
            [ox + t * 0.66, oy + t * 0.28],
          ], '#ead39b', 0.30)
        } else if (terrainName === 'swamp') {
          ctx.fillStyle = '#1c3428'
          ctx.globalAlpha = 0.55
          ctx.fillRect(Math.round(ox + t * 0.20), Math.round(oy + t * 0.44), Math.round(t * 0.42), dash)
          ctx.fillRect(Math.round(ox + t * 0.40), Math.round(oy + t * 0.62), Math.round(t * 0.34), dash)
          ctx.globalAlpha = 1
        } else if (terrainName === 'fertile' || terrainName === 'plains') {
          // A couple of grass tufts give large fields visible structure instead
          // of flat colour, without turning the map into noise.
          const grain = Math.max(1, Math.round(t * 0.05))
          const tuft = Math.round(t * 0.16)
          ctx.fillStyle = '#22381f'
          ctx.globalAlpha = 0.22
          ctx.fillRect(Math.round(ox + t * 0.24), Math.round(oy + t * 0.58), grain, tuft)
          ctx.fillRect(Math.round(ox + t * 0.70), Math.round(oy + t * 0.30), grain, Math.round(tuft * 0.75))
          ctx.globalAlpha = 1
        }
      }
    }
  }

  if (overlay === 'resources') {
    const radius = Math.max(2, Math.round(t * 0.09))
    for (let y = 0; y < world.height; y += 1) {
      for (let x = 0; x < world.width; x += 1) {
        const deposits = world.tiles.resources[y * world.width + x]
        if (!deposits) continue
        const keys = Object.keys(deposits).slice(0, 3)
        keys.forEach((key, slot) => {
          const cx = Math.round(x * t + half + (slot - 1) * t * 0.24)
          const cy = Math.round(y * t + half)
          poly(ctx, [
            [cx, cy - radius],
            [cx + radius, cy],
            [cx, cy + radius],
            [cx - radius, cy],
          ], RESOURCE_COLORS[key] ?? '#ffffff', 0.9)
        })
      }
    }
  }
}

function clientToViewBox(svg: SVGSVGElement, clientX: number, clientY: number) {
  const point = svg.createSVGPoint()
  point.x = clientX
  point.y = clientY
  const matrix = svg.getScreenCTM()
  if (!matrix) return { x: 0, y: 0 }
  const mapped = point.matrixTransform(matrix.inverse())
  return { x: mapped.x, y: mapped.y }
}

export function WorldMap({
  world,
  agents,
  settlements,
  overlay = 'terrain',
  selectedAgentId,
  selectedSettlementId,
  onSelectAgent,
  onSelectSettlement,
  onSelectTile,
}: {
  world: WorldData | null
  agents: AgentSummary[]
  settlements: SettlementSummary[]
  overlay?: MapOverlay
  selectedAgentId?: string | null
  selectedSettlementId?: string | null
  onSelectAgent?: (id: string) => void
  onSelectSettlement?: (id: string) => void
  onSelectTile?: (tile: { x: number; y: number }) => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const dragRef = useRef<{ startX: number; startY: number; panX: number; panY: number; moved: boolean } | null>(null)
  const suppressClick = useRef(false)
  const [view, setView] = useState({ zoom: 1, panX: 0, panY: 0 })
  const viewRef = useRef(view)
  viewRef.current = view

  // Measured size in CSS px plus the display's real device pixel ratio.
  const [box, setBox] = useState({ width: 0, height: 0, dpr: 1 })

  useEffect(() => {
    const element = containerRef.current
    if (!element) return
    const update = () => {
      const rect = element.getBoundingClientRect()
      setBox({
        width: rect.width,
        height: rect.height,
        dpr: window.devicePixelRatio || 1,
      })
    }
    update()
    const observer = new ResizeObserver(update)
    observer.observe(element)
    const media = window.matchMedia(`(resolution: ${window.devicePixelRatio || 1}dppx)`)
    media.addEventListener('change', update)
    window.addEventListener('resize', update)
    return () => {
      observer.disconnect()
      media.removeEventListener('change', update)
      window.removeEventListener('resize', update)
    }
  }, [])

  const territoryOrder = useMemo(() => settlements.map((settlement) => settlement.id).join('|'), [settlements])
  const settlementColors = useMemo(() => {
    const palette = new Map<string, string>()
    settlements.forEach((settlement, index) => {
      palette.set(settlement.id, SETTLEMENT_COLORS[index % SETTLEMENT_COLORS.length])
    })
    return palette
  }, [settlements])

  // Fit the world's aspect ratio inside the panel, then choose an integer tile
  // size in *device* pixels. The canvas never needs fractional geometry.
  const fit = world && box.width > 0 && box.height > 0
    ? Math.min(box.width / world.width, box.height / world.height)
    : 0
  const contentWidth = world ? world.width * fit : 0
  const contentHeight = world ? world.height * fit : 0
  const tilePx = Math.max(2, Math.min(MAX_TILE_PX, Math.ceil((fit || 1) * box.dpr)))
  const surfaceWidth = world ? world.width * tilePx : 0
  const surfaceHeight = world ? world.height * tilePx : 0

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !world || fit <= 0) return
    const owners = territoryOrder ? territoryOrder.split('|') : []
    drawTerrain(canvas, world, overlay, owners, tilePx)
  }, [world, overlay, territoryOrder, tilePx, fit])

  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return
    const onWheel = (event: WheelEvent) => {
      event.preventDefault()
      const point = clientToViewBox(svg, event.clientX, event.clientY)
      const current = viewRef.current
      const factor = event.deltaY < 0 ? 1.15 : 0.87
      const zoom = Math.max(1, Math.min(8, current.zoom * factor))
      const worldX = (point.x - current.panX) / current.zoom
      const worldY = (point.y - current.panY) / current.zoom
      setView({ zoom, panX: point.x - worldX * zoom, panY: point.y - worldY * zoom })
    }
    svg.addEventListener('wheel', onWheel, { passive: false })
    return () => svg.removeEventListener('wheel', onWheel)
  }, [])

  const resetIfNeeded = () => {
    if (viewRef.current.zoom === 1 && viewRef.current.panX === 0 && viewRef.current.panY === 0) return
    setView({ zoom: 1, panX: 0, panY: 0 })
  }

  const handlePointerDown = (event: React.PointerEvent<SVGSVGElement>) => {
    if (event.button !== 0) return
    const svg = event.currentTarget
    const point = clientToViewBox(svg, event.clientX, event.clientY)
    dragRef.current = {
      startX: point.x, startY: point.y,
      panX: viewRef.current.panX, panY: viewRef.current.panY,
      moved: false,
    }
    svg.setPointerCapture(event.pointerId)
  }

  const handlePointerMove = (event: React.PointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current
    if (!drag) return
    const point = clientToViewBox(event.currentTarget, event.clientX, event.clientY)
    const dx = point.x - drag.startX
    const dy = point.y - drag.startY
    if (!drag.moved && Math.abs(dx) + Math.abs(dy) > 0.12) drag.moved = true
    setView((current) => ({ ...current, panX: drag.panX + dx, panY: drag.panY + dy }))
  }

  const handlePointerUp = () => {
    const drag = dragRef.current
    if (drag?.moved) {
      suppressClick.current = true
      window.setTimeout(() => { suppressClick.current = false }, 0)
    }
    dragRef.current = null
  }

  const handleMapClick = (event: React.MouseEvent<SVGSVGElement>) => {
    if (suppressClick.current || !world || !onSelectTile) return
    const point = clientToViewBox(event.currentTarget, event.clientX, event.clientY)
    const x = Math.floor((point.x - view.panX) / view.zoom)
    const y = Math.floor((point.y - view.panY) / view.zoom)
    if (x >= 0 && y >= 0 && x < world.width && y < world.height) onSelectTile({ x, y })
  }

  if (!world) {
    return (
      <div className="map-canvas relative h-full w-full bg-bg">
        <div className="absolute inset-0 flex items-center justify-center font-mono text-[11px] uppercase tracking-widest text-dim">
          Generating world…
        </div>
      </div>
    )
  }

  const markerScale = 1 / view.zoom
  const labelFont = 0.78
  const left = (box.width - contentWidth) / 2
  const top = (box.height - contentHeight) / 2
  // Keep the canvas and the marker SVG on the exact same transform. The canvas
  // is in CSS pixels (fit px per world unit); the SVG is in world units.
  const canvasTransform = `translate(${view.panX * fit}px, ${view.panY * fit}px) scale(${view.zoom})`

  return (
    <div ref={containerRef} className="map-canvas relative h-full w-full overflow-hidden bg-bg">
      <div
        className="absolute"
        style={{ left: `${left}px`, top: `${top}px`, width: `${contentWidth}px`, height: `${contentHeight}px` }}
      >
        <canvas
          ref={canvasRef}
          width={surfaceWidth}
          height={surfaceHeight}
          className="absolute inset-0 h-full w-full"
          style={{
            imageRendering: 'pixelated',
            transform: canvasTransform,
            transformOrigin: '0 0',
          }}
        />
        <svg
          ref={svgRef}
          viewBox={`0 0 ${world.width} ${world.height}`}
          preserveAspectRatio="none"
          className="absolute inset-0 h-full w-full select-none"
          style={{ touchAction: 'none', cursor: dragRef.current ? 'grabbing' : 'grab', overflow: 'visible' }}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
          onDoubleClick={resetIfNeeded}
          onClick={handleMapClick}
        >
          <g transform={`translate(${view.panX} ${view.panY}) scale(${view.zoom})`}>
            {settlements.map((settlement) => {
              const selected = settlement.id === selectedSettlementId
              const color = settlementColors.get(settlement.id) ?? '#f0b35a'
              return (
                <g
                  key={settlement.id}
                  transform={`translate(${settlement.x + 0.5} ${settlement.y + 0.5}) scale(${markerScale})`}
                  style={{ cursor: 'pointer' }}
                  onClick={(event) => {
                    event.stopPropagation()
                    if (!suppressClick.current) onSelectSettlement?.(settlement.id)
                  }}
                >
                  <path
                    d="M0 -0.5L0.5 0L0 0.5L-0.5 0Z"
                    fill={color}
                    stroke={selected ? '#ffffff' : '#0a101b'}
                    strokeWidth={selected ? 0.16 : 0.09}
                  />
                  <g style={{ pointerEvents: 'none' }}>
                    <rect
                      x={-(settlement.name.length * 0.43 + 0.5) / 2}
                      y={0.2}
                      width={settlement.name.length * 0.43 + 0.5}
                      height={0.95}
                      rx={0.22}
                      fill="#070b12"
                      fillOpacity={0.82}
                      stroke="#1d2b3f"
                      strokeWidth={0.045}
                    />
                    <text
                      x={0}
                      y={0.86}
                      textAnchor="middle"
                      fontFamily="JetBrains Mono, monospace"
                      fontSize={labelFont}
                      fontWeight={600}
                      fill="#f4ecdc"
                    >
                      {settlement.name}
                    </text>
                  </g>
                </g>
              )
            })}

            {agents.filter((agent) => agent.alive).map((agent) => {
              const selected = agent.id === selectedAgentId
              const color = agent.settlement_id ? settlementColors.get(agent.settlement_id) ?? '#dce7f5' : '#9aa7b4'
              return (
                <circle
                  key={agent.id}
                  cx={agent.x + 0.5}
                  cy={agent.y + 0.5}
                  r={(selected ? 0.34 : 0.23) * markerScale}
                  fill={color}
                  stroke={selected ? '#ffffff' : '#070b12'}
                  strokeWidth={(selected ? 0.12 : 0.06) * markerScale}
                  style={{ cursor: 'pointer' }}
                  onClick={(event) => {
                    event.stopPropagation()
                    if (!suppressClick.current) onSelectAgent?.(agent.id)
                  }}
                />
              )
            })}
          </g>
        </svg>
      </div>
      <div className="pointer-events-none absolute right-3 top-3 rounded border border-edge bg-bg/85 px-2 py-1 font-mono text-[9px] uppercase tracking-wider text-dim">
        canvas · {surfaceWidth}×{surfaceHeight} px · dpr {Math.round(box.dpr * 100) / 100}× · {tilePx}px/tile
      </div>
      <div className="pointer-events-none absolute bottom-3 left-3 rounded border border-edge bg-bg/85 px-2 py-1 font-mono text-[9px] uppercase tracking-wider text-dim">
        drag to pan · scroll to zoom · double-click to reset
      </div>
    </div>
  )
}
