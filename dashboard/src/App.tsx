import { usePipeline } from './hooks/usePipeline'
import { HealthBar } from './components/HealthBar'
import { StatsBar } from './components/StatsBar'
import { FireMap } from './components/FireMap'
import { AlertPanel } from './components/AlertPanel'
import { DetectionList } from './components/DetectionList'

export default function App() {
  const { detections, predictions, alerts, health, lastUpdated, error, wsConnected, refresh } = usePipeline()

  return (
    <div className="app">
      <HealthBar health={health} lastUpdated={lastUpdated} wsConnected={wsConnected} onRefresh={refresh} />
      {error && <div className="error-banner">⚠ {error}</div>}
      <StatsBar detections={detections} predictions={predictions} alerts={alerts} />
      <div className="main-grid">
        <div className="map-col">
          <FireMap detections={detections} predictions={predictions} />
        </div>
        <div className="side-col">
          <AlertPanel alerts={alerts} />
          <DetectionList detections={detections} />
        </div>
      </div>
    </div>
  )
}
