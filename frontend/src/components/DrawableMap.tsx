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

  const locMarkerRef = useRef<L.CircleMarker | null>(null)
  const locRingRef = useRef<L.CircleMarker | null>(null)

  useEffect(() => {
    if (mapRef.current || !containerRef.current) return
    const m = L.map(containerRef.current, { attributionControl: false }).setView([-3.0, -60.0], 10)
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18 }).addTo(m)
    L.control.attribution({ prefix: false }).addAttribution("&copy; OpenStreetMap").addTo(m)

    const LocateControl = L.Control.extend({
      onAdd() {
        const btn = L.DomUtil.create("button", "leaflet-locate-btn")
        btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="M2 12h2"/><path d="M20 12h2"/></svg>`
        btn.title = "Go to my location"
        btn.type = "button"
        btn.style.cssText =
          "width:34px;height:34px;background:#fff;border:2px solid rgba(0,0,0,.2);border-radius:4px;cursor:pointer;display:flex;align-items:center;justify-content:center;color:#333;"
        L.DomEvent.disableClickPropagation(btn)
        btn.addEventListener("click", () => {
          btn.style.color = "#137a3f"
          if (!navigator.geolocation) {
            alert("Geolocation is not supported by your browser.")
            btn.style.color = "#333"
            return
          }
          navigator.geolocation.getCurrentPosition(
            (pos) => {
              const { latitude, longitude, accuracy } = pos.coords
              m.setView([latitude, longitude], 14)
              if (locMarkerRef.current) m.removeLayer(locMarkerRef.current)
              if (locRingRef.current) m.removeLayer(locRingRef.current)
              locRingRef.current = L.circleMarker([latitude, longitude], {
                radius: Math.min(40, Math.max(12, accuracy / 10)),
                color: "#137a3f",
                fillColor: "#137a3f",
                fillOpacity: 0.1,
                weight: 1,
              }).addTo(m)
              locMarkerRef.current = L.circleMarker([latitude, longitude], {
                radius: 7,
                color: "#fff",
                fillColor: "#137a3f",
                fillOpacity: 1,
                weight: 2,
              })
                .addTo(m)
                .bindPopup(
                  `<b>Your location</b><br/>${latitude.toFixed(5)}, ${longitude.toFixed(5)}<br/><i>Accuracy: ~${accuracy.toFixed(0)} m</i>`
                )
              btn.style.color = "#137a3f"
            },
            (err) => {
              alert(`Location error: ${err.message}`)
              btn.style.color = "#333"
            },
            { enableHighAccuracy: true, timeout: 10000 }
          )
        })
        return btn
      },
    })
    new LocateControl({ position: "topright" }).addTo(m)

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
