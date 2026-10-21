import { useEffect, useRef, useCallback } from "react"
import L from "leaflet"
import "leaflet/dist/leaflet.css"
import type { LatLng, RegistryEntry } from "@/lib/types"

interface DrawableMapProps {
  polygon: LatLng[] | null
  onPolygonChange: (coords: LatLng[]) => void
  registryPolys: RegistryEntry[]
  submittedPolys: RegistryEntry[]
  drawingMode: "idle" | "drawing"
}

export function useDrawableMap({
  polygon,
  onPolygonChange,
  registryPolys,
  submittedPolys,
  drawingMode,
}: DrawableMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const workingLayerRef = useRef<L.Layer | null>(null)
  const workingVerticesRef = useRef<LatLng[]>([])
  const overlayLayersRef = useRef<L.Layer[]>([])
  const vertexMarkersRef = useRef<L.CircleMarker[]>([])

  useEffect(() => {
    if (mapRef.current || !containerRef.current) return
    const m = L.map(containerRef.current, { attributionControl: false }).setView([-3.0, -60.0], 10)
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18 }).addTo(m)
    L.control.attribution({ prefix: false }).addAttribution("&copy; OpenStreetMap").addTo(m)
    mapRef.current = m
  }, [])

  useEffect(() => {
    const m = mapRef.current
    if (!m) return
    overlayLayersRef.current.forEach((l) => m.removeLayer(l))
    overlayLayersRef.current = []
    const toLatLngs = (geo: { coordinates: number[][][] }) =>
      geo.coordinates[0].map(([lon, lat]) => [lat, lon] as L.LatLngTuple)

    ;(registryPolys || []).forEach((p) => {
      const layer = L.polygon(toLatLngs(p.polygon), {
        color: "#a05e00",
        weight: 2,
        fillOpacity: 0.12,
        dashArray: "6,4",
      })
        .addTo(m)
        .bindPopup(
          `<b>${p.name}</b><br/>${p.registry || "registry"} &middot; ${p.project_id}<br/><i>Existing registry entry</i>`
        )
      overlayLayersRef.current.push(layer)
    })
    ;(submittedPolys || []).forEach((p) => {
      const layer = L.polygon(toLatLngs(p.polygon), {
        color: "#137a3f",
        weight: 2,
        fillOpacity: 0.2,
      })
        .addTo(m)
        .bindPopup(`<b>${p.name}</b><br/>${p.project_id}<br/><i>Already submitted on-chain</i>`)
      overlayLayersRef.current.push(layer)
    })
  }, [registryPolys, submittedPolys])

  useEffect(() => {
    const m = mapRef.current
    if (!m) return
    if (workingLayerRef.current) m.removeLayer(workingLayerRef.current)
    workingLayerRef.current = null
    if (polygon && polygon.length >= 3) {
      workingLayerRef.current = L.polygon(polygon, {
        color: "#137a3f",
        weight: 3,
        fillOpacity: 0.3,
      }).addTo(m)
      try {
        m.fitBounds((workingLayerRef.current as L.Polygon).getBounds(), {
          padding: [30, 30],
          maxZoom: 13,
        })
      } catch (_) {}
    }
  }, [polygon])

  useEffect(() => {
    const m = mapRef.current
    if (!m) return
    const handleClick = (e: L.LeafletMouseEvent) => {
      if (drawingMode !== "drawing") return
      workingVerticesRef.current.push([e.latlng.lat, e.latlng.lng])
      if (workingLayerRef.current) m.removeLayer(workingLayerRef.current)
      if (workingVerticesRef.current.length >= 2) {
        workingLayerRef.current = L.polyline(workingVerticesRef.current, {
          color: "#137a3f",
          weight: 2,
          dashArray: "4,4",
        }).addTo(m)
      }
      const marker = L.circleMarker(e.latlng, {
        radius: 4,
        color: "#137a3f",
        fillOpacity: 1,
      }).addTo(m)
      vertexMarkersRef.current.push(marker)
    }
    const handleDbl = () => {
      if (drawingMode !== "drawing") return
      if (workingVerticesRef.current.length >= 3) {
        onPolygonChange(workingVerticesRef.current.slice())
        workingVerticesRef.current = []
        vertexMarkersRef.current.forEach((marker) => m.removeLayer(marker))
        vertexMarkersRef.current = []
      }
    }
    m.on("click", handleClick)
    m.on("dblclick", handleDbl)
    m.doubleClickZoom.disable()
    return () => {
      m.off("click", handleClick)
      m.off("dblclick", handleDbl)
      m.doubleClickZoom.enable()
    }
  }, [drawingMode, onPolygonChange])

  useEffect(() => {
    if (!polygon) {
      workingVerticesRef.current = []
      const m = mapRef.current
      if (m) {
        vertexMarkersRef.current.forEach((marker) => m.removeLayer(marker))
        vertexMarkersRef.current = []
      }
    }
  }, [polygon])

  const centerOn = useCallback((lat: number, lng: number, z = 11) => {
    mapRef.current?.setView([lat, lng], z)
  }, [])

  const mapElement = <div id="map" ref={containerRef} />

  return { mapElement, centerOn }
}
