import type { Detection, Prediction, Alert } from '../types'

interface Props {
  detections: Detection[]
  predictions: Prediction[]
  alerts: Alert[]
}

export function StatsBar({ detections, predictions, alerts }: Props) {
  const flames = detections.filter((d) => d.fire_class === 'flame').length
  const smokes = detections.filter((d) => d.fire_class === 'smoke').length
  const emergencies = alerts.filter((a) => a.severity === 'emergency').length
  const warnings = alerts.filter((a) => a.severity === 'warning').length

  const stats = [
    { label: 'Detections', value: detections.length, accent: '#ff4500' },
    { label: 'Flame', value: flames, accent: '#ff4500' },
    { label: 'Smoke', value: smokes, accent: '#ffa500' },
    { label: 'Predictions', value: predictions.length, accent: '#ffcc00' },
    { label: 'Alerts', value: alerts.length, accent: '#ff6600' },
    { label: 'Emergency', value: emergencies, accent: '#ff0000' },
    { label: 'Warning', value: warnings, accent: '#ff6600' },
  ]

  return (
    <div className="stats-bar">
      {stats.map((s) => (
        <div key={s.label} className="stat-card">
          <span className="stat-card__value" style={{ color: s.accent }}>{s.value}</span>
          <span className="stat-card__label">{s.label}</span>
        </div>
      ))}
    </div>
  )
}
