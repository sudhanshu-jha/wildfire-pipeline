import type { Detection } from '../types'

interface Props {
  detections: Detection[]
}

export function DetectionList({ detections }: Props) {
  const sorted = [...detections].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  )

  return (
    <section className="panel detection-panel">
      <h2 className="panel__title">Detections <span className="panel__count">{detections.length}</span></h2>
      {sorted.length === 0 ? (
        <p className="panel__empty">No detections</p>
      ) : (
        <ul className="detection-list">
          {sorted.map((d) => (
            <li key={d.detection_id} className="detection-item">
              <div className={`detection-item__badge detection-item__badge--${d.fire_class}`}>
                {d.fire_class}
              </div>
              <div className="detection-item__body">
                <span className="detection-item__drone">{d.drone_id}</span>
                <span className="detection-item__conf">{(d.confidence * 100).toFixed(0)}% conf</span>
              </div>
              <span className="detection-item__time">
                {new Date(d.timestamp).toLocaleTimeString()}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
