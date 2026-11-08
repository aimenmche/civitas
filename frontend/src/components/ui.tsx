import type { ReactNode } from 'react'
import { Activity, ArrowDownRight, ArrowUpRight } from 'lucide-react'
import clsx from 'clsx'

export function Panel({
  title,
  eyebrow,
  action,
  children,
  className,
  bodyClassName,
}: {
  title?: ReactNode
  eyebrow?: string
  action?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
}) {
  return (
    <section className={clsx('panel flex min-h-0 flex-col', className)}>
      {(title || eyebrow) && (
        <header className="panel-head">
          <div className="min-w-0">
            {eyebrow && <div className="eyebrow mb-0.5">{eyebrow}</div>}
            {title && <h2 className="truncate text-[13px] font-semibold tracking-wide text-fg">{title}</h2>}
          </div>
          {action}
        </header>
      )}
      <div className={clsx('min-h-0 flex-1', bodyClassName)}>{children}</div>
    </section>
  )
}

export function StatCard({
  label,
  value,
  hint,
  icon,
  tone = 'default',
  trend,
}: {
  label: string
  value: ReactNode
  hint?: ReactNode
  icon?: ReactNode
  tone?: 'default' | 'amber' | 'teal' | 'violet' | 'danger' | 'good'
  trend?: number
}) {
  const tones: Record<string, string> = {
    default: 'text-fg',
    amber: 'text-amber',
    teal: 'text-teal',
    violet: 'text-violet',
    danger: 'text-danger',
    good: 'text-good',
  }
  return (
    <div className="panel px-4 py-3.5">
      <div className="flex items-start justify-between gap-2">
        <span className="stat-label">{label}</span>
        {icon ? <span className="text-dim">{icon}</span> : trend !== undefined ? (
          <span className={clsx('inline-flex items-center gap-0.5 font-mono text-[10px]', trend >= 0 ? 'text-good' : 'text-danger')}>
            {trend >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
            {Math.abs(trend).toFixed(0)}
          </span>
        ) : null}
      </div>
      <div className={clsx('stat-value mt-1.5', tones[tone])}>{value}</div>
      {hint && <div className="mt-1 truncate text-[11px] text-muted">{hint}</div>}
    </div>
  )
}

export function NeedBar({
  label,
  value,
  tone,
  compact = false,
}: {
  label: string
  value: number
  tone: string
  compact?: boolean
}) {
  return (
    <div className={compact ? 'space-y-1' : 'space-y-1.5'}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[11px] capitalize text-muted">{label}</span>
        <span className="num text-[11px] text-fg">{Math.round(value)}</span>
      </div>
      <div className="meter">
        <div className="meter-fill" style={{ width: `${Math.max(0, Math.min(100, value))}%`, background: tone }} />
      </div>
    </div>
  )
}

export function Meter({
  value,
  max = 100,
  tone = 'var(--color-teal)',
  className,
}: {
  value: number
  max?: number
  tone?: string
  className?: string
}) {
  const width = Math.max(0, Math.min(100, (value / Math.max(1, max)) * 100))
  return (
    <div className={clsx('meter', className)}>
      <div className="meter-fill" style={{ width: `${width}%`, background: tone }} />
    </div>
  )
}

export function EmptyState({
  icon,
  title,
  children,
}: {
  icon?: ReactNode
  title: string
  children?: ReactNode
}) {
  return (
    <div className="flex h-full min-h-[140px] flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      <div className="text-dim">{icon ?? <Activity size={22} />}</div>
      <div className="text-sm font-medium text-fg">{title}</div>
      {children && <div className="max-w-sm text-xs leading-relaxed text-muted">{children}</div>}
    </div>
  )
}

export function Badge({
  children,
  tone = 'muted',
  className,
}: {
  children: ReactNode
  tone?: 'muted' | 'good' | 'danger' | 'amber' | 'teal' | 'violet'
  className?: string
}) {
  const tones: Record<string, string> = {
    muted: 'text-muted border-edge bg-panel2/70',
    good: 'text-good border-good/30 bg-good/10',
    danger: 'text-danger border-danger/30 bg-danger/10',
    amber: 'text-amber border-amber/30 bg-amber/10',
    teal: 'text-teal border-teal/30 bg-teal/10',
    violet: 'text-violet border-violet/30 bg-violet/10',
  }
  return <span className={clsx('chip', tones[tone], className)}>{children}</span>
}

export function Divider({ className }: { className?: string }) {
  return <div className={clsx('h-px w-full bg-edge-soft', className)} />
}

export function KeyValue({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5">
      <span className="text-[11px] text-muted">{label}</span>
      <span className="num text-right text-[12px] text-fg">{value}</span>
    </div>
  )
}
