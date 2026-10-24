import type { GeoJSONPolygon, LatLng } from "./types"

export function polygonAreaHa(coords: LatLng[]): number {
  if (coords.length < 3) return 0
  const toRad = (d: number) => (d * Math.PI) / 180
  const R = 6371000
  const ring = [...coords, coords[0]]
  const meanLat = coords.reduce((s, c) => s + c[0], 0) / coords.length
  const cosLat = Math.cos(toRad(meanLat))
  let area = 0
  for (let i = 0; i < ring.length - 1; i++) {
    const x1 = toRad(ring[i][1]) * cosLat * R
    const y1 = toRad(ring[i][0]) * R
    const x2 = toRad(ring[i + 1][1]) * cosLat * R
    const y2 = toRad(ring[i + 1][0]) * R
    area += x1 * y2 - x2 * y1
  }
  return Math.abs(area / 2) / 10000
}

export function latLngsToGeoJSON(coords: LatLng[]): GeoJSONPolygon | null {
  if (!coords || coords.length < 3) return null
  const ring = coords.slice()
  const first = ring[0]
  const last = ring[ring.length - 1]
  if (first[0] !== last[0] || first[1] !== last[1]) ring.push([first[0], first[1]])
  const lonlat = ring.map(([lat, lng]) => [lng, lat])
  return { type: "Polygon", coordinates: [lonlat] }
}

export function geoJSONToLatLngs(geo: GeoJSONPolygon): LatLng[] | null {
  if (!geo || geo.type !== "Polygon") return null
  return geo.coordinates[0].slice(0, -1).map(([lng, lat]) => [lat, lng] as LatLng)
}
