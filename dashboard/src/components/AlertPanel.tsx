import type { Alert } from '../types'

interface Props {
  alerts: Alert[]
}

const SEVERITY_CLASS: Record<string, string> = {
  emergency: 'alert-item--emergency',
  warning: 'alert-item--warning',
  watch: 'alert-item--watch',
}

const SEVERITY_ICON: Record<string, string> = {
  emergency: '🚨',
  warning: '⚠️',
  watch: '👁',
}

export function AlertPanel({ alerts }: Props) {
  const sorted = [...alerts].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  )

  return (
    <section className="panel alert-panel">
      <h2 className="panel__title">Alerts <span className="panel__count">{alerts.length}</span></h2>
      {sorted.length === 0 ? (
        <p className="panel__empty">No alerts</p>
      ) : (
        <ul className="alert-list">
          {sorted.map((a) => (
            <li key={a.alert_id} className={`alert-item ${SEVERITY_CLASS[a.severity] ?? 'alert-item--watch'}`}>
              <span className="alert-item__icon">{SEVERITY_ICON[a.severity] ?? '👁'}</span>
              <div className="alert-item__body">
                <p className="alert-item__msg">{a.message}</p>
                <p className="alert-item__meta">
                  {a.severity.toUpperCase()} · {new Date(a.timestamp).toLocaleTimeString()}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
