import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity, AlertTriangle, Atom, FlaskConical, Globe2, Hammer, Landmark,
  Link2, Loader2, RefreshCw, ScrollText, Sigma, Sparkles, Users,
} from 'lucide-react'
import clsx from 'clsx'
import { useStore } from '../store'
import { api } from '../api'
import { Badge, EmptyState, Panel, StatCard } from '../components/ui'
import { fmt } from '../lib/format'
import type { EmergenceFinding, EmergenceReport } from '../types'

const KIND_ORDER = [
  'institution', 'technology', 'politics', 'diplomacy', 'economy', 'settlement',
  'structure', 'collapse', 'language', 'demography', 'anomaly',
] as const

const KIND_LABEL: Record<string, string> = {
  institution: 'institution',
  technology: 'technology',
  politics: 'politics',
  diplomacy: 'diplomacy',
  economy: 'economy',
  settlement: 'settlement',
  structure: 'structure',
  collapse: 'collapse',
  language: 'language',
  demography: 'demography',
  anomaly: 'anomaly',
}

const KIND_TONE: Record<string, 'muted' | 'good' | 'danger' | 'amber' | 'teal' | 'violet'> = {
  institution: 'teal',
  technology: 'violet',
  politics: 'amber',
  diplomacy: 'good',
  economy: 'teal',
  settlement: 'amber',
  structure: 'violet',
  collapse: 'danger',
  language: 'violet',
  demography: 'muted',
  anomaly: 'danger',
}

function KindIcon({ kind, size = 13 }: { kind: string; size?: number }) {
  switch (kind) {
    case 'technology': return <Sparkles size={size} />
    case 'politics': return <Landmark size={size} />
    case 'diplomacy': return <Globe2 size={size} />
    case 'economy': return <Sigma size={size} />
    case 'settlement': return <Globe2 size={size} />
    case 'structure': return <Atom size={size} />
    case 'collapse': return <AlertTriangle size={size} />
    case 'language': return <ScrollText size={size} />
    case 'demography': return <Users size={size} />
    case 'anomaly': return <Activity size={size} />
    default: return <Hammer size={size} />
  }
}

function FindingCard({ finding }: { finding: EmergenceFinding }) {
  return (
    <article className="border-b border-edge-soft/60 px-4 py-3.5 last:border-0">
      <div className="flex items-start gap-3">
        <div className={clsx(
          'mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded border border-edge-soft bg-bg2/50',
          finding.kind === 'anomaly' || finding.kind === 'collapse' ? 'text-danger' : 'text-dim',
        )}>
          <KindIcon kind={finding.kind} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge tone={KIND_TONE[finding.kind] ?? 'muted'}>{KIND_LABEL[finding.kind] ?? finding.kind}</Badge>
            {finding.confidence === 'hypothesis' && <Badge tone="amber">hypothesis</Badge>}
            <span className="font-mono text-[8.5px] uppercase tracking-wider text-dim">
              day {fmt(finding.day)} · year {fmt(finding.year)} · {finding.season}
            </span>
          </div>
          <h3 className="mt-1.5 text-[12.5px] font-medium leading-snug text-fg">{finding.title}</h3>
          <p className="mt-1 text-[11px] leading-relaxed text-muted">{finding.observed}</p>

          {finding.measured.length > 0 && (
            <div className="mt-2 rounded border border-edge-soft bg-bg2/40 px-2.5 py-2">
              <div className="stat-label mb-1">measured from the daily series</div>
              <ul className="space-y-0.5">
                {finding.measured.map((line) => (
                  <li key={line} className="num text-[10.5px] leading-relaxed text-teal">{line}</li>
                ))}
              </ul>
            </div>
          )}

          {finding.hypothesis && (
            <div className="mt-2 flex gap-2 rounded border border-amber/25 bg-amber/[0.05] px-2.5 py-2">
              <FlaskConical size={12} className="mt-0.5 shrink-0 text-amber" />
              <div className="min-w-0">
                <div className="font-mono text-[8.5px] uppercase tracking-wider text-amber">hypothesis — the log does not establish this</div>
                <p className="mt-0.5 text-[10.5px] leading-relaxed text-muted">{finding.hypothesis}</p>
              </div>
            </div>
          )}

          {finding.evidence.length > 0 && (
            <div className="mt-2">
              <div className="stat-label mb-1">evidence rows</div>
              <div className="space-y-0.5">
                {finding.evidence.map((row) => (
                  <div key={row.event_id} className="flex items-baseline gap-1.5 text-[10px]">
                    <Link2 size={9} className="shrink-0 text-dim" />
                    <span className="shrink-0 font-mono text-dim">d{fmt(row.day)}</span>
                    <span className="truncate text-muted" title={row.title}>{row.title}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {finding.participants.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {finding.participants.map((participant) => (
                <span key={participant} className="rounded border border-edge-soft px-1.5 py-0.5 font-mono text-[8.5px] text-dim">{participant}</span>
              ))}
            </div>
          )}
        </div>
      </div>
    </article>
  )
}

export function EmergencePage() {
  const state = useStore((s) => s.state)
  const runId = state?.run.id
  const day = state?.run.day ?? 0

  const [report, setReport] = useState<EmergenceReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [kind, setKind] = useState<string>('all')
  const [confidence, setConfidence] = useState<'all' | 'observation' | 'hypothesis'>('all')
  const [newestFirst, setNewestFirst] = useState(true)
  const [tick, setTick] = useState(0)

  const lastFetch = useRef<{ runId: string; day: number } | null>(null)
  const forceRefresh = useRef(false)
  const seq = useRef(0)

  useEffect(() => {
    if (!runId) return
    const last = lastFetch.current
    const due = forceRefresh.current
      || !last
      || last.runId !== runId
      || day - last.day >= 8
    if (!due) return
    forceRefresh.current = false
    lastFetch.current = { runId, day }
    const current = ++seq.current
    setLoading(true)
    api.getEmergence(runId)
      .then((next) => {
        if (seq.current !== current) return
        setReport(next)
        setError(null)
      })
      .catch((err: unknown) => {
        if (seq.current !== current) return
        setError(err instanceof Error ? err.message : 'Could not read the emergence report')
      })
      .finally(() => {
        if (seq.current === current) setLoading(false)
      })
  }, [runId, day, tick])

  const data = report && report.run_id === runId ? report : null
  const findings = useMemo(() => data?.findings ?? [], [data])

  const kindCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const finding of findings) counts[finding.kind] = (counts[finding.kind] ?? 0) + 1
    return counts
  }, [findings])

  const presentKinds = useMemo(
    () => KIND_ORDER.filter((entry) => (kindCounts[entry] ?? 0) > 0),
    [kindCounts],
  )

  const visible = useMemo(() => {
    const rows = findings.filter((finding) => (
      (kind === 'all' || finding.kind === kind)
      && (confidence === 'all' || finding.confidence === confidence)
    ))
    const ordered = [...rows].sort((a, b) => (newestFirst ? b.day - a.day : a.day - b.day))
    return ordered
  }, [findings, kind, confidence, newestFirst])

  const hypotheses = findings.filter((finding) => finding.confidence === 'hypothesis').length
  const anomalies = kindCounts.anomaly ?? 0
  const structural = findings.length - anomalies
  const metricDays = data?.metric_days ?? 0
  const eventCount = data?.event_count ?? 0

  if (!state) return <EmptyState icon={<Atom size={22} />} title="No run loaded" />

  const refresh = () => {
    forceRefresh.current = true
    setTick((value) => value + 1)
  }

  return (
    <div className="scroll-area h-full">
      <div className="mx-auto max-w-[1500px] space-y-4 px-5 py-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard
            label="recorded findings"
            value={fmt(findings.length)}
            hint={`${fmt(eventCount)} events scanned`}
            icon={<Atom size={14} />}
            tone="amber"
          />
          <StatCard
            label="structural firsts"
            value={fmt(structural)}
            hint="institutions, politics, technology, contact"
            icon={<Sparkles size={14} />}
            tone="teal"
          />
          <StatCard
            label="statistical anomalies"
            value={fmt(anomalies)}
            hint={`${fmt(metricDays)} daily metric rows`}
            icon={<Activity size={14} />}
            tone={anomalies ? 'danger' : 'default'}
          />
          <StatCard
            label="labelled hypotheses"
            value={fmt(hypotheses)}
            hint="causal claims the log cannot prove"
            icon={<FlaskConical size={14} />}
            tone="violet"
          />
        </div>

        <Panel
          title="Emergence detector"
          eyebrow="read from the persisted event log and daily metrics"
          action={(
            <button
              type="button"
              className="btn-ghost flex items-center gap-1.5 p-1 font-mono text-[9px] uppercase tracking-wider text-dim hover:text-fg"
              onClick={refresh}
              disabled={loading}
            >
              {loading ? <Loader2 size={11} className="animate-spin" /> : <RefreshCw size={11} />}
              {loading ? 'scanning' : 'rescan'}
            </button>
          )}
        >
          <div className="flex flex-wrap items-center gap-2 border-b border-edge-soft/60 px-4 py-2.5">
            <button
              type="button"
              onClick={() => setKind('all')}
              className={clsx(
                'rounded px-2 py-1 font-mono text-[9px] uppercase tracking-wider transition-colors',
                kind === 'all' ? 'bg-amber/15 text-amber' : 'text-muted hover:bg-white/5 hover:text-fg',
              )}
            >
              all · {findings.length}
            </button>
            {presentKinds.map((entry) => (
              <button
                key={entry}
                type="button"
                onClick={() => setKind(entry)}
                className={clsx(
                  'rounded px-2 py-1 font-mono text-[9px] uppercase tracking-wider transition-colors',
                  kind === entry ? 'bg-amber/15 text-amber' : 'text-muted hover:bg-white/5 hover:text-fg',
                )}
              >
                {KIND_LABEL[entry]} · {kindCounts[entry]}
              </button>
            ))}
            <span className="mx-1 h-4 w-px bg-edge-soft" />
            {(['all', 'observation', 'hypothesis'] as const).map((entry) => (
              <button
                key={entry}
                type="button"
                onClick={() => setConfidence(entry)}
                className={clsx(
                  'rounded px-2 py-1 font-mono text-[9px] uppercase tracking-wider transition-colors',
                  confidence === entry ? 'bg-teal/15 text-teal' : 'text-muted hover:bg-white/5 hover:text-fg',
                )}
              >
                {entry === 'all' ? 'any confidence' : entry}
              </button>
            ))}
            <button
              type="button"
              onClick={() => setNewestFirst((value) => !value)}
              className="ml-auto rounded px-2 py-1 font-mono text-[9px] uppercase tracking-wider text-dim hover:bg-white/5 hover:text-fg"
            >
              {newestFirst ? 'newest first' : 'oldest first'}
            </button>
          </div>

          {error && (
            <div className="flex items-center gap-2 border-b border-danger/25 bg-danger/[0.05] px-4 py-2.5 text-[10.5px] text-danger">
              <AlertTriangle size={12} className="shrink-0" />
              {error}
            </div>
          )}

          {!data && loading && (
            <div className="flex items-center justify-center gap-2 px-4 py-16 font-mono text-[9px] uppercase tracking-[0.2em] text-dim">
              <Loader2 size={13} className="animate-spin" /> reading the record
            </div>
          )}

          {!data && !loading && !error && (
            <div className="px-4 py-16 text-center text-[11.5px] text-muted">
              No report yet. Use rescan to read this world's persisted record.
            </div>
          )}

          {data && visible.length === 0 && (
            <div className="px-4 py-16 text-center text-[11.5px] leading-relaxed text-muted">
              {findings.length === 0
                ? 'This world has not recorded a structural first yet. The detector only reports rows that exist in the log.'
                : 'No finding matches these filters.'}
            </div>
          )}

          {visible.map((finding) => <FindingCard key={finding.id} finding={finding} />)}
        </Panel>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Panel title="How a finding is produced" eyebrow="no invented conclusions">
            <div className="flex gap-2 px-4 py-3 text-[10.5px] leading-relaxed text-muted">
              <ScrollText size={13} className="mt-0.5 shrink-0 text-dim" />
              <div className="space-y-2">
                <p>
                  The detector reads the same persisted event rows and daily metric rows as the History and Overview pages.
                  It reports the first occurrence of a structural change, or an outlier computed directly from the metric series.
                </p>
                <p>
                  A measured line is a difference between two recorded days, with the window stated. Nothing is estimated,
                  interpolated or filled in.
                </p>
                <p>
                  Where the page draws a causal connection, it is labelled <span className="text-amber">hypothesis</span> and
                  says that the log only establishes temporal proximity, not cause.
                </p>
              </div>
            </div>
          </Panel>

          <Panel title="Coverage in this run" eyebrow="what the scanner looked at">
            <div className="space-y-2 px-4 py-3">
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-muted">persisted events</span>
                <span className="num text-fg">{fmt(eventCount)}</span>
              </div>
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-muted">daily metric rows</span>
                <span className="num text-fg">{fmt(metricDays)}</span>
              </div>
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-muted">world day at scan</span>
                <span className="num text-fg">{fmt(data?.day ?? day)}</span>
              </div>
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-muted">findings returned</span>
                <span className="num text-fg">{fmt(findings.length)}</span>
              </div>
              <p className="pt-1 text-[10px] leading-relaxed text-dim">
                Findings are capped at the earliest 100 by day. The scan covers the entire stored log, not just recent days.
              </p>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  )
}
