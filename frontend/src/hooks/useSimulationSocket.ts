import { useEffect } from 'react'
import { websocketUrl } from '../api'
import { useStore } from '../store'
import type { SocketPayload } from '../types'

export function useSimulationSocket() {
  const runId = useStore((state) => state.currentRunId)

  useEffect(() => {
    if (!runId) {
      useStore.getState().setSocketStatus('offline')
      return
    }
    let disposed = false
    let socket: WebSocket | null = null
    let retry: number | null = null
    let ping: number | null = null

    const connect = () => {
      if (disposed) return
      useStore.getState().setSocketStatus('connecting')
      try {
        socket = new WebSocket(websocketUrl(runId))
      } catch {
        useStore.getState().setSocketStatus('error')
        schedule()
        return
      }
      socket.onopen = () => {
        useStore.getState().setSocketStatus('live')
        ping = window.setInterval(() => {
          if (socket?.readyState === WebSocket.OPEN) socket.send('ping')
        }, 25000)
      }
      socket.onmessage = (message) => {
        try {
          const payload = JSON.parse(message.data) as SocketPayload
          useStore.getState().handleSocket(payload)
        } catch {
          // Ignore malformed frames rather than tearing down a live feed.
        }
      }
      socket.onclose = () => {
        if (ping) window.clearInterval(ping)
        ping = null
        if (!disposed) {
          useStore.getState().setSocketStatus('offline')
          schedule()
        }
      }
      socket.onerror = () => {
        useStore.getState().setSocketStatus('error')
      }
    }

    const schedule = () => {
      if (disposed) return
      retry = window.setTimeout(connect, 2500)
    }

    connect()

    return () => {
      disposed = true
      if (retry) window.clearTimeout(retry)
      if (ping) window.clearInterval(ping)
      socket?.close()
      useStore.getState().setSocketStatus('offline')
    }
  }, [runId])
}
