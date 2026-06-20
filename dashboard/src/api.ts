import type { Detection, Prediction, Alert } from './types'

const INGESTION = '/api/ingestion'
const DETECTION = '/api/detection'
const PREDICTION = '/api/prediction'
const ALERTING = '/api/alerting'

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`${r.status} ${url}`)
  return r.json()
}

export async function fetchDetections(): Promise<Detection[]> {
  return get<Detection[]>(`${DETECTION}/detections`)
}

export async function fetchPredictions(): Promise<Prediction[]> {
  return get<Prediction[]>(`${PREDICTION}/predictions`)
}

export async function fetchAlerts(): Promise<Alert[]> {
  return get<Alert[]>(`${ALERTING}/alerts`)
}

export async function checkHealth(_name: string, base: string): Promise<boolean> {
  try {
    const r = await fetch(`${base}/health`, { signal: AbortSignal.timeout(2000) })
    return r.ok
  } catch {
    return false
  }
}

export const SERVICES = [
  { name: 'ingestion', url: INGESTION },
  { name: 'detection', url: DETECTION },
  { name: 'prediction', url: PREDICTION },
  { name: 'alerting', url: ALERTING },
]
