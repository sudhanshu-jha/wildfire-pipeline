import { MapContainer, TileLayer, CircleMarker, Polygon, Tooltip } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import type { Detection, Prediction } from '../types'

interface Props {
  detections: Detection[]
  predictions: Prediction[]
}

const FIRE_CLASS_COLOR: Record<string, string> = {
  flame: '#ff4500',
  smoke: '#ffa500',
}

const SEVERITY_STROKE: Record<string, string> = {
  emergency: '#ff0000',
  warning: '#ff6600',
  watch: '#ffcc00',
}

export function FireMap({ detections, predictions }: Props) {
  const center: [number, number] = [30.0668, -5.0026]

  return (
    <MapContainer
      center={center}
      zoom={10}
      className="fire-map"
      attributionControl={false}
    >
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        attribution=""
      />

      {predictions.map((p) => {
        const positions = p.projected_perimeter.map(
          (pt): [number, number] => [pt.lat, pt.lon]
        )
        const score = p.risk_score ?? 0
        const stroke = score > 0.7 ? SEVERITY_STROKE.emergency
          : score > 0.5 ? SEVERITY_STROKE.warning
          : SEVERITY_STROKE.watch
        return (
          <Polygon
            key={p.prediction_id}
            positions={positions}
            pathOptions={{ color: stroke, fillColor: stroke, fillOpacity: 0.12, weight: 1.5 }}
          >
            <Tooltip sticky>
              Risk {(score * 100).toFixed(0)}% · {p.horizon_minutes ?? 60}min horizon
            </Tooltip>
          </Polygon>
        )
      })}

      {detections.map((d) => (
        <CircleMarker
          key={d.detection_id}
          center={[d.location.lat, d.location.lon]}
          radius={8}
          pathOptions={{
            color: FIRE_CLASS_COLOR[d.fire_class] ?? '#ff4500',
            fillColor: FIRE_CLASS_COLOR[d.fire_class] ?? '#ff4500',
            fillOpacity: 0.85,
            weight: 1,
          }}
        >
          <Tooltip>
            {d.drone_id} · {d.fire_class} · {(d.confidence * 100).toFixed(0)}%
            <br />
            {new Date(d.timestamp).toLocaleTimeString()}
          </Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  )
}
