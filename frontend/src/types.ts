export type Page =
  | 'overview'
  | 'world'
  | 'agents'
  | 'settlements'
  | 'economy'
  | 'politics'
  | 'culture'
  | 'technology'
  | 'diplomacy'
  | 'history'
  | 'emergence'
  | 'experiments'
  | 'multiverse'
  | 'settings'

export interface RunSummary {
  id: string
  world_name: string
  preset: string
  seed: number
  status: string
  speed: number
  day: number
  population: number
  settlements: number
  note?: string
  parent_run_id?: string | null
  branch_day?: number | null
  created_at?: string | null
  updated_at?: string | null
  last_error?: string | null
}

export interface MetricsPoint {
  day: number
  year?: number
  season?: string
  population?: number
  births?: number
  deaths?: number
  settlements?: number
  buildings?: number
  avg_happiness?: number
  avg_health?: number
  avg_trust?: number
  food?: number
  food_stores?: number
  water?: number
  inequality?: number
  wealth_median?: number
  wealth_max?: number
  tech_count?: number
  era?: string
  conflicts?: number
  trades?: number
  trades_today?: number
  stability?: number
  children?: number
  elders?: number
  generations?: number
  families?: number
  languages?: number
}

export interface WorldConfig {
  world_name: string
  preset: string
  seed?: number | null
  width: number
  height: number
  initial_population: number
  climate: string
  resource_abundance: number
  environmental_difficulty: number
  personality_distribution: string
  starting_technology: string
  starting_groups: number
  cooperation_bias: number
  no_currency: boolean
  no_leader: boolean
  asymmetric_groups: boolean
  max_population: number
  notation: string
}

export interface RunInfo {
  id: string
  world_name: string
  seed: number
  day: number
  tick: number
  year: number
  season: string
  day_of_season: number
  time_label: string
  status: string
  weather: string
  disaster: Disaster | null
  config: WorldConfig
  population: number
  settlements: number
  births: number
  deaths: number
  techs: string[]
  era: string
  language_count: number
  culture_count: number
  family_count: number
}

export interface Disaster {
  kind: string
  severity: number
  started_day?: number
  until_day?: number
  center?: [number, number] | null
  description?: string
}

export interface AgentActionView {
  kind?: string
  label?: string
  target?: Record<string, unknown>
}

export interface AgentSummary {
  id: string
  name: string
  x: number
  y: number
  gender: string
  age: number
  generation: number
  alive: boolean
  settlement_id: string | null
  occupation: string
  state: string
  action: AgentActionView | null
  health: number
  happiness: number
  hunger: number
  thirst: number
  goal: string
  thought: string
  family_id: string | null
  partner_id: string | null
}

export interface Relationship {
  other_id: string
  other_name?: string
  other_alive?: boolean
  affinity: number
  trust: number
  interactions: number
  trades?: number
  conflicts?: number
  gifts?: number
  type?: string
  partnered?: boolean
  first_met_day?: number
  last_interaction_day?: number
  history?: Array<Record<string, unknown>>
  social_memories?: MemoryView[]
}

export interface MemoryView {
  id: string
  day: number
  kind: string
  summary: string
  importance: number
  sentiment: number
  participants?: string[]
  tags?: string[]
  location?: number[] | null
}

export interface AgentDetail extends AgentSummary {
  birth_day: number
  birth_location: number[] | null
  death_day: number | null
  death_cause: string | null
  personality: Record<string, number>
  skills: Record<string, number>
  needs: Record<string, number>
  inventory: Record<string, number>
  home_tile: number[] | null
  ambition: string
  relationships: Relationship[]
  family_id: string | null
  parent_ids: string[]
  child_ids: string[]
  partner_id: string | null
  memories: { short_term: MemoryView[]; long_term: MemoryView[]; [key: string]: unknown }
  memory_facts: string[]
  known_techs: string[]
  known_languages: string[]
  personal_vocabulary: Record<string, string>
  research_target: string | null
  research_progress: Record<string, number>
  influence: number
  reputation: number
  pregnant: Record<string, unknown> | null
  founder_of: string | null
  current_goal: Record<string, unknown>
  decision: Record<string, unknown>
  action: Record<string, unknown>
  plan: unknown
  lifespan: number
  reproductive_role: string
  wealth: number
  stats: Record<string, unknown>
  family?: {
    name?: string
    member_ids?: string[]
    members_detail?: Array<{ id: string; name: string; age: number; alive: boolean; relation: string }>
    [key: string]: unknown
  } | null
  parents: Array<{ id: string; name: string; alive: boolean }>
  children: Array<{ id: string; name: string; age: number; alive: boolean }>
  partner: { id: string; name: string; alive: boolean } | null
  settlement: { id: string; name: string } | null
}

export interface SettlementSummary {
  id: string
  name: string
  x: number
  y: number
  population: number
  founded_day: number
  founder_id: string
  leader_id: string | null
  leader_name: string | null
  territory_radius: number
  government: string
  government_label: string
  economic_stage: number
  uses_currency: boolean
  culture_id: string
  language_id: string
  buildings: number
  housing_capacity: number
  food: number
  water: number
  wealth: number
  safety: number
  stability: number
  happiness: number
  food_production: number
  abandoned_day: number | null
  ruins: boolean
  population_peak: number
}

export interface SettlementDetail extends Omit<SettlementSummary, 'government'> {
  storage: Record<string, number>
  storage_capacity: number
  buildings_detail: Array<{
    id?: string
    type: string
    name: string
    level?: number
    built_day?: number
    condition?: number
    housing?: number
    effect?: string
  }>
  build_queue: Array<{ id: string; type: string; name: string; work_required: number; work_done: number; started_day?: number }>
  government: Record<string, unknown>
  laws: Array<{ key: string; title: string; description: string; enacted_day: number; support: number; effects?: Record<string, number> }>
  factions: Array<{ id: string; name: string; value: string; description: string; members: string[]; share: number }>
  diplomacy: Record<string, { status: string; trust: number; since_day?: number }>
  known_techs: string[]
  market_prices: Record<string, number>
  trade_volume: number
  tax_revenue: number
  culture: Culture | null
  language: Language | null
  history: Array<Record<string, unknown>>
  stats: Record<string, unknown>
  members: Array<{ id: string; name: string; age: number; occupation: string; role: string }>
}

export interface Culture {
  id: string
  name: string
  settlement_id?: string
  values: Record<string, number>
  traditions: Array<{ name: string; description: string; category?: string; origin?: string; since_day?: number }>
  symbols?: string[]
  customs?: Array<Record<string, unknown>>
  art_forms?: Array<{ name?: string; by?: string; day?: number; form?: string; subject?: string }>
  taboos?: string[]
  cuisine?: string[]
  founded_day?: number
  [key: string]: unknown
}

export interface Language {
  id: string
  name: string
  family?: string
  lexicon: Record<string, string>
  speakers?: number
  origins?: string[]
  loans?: unknown[]
  [key: string]: unknown
}

export interface SimEvent {
  id: string
  run_id: string
  day: number
  year: number
  season: string
  category: string
  importance: number
  title: string
  description: string
  location: number[] | null
  location_name: string | null
  participants: string[]
  participant_names?: string[]
  consequences: string[]
  related: Record<string, unknown>
  narrative: string | null
}

export interface Transaction {
  day: number
  kind: string
  from?: string
  to?: string
  items?: Record<string, number>
  price?: number
  settlement_id?: string
  [key: string]: unknown
}

export interface FullState {
  run: RunInfo
  metrics: MetricsPoint
  agents: AgentSummary[]
  settlements: SettlementSummary[]
  cultures: Culture[]
  languages: Language[]
  families: Array<Record<string, unknown>>
  events: SimEvent[]
  metrics_history: MetricsPoint[]
  technology: TechnologyView
  transactions: Transaction[]
  world: {
    width: number
    height: number
    seed: number
    land_ratio: number
    rivers: number
    lakes: number
    biomes: Record<string, number>
    start_sites: Array<{ x: number; y: number; [key: string]: unknown }>
    disaster: Disaster | null
  }
}

export interface WorldData {
  width: number
  height: number
  seed: number
  land_ratio: number
  rivers: number
  lakes: number
  biomes: Record<string, number>
  start_sites?: Array<Record<string, unknown>>
  weather: string
  disaster: Disaster | null
  tiles: {
    terrain: string[]
    elevation: number[]
    water: number[]
    fertility: number[]
    buildable: boolean[]
    passable: boolean[]
    freshwater: boolean[]
    owner: (string | null)[]
    resources: Array<Record<string, number>>
  }
}

export interface TechNode {
  key: string
  name: string
  era: string
  cost: number
  prereq: string[]
  effect: string
  status: 'discovered' | 'available' | 'locked'
  progress: number
  conditions: Record<string, number | boolean>
}

export interface TechnologyView {
  era: string
  known: string[]
  tree: TechNode[]
  discoveries: Record<string, { day: number; year: number; agent_id: string; agent_name: string; settlement_id: string | null; settlement_name: string | null; initial: boolean }>
  researching: Array<{ agent_id: string; name: string; tech: string | null; progress: number }>
}

export interface EmergenceEvidence {
  event_id: string
  day: number
  title: string
}

export interface EmergenceFinding {
  id: string
  kind: string
  title: string
  day: number
  year: number
  season: string
  observed: string
  evidence: EmergenceEvidence[]
  measured: string[]
  hypothesis: string | null
  confidence: 'observation' | 'hypothesis'
  participants: string[]
}

export interface EmergenceReport {
  run_id: string
  day: number
  event_count: number
  metric_days: number
  counts: Record<string, number>
  findings: EmergenceFinding[]
}

export interface SnapshotInfo {
  id: string
  run_id: string
  day: number
  label: string
  created_at: string | null
}

export interface TickPayload {
  type: 'tick'
  run_id: string
  tick: number
  day: number
  year: number
  season: string
  day_of_season: number
  time_label: string
  weather: string
  status: string
  population: number
  births: number
  deaths: number
  metrics: MetricsPoint
  agents: AgentSummary[]
  settlements: SettlementSummary[]
  events: SimEvent[]
  speed?: number
}

export interface StatusPayload {
  type: 'status'
  run_id: string
  status: string
  day: number
  speed?: number
}

export interface StatePayload {
  type: 'state'
  state: FullState
}

export type SocketPayload = TickPayload | StatusPayload | StatePayload | { type: 'error'; run_id: string; error: string }
