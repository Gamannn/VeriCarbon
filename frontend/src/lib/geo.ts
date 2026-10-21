import type { GeoJSONPolygon, LatLng } from "./types"

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
