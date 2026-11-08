import { useMemo } from 'react'
import clsx from 'clsx'
import { ScrollText } from 'lucide-react'
import type { SimEvent } from '../types'
import { eventCategoryTone, relativeDay } from '../lib/format'
import { EmptyState } from './ui'

export function EventFeed({
  events,
  limit = 20,
  dense = false,
  onSelect,
  className,
  currentDay,
}: {
  events: SimEvent[]
  limit?: number
  dense?: boolean
  onSelect?: (event: SimEvent) => void
  className?: string
  currentDay?: number
}) {
  const shown = useMemo(
    () => [...events].sort((a, b) => b.day - a.day || b.id.localeCompare(a.id)).slice(0, limit),
    [events, limit],
  )
  if (!shown.length) {
    return (
      <EmptyState icon={<ScrollText size={20} />} title="No recorded events yet">
        History is written when something actually happens: meals, meetings, births, discoveries, disputes.
      </EmptyState>
    )
  }
  return (
    <div className={clsx('scroll-area', className)}>
      {shown.map((event) => (
        <button
          key={event.id}
          type="button"
          onClick={() => onSelect?.(event)}
          className={clsx(
            'group flex w-full gap-3 border-b border-edge-soft/60 px-4 text-left transition-colors last:border-0 hover:bg-white/[0.025]',
            dense ? 'py-2' : 'py-3',
          )}
        >
          <div className="flex w-12 shrink-0 flex-col items-end gap-1 pt-0.5">
            <span className="num text-[10px] text-muted">D{event.day}</span>
            {currentDay !== undefined && (
              <span className="font-mono text-[9px] text-dim">{relativeDay(event.day, currentDay)}</span>
            )}
          </div>
          <div className="min-w-0 flex-1">
            <div className="mb-1 flex items-center gap-2">
              <span className={clsx('rounded border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider', eventCategoryTone(event.category))}>
                {event.category}
              </span>
              {event.importance >= 4 && (
                <span className="font-mono text-[9px] uppercase tracking-wider text-amber">major</span>
              )}
              {event.location_name && <span className="truncate text-[10px] text-dim">{event.location_name}</span>}
            </div>
            <div className="text-[12.5px] font-medium leading-snug text-fg group-hover:text-white">{event.title}</div>
            {!dense && <p className="mt-1 line-clamp-2 text-[11.5px] leading-relaxed text-muted">{event.description}</p>}
          </div>
        </button>
      ))}
    </div>
  )
}
