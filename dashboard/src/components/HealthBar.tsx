import type { ServiceHealth } from '../types'

interface Props {
  health: ServiceHealth[]
  lastUpdated: Date | null
  wsConnected: boolean
  onRefresh: () => void
}

export function HealthBar({ health, lastUpdated, wsConnected, onRefresh }: Props) {
  return (
    <header className="health-bar">
      <div className="health-bar__title">
        <span className="health-bar__flame">🔥</span>
        Wildfire Pipeline
      </div>
      <div className="health-bar__services">
        {health.map((s) => (
          <div key={s.name} className={`health-pill ${s.ok ? 'health-pill--ok' : 'health-pill--err'}`}>
            <span className="health-pill__dot" />
            {s.name}
          </div>
        ))}
        <div className={`health-pill ${wsConnected ? 'health-pill--ok' : 'health-pill--err'}`}>
          <span className="health-pill__dot" />
          ws
        </div>
      </div>
      <div className="health-bar__meta">
        {lastUpdated && (
          <span className="health-bar__ts">
            updated {lastUpdated.toLocaleTimeString()}
          </span>
        )}
        <button className="health-bar__refresh" onClick={onRefresh}>↻ refresh</button>
      </div>
    </header>
  )
}
