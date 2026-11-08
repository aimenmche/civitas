import { useEffect, useRef } from 'react'

/**
 * Runs an effect on the leading edge only, at most once per `minIntervalMs`.
 *
 * The websocket pushes state on every tick, so effects that depend on
 * `run.day` fire dozens of times a second while the sim is running. That
 * hammered the API with per-tick detail refetches and starved the main
 * thread. A leading-edge throttle keeps panels fresh without the storm.
 *
 * It deliberately has no trailing timer: a trailing timer is cancelled and
 * rescheduled by every tick, so during a continuous run it would never fire.
 */
export function useThrottledEffect(effect: () => void, deps: unknown[], minIntervalMs = 2500) {
  const lastRun = useRef(0)
  const effectRef = useRef(effect)
  effectRef.current = effect

  useEffect(() => {
    const now = Date.now()
    if (now - lastRun.current < minIntervalMs) return
    lastRun.current = now
    effectRef.current()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
}
