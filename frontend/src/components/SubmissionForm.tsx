import { useState } from "react"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { MapPin, FileJson, Square, Zap } from "lucide-react"
import { geoJSONToLatLngs } from "@/lib/geo"
import { latLngsToGeoJSON } from "@/lib/geo"
import { TEMPLATES } from "@/lib/types"
import type { SubmissionForm as FormData, LatLng } from "@/lib/types"

interface SubmissionFormProps {
  form: FormData
  setForm: (f: FormData) => void
  polygon: LatLng[] | null
  setPolygon: (p: LatLng[] | null) => void
  drawingMode: "idle" | "drawing"
  setDrawingMode: (m: "idle" | "drawing") => void
  onLoadTemplate: (t: (typeof TEMPLATES)[number]) => void
}

export function SubmissionForm({
  form,
  setForm,
  polygon,
  setPolygon,
  drawingMode,
  setDrawingMode,
  onLoadTemplate,
}: SubmissionFormProps) {
  const [geoJsonText, setGeoJsonText] = useState("")
  const [bbox, setBbox] = useState({ n: "", s: "", e: "", w: "" })
  const [importError, setImportError] = useState("")

  function applyGeoJSON() {
    setImportError("")
    try {
      const g = JSON.parse(geoJsonText)
      const geo = g.type === "Feature" ? g.geometry : g
      if (geo.type !== "Polygon") throw new Error("Only Polygon geometry supported.")
      const coords = geoJSONToLatLngs(geo)
      if (!coords || coords.length < 3) throw new Error("Polygon has fewer than 3 corners.")
      setPolygon(coords)
    } catch (e) {
      setImportError((e as Error).message)
    }
  }

  function applyBbox() {
    setImportError("")
    const n = parseFloat(bbox.n),
      s = parseFloat(bbox.s),
      e = parseFloat(bbox.e),
      w = parseFloat(bbox.w)
    if ([n, s, e, w].some((x) => !isFinite(x))) {
      setImportError("All four values required.")
      return
    }
    if (s >= n || w >= e) {
      setImportError("Need south<north and west<east.")
      return
    }
    setPolygon([
      [s, w],
      [s, e],
      [n, e],
      [n, w],
    ])
  }

  const polyGeoJSON = latLngsToGeoJSON(polygon ?? [])
  const polyText = polyGeoJSON ? JSON.stringify(polyGeoJSON) : ""

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="project_id">Project ID</Label>
          <Input
            id="project_id"
            value={form.project_id}
            onChange={(e) => setForm({ ...form, project_id: e.target.value })}
            placeholder="e.g. my-pilot-2026-01"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="area">Claimed area (hectares)</Label>
          <Input
            id="area"
            type="number"
            min="0"
            step="0.1"
            value={form.claimed_area_ha}
            onChange={(e) => setForm({ ...form, claimed_area_ha: e.target.value })}
            placeholder="e.g. 500"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="name">Project name</Label>
          <Input
            id="name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="e.g. Amazonia Reforestation Pilot"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="org">Organization</Label>
          <Input
            id="org"
            value={form.organization}
            onChange={(e) => setForm({ ...form, organization: e.target.value })}
            placeholder="e.g. GreenForest Inc"
          />
        </div>
        <div className="sm:col-span-2 space-y-1.5">
          <Label htmlFor="desc">Short description</Label>
          <Input
            id="desc"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="One sentence — context for the restoration activity."
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label>Land boundary</Label>
        <BoundaryTabs
          drawingMode={drawingMode}
          setDrawingMode={setDrawingMode}
          polygon={polygon}
          setPolygon={setPolygon}
          geoJsonText={geoJsonText}
          setGeoJsonText={setGeoJsonText}
          applyGeoJSON={applyGeoJSON}
          polyText={polyText}
          bbox={bbox}
          setBbox={setBbox}
          applyBbox={applyBbox}
          onLoadTemplate={onLoadTemplate}
          importError={importError}
        />
      </div>
    </div>
  )
}

function BoundaryTabs({
  drawingMode,
  setDrawingMode,
  polygon,
  setPolygon,
  geoJsonText,
  setGeoJsonText,
  applyGeoJSON,
  polyText,
  bbox,
  setBbox,
  applyBbox,
  onLoadTemplate,
  importError,
}: {
  drawingMode: "idle" | "drawing"
  setDrawingMode: (m: "idle" | "drawing") => void
  polygon: LatLng[] | null
  setPolygon: (p: LatLng[] | null) => void
  geoJsonText: string
  setGeoJsonText: (s: string) => void
  applyGeoJSON: () => void
  polyText: string
  bbox: { n: string; s: string; e: string; w: string }
  setBbox: (b: { n: string; s: string; e: string; w: string }) => void
  applyBbox: () => void
  onLoadTemplate: (t: (typeof TEMPLATES)[number]) => void
  importError: string
}) {
  const [tab, setTab] = useState("draw")

  return (
    <div>
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="draw">
            <MapPin className="h-3.5 w-3.5 mr-1.5" />
            Draw
          </TabsTrigger>
          <TabsTrigger value="geojson">
            <FileJson className="h-3.5 w-3.5 mr-1.5" />
            GeoJSON
          </TabsTrigger>
          <TabsTrigger value="bbox">
            <Square className="h-3.5 w-3.5 mr-1.5" />
            Bbox
          </TabsTrigger>
          <TabsTrigger value="template">
            <Zap className="h-3.5 w-3.5 mr-1.5" />
            Examples
          </TabsTrigger>
        </TabsList>

        <TabsContent value="draw">
          <div className="text-sm text-muted-foreground">
            {drawingMode === "drawing" ? (
              <div className="flex items-center gap-2 flex-wrap">
                <span>Click on the map to drop corners. Double-click to finish (min 3).</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setDrawingMode("idle")
                    setPolygon(null)
                  }}
                >
                  Cancel
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-2 flex-wrap">
                <Button
                  size="sm"
                  onClick={() => {
                    setPolygon(null)
                    setDrawingMode("drawing")
                  }}
                >
                  Start drawing
                </Button>
                {polygon && (
                  <Button variant="outline" size="sm" onClick={() => setPolygon(null)}>
                    Clear
                  </Button>
                )}
                <span className="text-xs">{polygon ? `${polygon.length} corners` : "No polygon yet"}</span>
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="geojson">
          <div className="space-y-2">
            <Textarea
              rows={4}
              value={geoJsonText}
              onChange={(e) => setGeoJsonText(e.target.value)}
              placeholder='{"type":"Polygon","coordinates":[[[-60.02,-3.01],...]]}'
            />
            <div className="flex items-center gap-2">
              <Button size="sm" onClick={applyGeoJSON}>
                Apply GeoJSON
              </Button>
              {polyText && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigator.clipboard?.writeText(polyText)}
                >
                  Copy current polygon
                </Button>
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="bbox">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <div className="space-y-1">
              <Label>North lat</Label>
              <Input
                value={bbox.n}
                onChange={(e) => setBbox({ ...bbox, n: e.target.value })}
                placeholder="-2.98"
              />
            </div>
            <div className="space-y-1">
              <Label>South lat</Label>
              <Input
                value={bbox.s}
                onChange={(e) => setBbox({ ...bbox, s: e.target.value })}
                placeholder="-3.01"
              />
            </div>
            <div className="space-y-1">
              <Label>East lon</Label>
              <Input
                value={bbox.e}
                onChange={(e) => setBbox({ ...bbox, e: e.target.value })}
                placeholder="-59.98"
              />
            </div>
            <div className="space-y-1">
              <Label>West lon</Label>
              <Input
                value={bbox.w}
                onChange={(e) => setBbox({ ...bbox, w: e.target.value })}
                placeholder="-60.02"
              />
            </div>
            <div className="sm:col-span-4">
              <Button size="sm" onClick={applyBbox}>
                Make rectangle
              </Button>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="template">
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">
              Load a ready-made polygon to quickly see each verification outcome.
            </p>
            {TEMPLATES.map((t) => (
              <Button
                key={t.id}
                variant="outline"
                className="w-full justify-start text-left h-auto py-2"
                onClick={() => onLoadTemplate(t)}
              >
                <div>
                  <div className="font-medium text-sm">{t.name}</div>
                  <div className="text-xs text-muted-foreground">{t.description}</div>
                </div>
              </Button>
            ))}
          </div>
        </TabsContent>
      </Tabs>

      {importError && <p className="text-xs text-destructive mt-2">{importError}</p>}
    </div>
  )
}
