export interface GeoPoint {
  lat: number
  lon: number
}

export interface Detection {
  detection_id: string
  drone_id: string
  location: GeoPoint
  timestamp: string
  confidence: number
  fire_class: 'smoke' | 'flame' | string
  bounding_box: [number, number, number, number]
}

export interface Prediction {
  prediction_id: string
  based_on_detection_id: string
  origin: GeoPoint
  timestamp: string
  projected_perimeter: GeoPoint[]
  risk_score: number
  horizon_minutes: number
}

export interface Alert {
  alert_id: string
  based_on_prediction_id: string
  location: GeoPoint
  severity: 'watch' | 'warning' | 'emergency' | string
  message: string
  timestamp: string
}

export interface ServiceHealth {
  name: string
  url: string
  ok: boolean
}
