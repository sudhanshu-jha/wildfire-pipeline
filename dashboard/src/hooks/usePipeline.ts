import { useState, useEffect, useCallback, useRef } from 'react'
import { fetchDetections, fetchPredictions, checkHealth, SERVICES } from '../api'
import type { Detection, Prediction, Alert, ServiceHealth } from '../types'

const POLL_MS = 5000
const WS_URL = `ws://${window.location.host}/api/alerting/ws/alerts`

export function usePipeline() {
  const [detections, setDetections] = useState<Detection[]>([])
  const [predictions, setPredictions] = useState<Prediction[]>([])
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [health, setHealth] = useState<ServiceHealth[]>([])
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [wsConnected, setWsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  // ── WebSocket for real-time alerts ─────────────────────────────────────────
  useEffect(() => {
    let retryTimer: ReturnType<typeof setTimeout>

    function connect() {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        setWsConnected(true)
        setError(null)
      }

      ws.onmessage = (evt) => {
        try {
          const alert: Alert = JSON.parse(evt.data)
          setAlerts((prev) => {
            const exists = prev.some((a) => a.alert_id === alert.alert_id)
            if (exists) return prev
            return [...prev.slice(-49), alert]
          })
          setLastUpdated(new Date())
        } catch {
          // malformed frame — ignore
        }
      }

      ws.onclose = () => {
        setWsConnected(false)
        // Reconnect after 3s
        retryTimer = setTimeout(connect, 3000)
      }

      ws.onerror = () => {
        ws.close()
      }
    }

    connect()
    return () => {
      clearTimeout(retryTimer)
      wsRef.current?.close()
    }
  }, [])

  // ── Poll detections + predictions + health ─────────────────────────────────
  const refresh = useCallback(async () => {
    try {
      const [d, p] = await Promise.all([fetchDetections(), fetchPredictions()])
      setDetections(d)
      setPredictions(p)
      setLastUpdated(new Date())
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'fetch failed')
    }

    const statuses = await Promise.all(
      SERVICES.map(async (s) => ({
        name: s.name,
        url: s.url,
        ok: await checkHealth(s.name, s.url),
      }))
    )
    setHealth(statuses)
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, POLL_MS)
    return () => clearInterval(id)
  }, [refresh])

  return { detections, predictions, alerts, health, lastUpdated, error, wsConnected, refresh }
}
