import { useState, useEffect, useCallback } from "react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { useDrawableMap } from "@/components/DrawableMap"
import { SubmissionForm } from "@/components/SubmissionForm"
import { VerificationPanel } from "@/components/VerificationPanel"
import { DuplicatePanel } from "@/components/DuplicatePanel"
import { ChainPanel } from "@/components/ChainPanel"
import { PipelineSteps } from "@/components/PipelineSteps"
import { ResultsDashboard } from "@/components/ResultsDashboard"
import { SubmissionHistory, type HistoryEntry } from "@/components/SubmissionHistory"
import { useTheme } from "@/lib/useTheme"
import { latLngsToGeoJSON, polygonAreaHa } from "@/lib/geo"
import { postJson, getJson } from "@/lib/api"
import { Leaf, Plus, Satellite, Search, Link, CheckCircle2, Terminal, Sun, Moon } from "lucide-react"
import type {
  SubmissionForm as FormData,
  LatLng,
  VerificationResult,
  DuplicateResult,
  OnchainResult,
  AttestResult,
  ProjectState,
  ChainStatus,
  RegistryEntry,
} from "@/lib/types"
import { TEMPLATES } from "@/lib/types"

const DEFAULT_FORM: FormData = {
  project_id: "",
  name: "",
  organization: "",
  description: "",
  claimed_area_ha: "",
}

function loadHistory(): HistoryEntry[] {
  try {
    return JSON.parse(localStorage.getItem("vericarbon-history") || "[]")
  } catch { return [] }
}
function saveHistory(h: HistoryEntry[]) {
  try { localStorage.setItem("vericarbon-history", JSON.stringify(h.slice(0, 20))) } catch {}
}

export default function App() {
  const { theme, toggle: toggleTheme } = useTheme()
  const [form, setForm] = useState(DEFAULT_FORM)
  const [polygon, setPolygon] = useState<LatLng[] | null>(null)
  const [drawingMode, setDrawingMode] = useState<"idle" | "drawing">("idle")

  const [registry, setRegistry] = useState<RegistryEntry[]>([])
  const [submitted, setSubmitted] = useState<RegistryEntry[]>([])
  const [chainStatus, setChainStatus] = useState<ChainStatus | null>(null)

  const [verify, setVerify] = useState<VerificationResult | null>(null)
  const [dup, setDup] = useState<DuplicateResult | null>(null)
  const [onchain, setOnchain] = useState<OnchainResult | null>(null)
  const [attest, setAttest] = useState<AttestResult | null>(null)
  const [proj, setProj] = useState<ProjectState | null>(null)
  const [log, setLog] = useState<string[]>([])
  const [running, setRunning] = useState(false)
  const [autoFlow, setAutoFlow] = useState(true)
  const [history, setHistory] = useState<HistoryEntry[]>(loadHistory)

  const onPolygonChange = useCallback((c: LatLng[]) => {
    setPolygon(c)
    setDrawingMode("idle")
  }, [])

  const { mapElement, centerOn } = useDrawableMap({
    polygon,
    onPolygonChange,
    registryPolys: registry,
    submittedPolys: submitted,
    drawingMode,
  })

  useEffect(() => {
    reloadLists()
    getJson<ChainStatus>("/chain/status")
      .then((r) => setChainStatus(r.data))
      .catch(() => {})
  }, [])

  function reloadLists() {
    getJson<{ projects: RegistryEntry[] }>("/registry/projects").then((r) =>
      setRegistry(r.data?.projects || [])
    )
    getJson<{ projects: RegistryEntry[] }>("/onchain/submitted").then((r) =>
      setSubmitted(r.data?.projects || [])
    )
  }

  function resetResults() {
    setVerify(null)
    setDup(null)
    setOnchain(null)
    setAttest(null)
    setProj(null)
    setLog([])
  }

  function onLoadTemplate(t: (typeof TEMPLATES)[number]) {
    const latlngs = [...t.poly] as LatLng[]
    setPolygon(latlngs)
    setForm({
      project_id: `demo-${t.id}-${Date.now().toString(36)}`,
      name: t.name,
      organization: t.org,
      description: t.desc,
      claimed_area_ha: t.area,
    })
    const latSum = latlngs.reduce((s, p) => s + p[0], 0)
    const lngSum = latlngs.reduce((s, p) => s + p[1], 0)
    centerOn(latSum / latlngs.length, lngSum / latlngs.length, 11)
  }

  function validate(): string | null {
    if (!form.project_id.trim()) return "Project ID is required."
    if (!form.name.trim()) return "Project name is required."
    if (!form.claimed_area_ha || parseFloat(form.claimed_area_ha) <= 0)
      return "Claimed area must be > 0."
    if (!polygon || polygon.length < 3)
      return "Draw or paste a polygon with at least 3 corners."
    return null
  }

  function addHistory(entry: HistoryEntry) {
    setHistory((prev) => {
      const next = [entry, ...prev].slice(0, 20)
      saveHistory(next)
      return next
    })
  }

  async function runPipeline() {
    const err = validate()
    if (err) {
      alert(err)
      return
    }

    const drawnArea = polygonAreaHa(polygon!)
    const claimed = parseFloat(form.claimed_area_ha)
    if (claimed > 0 && drawnArea > 0 && claimed > drawnArea * 2) {
      const proceed = window.confirm(
        `Area mismatch: you claimed ${claimed.toFixed(1)} ha but the drawn polygon covers only ~${drawnArea.toFixed(1)} ha.\n\n` +
        `The claimed area is ${(claimed / drawnArea).toFixed(1)}x larger than the selected region.\n\n` +
        `Press OK to submit anyway, or Cancel to go back and correct it.`
      )
      if (!proceed) return
    }

    setRunning(true)
    resetResults()
    const body = {
      project_id: form.project_id.trim(),
      name: form.name.trim(),
      organization: form.organization.trim(),
      description: form.description.trim(),
      polygon: latLngsToGeoJSON(polygon!),
      claimed_area_ha: parseFloat(form.claimed_area_ha),
      registry_refs: [],
    }

    let vOutcome: VerificationResult["outcome"] | null = null
    let dRisk: DuplicateResult["highest_risk_level"] | null = null
    let chainResult: HistoryEntry["chainResult"] = "skipped"
    let txHash: string | null = null
    let confidencePct: number | null = null
    let cellCount: number | null = null
    let finalState: string | null = null

    try {
      setLog((l) => [...l, "→ Running satellite verification…"])
      const v = await postJson<VerificationResult>("/verify", body)
      if (!v.ok)
        throw new Error(
          (v.data as unknown as { detail?: string }).detail || `verify ${v.status}`
        )
      setVerify(v.data)
      vOutcome = v.data.outcome
      confidencePct = v.data.confidence_bps / 100
      setLog((l) => [
        ...l,
        `✓ Verification: ${v.data.outcome} @ ${(v.data.confidence_bps / 100).toFixed(1)}% (${v.data.mode})`,
      ])

      setLog((l) => [...l, "→ Checking cross-registry duplicates…"])
      const d = await postJson<DuplicateResult>("/duplicate-check", body)
      if (!d.ok)
        throw new Error(
          (d.data as unknown as { detail?: string }).detail || `duplicate-check ${d.status}`
        )
      setDup(d.data)
      dRisk = d.data.highest_risk_level
      setLog((l) => [
        ...l,
        `✓ Duplicate scan: highest ${d.data.highest_risk_level} across ${d.data.matches.length} match(es)`,
      ])

      setLog((l) => [...l, "→ Submitting to smart contract…"])
      const sub = await postJson<OnchainResult["data"]>("/onchain/submit", body)
      const onchainResult: OnchainResult = { ok: sub.ok, data: sub.data }
      setOnchain(onchainResult)
      cellCount = sub.data?.cell_count ?? null
      if (!sub.ok || sub.data?.error) {
        const errMsg = sub.data?.error || sub.data?.detail || ""
        chainResult = typeof errMsg === "string" && errMsg.includes("0x5bfccfba") ? "rejected" : "failed"
        setLog((l) => [
          ...l,
          `✗ Submit blocked: ${sub.data?.error ? "contract reverted" : sub.data?.detail || "chain error"}`,
        ])
        setRunning(false)
        reloadLists()
        return
      }
      chainResult = "submitted"
      txHash = sub.data.tx!.tx_hash
      setLog((l) => [
        ...l,
        `✓ On-chain submit tx 0x${sub.data.tx!.tx_hash.slice(0, 16)}… (${sub.data.cell_count} cells)`,
      ])

      if (autoFlow && v.data.outcome !== "REJECT") {
        setLog((l) => [...l, "→ Posting validator attestation…"])
        const a = await postJson<AttestResult>("/onchain/attest", body)
        if (a.ok) {
          setAttest(a.data)
          setLog((l) => [
            ...l,
            `✓ Attestation #1 tx 0x${a.data.tx_hash.slice(0, 16)}… (second validator required)`,
          ])
        } else {
          setLog((l) => [
            ...l,
            `✗ Attest failed: ${(a.data as unknown as { detail?: string })?.detail}`,
          ])
        }
      }

      const p = await getJson<ProjectState>(
        `/onchain/project/${encodeURIComponent(body.project_id)}`
      )
      if (p.ok) {
        setProj(p.data)
        finalState = p.data.state
        setLog((l) => [...l, `✓ On-chain state: ${p.data.state}`])
      }
      reloadLists()
    } catch (e) {
      setLog((l) => [...l, `✗ ${(e as Error).message}`])
    } finally {
      setRunning(false)
      addHistory({
        id: `${body.project_id}-${Date.now()}`,
        projectId: body.project_id,
        name: body.name,
        organization: body.organization,
        timestamp: Date.now(),
        outcome: vOutcome,
        riskLevel: dRisk,
        chainResult,
        txHash,
        confidencePct,
        cellCount,
        state: finalState,
      })
    }
  }

  function newSubmission() {
    resetResults()
    setForm(DEFAULT_FORM)
    setPolygon(null)
    setDrawingMode("idle")
  }

  type StepState = "done" | "active" | "fail" | "pending"
  const steps: { label: string; state: StepState }[] = [
    { label: "Verify", state: verify ? "done" : running ? "active" : "pending" },
    { label: "Dup scan", state: dup ? "done" : running && verify ? "active" : "pending" },
    {
      label: "On-chain",
      state: onchain?.data?.tx
        ? "done"
        : onchain?.data?.error
          ? "fail"
          : running && dup
            ? "active"
            : "pending",
    },
    {
      label: "Attest",
      state: attest ? "done" : running && onchain?.data?.tx ? "active" : "pending",
    },
    {
      label: "State read",
      state: proj ? "done" : running && (attest || onchain?.data?.tx) ? "active" : "pending",
    },
  ]

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="max-w-7xl mx-auto flex items-center justify-between px-4 sm:px-6 h-16">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-primary text-primary-foreground">
              <Leaf className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-lg font-bold leading-tight">VeriCarbon</h1>
              <p className="text-[11px] text-muted-foreground leading-tight">
                Satellite-verified carbon credits with on-chain duplicate prevention
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {chainStatus && (
              <Badge variant={chainStatus.configured ? "success" : "muted"}>
                {chainStatus.configured ? "Sepolia connected" : "chain not configured"}
              </Badge>
            )}
            <Button variant="ghost" size="sm" onClick={toggleTheme} className="h-9 w-9 p-0">
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <Button variant="outline" size="sm" onClick={newSubmission}>
              <Plus className="h-4 w-4 mr-1.5" />
              New submission
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-4">
        <div className="grid gap-3 lg:grid-cols-2 items-start">
          <div className="space-y-3 lg:sticky lg:top-[4.5rem]">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Satellite className="h-4 w-4 text-primary" />
                  1 &middot; Land boundary
                </CardTitle>
              </CardHeader>
              <CardContent>
                {mapElement}
                <div className="mt-3 flex items-center gap-4 flex-wrap text-xs text-muted-foreground">
                  <span className="flex items-center gap-1.5">
                    <span className="inline-block w-2.5 h-2.5 rounded-sm bg-primary" />
                    Your submission
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="inline-block w-2.5 h-2.5 rounded-sm bg-primary/30" />
                    Already on-chain
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="inline-block w-2.5 h-2.5 rounded-sm bg-amber-500/40" />
                    Existing registry (synthetic)
                  </span>
                </div>
              </CardContent>
            </Card>

            <Card className="overflow-hidden">
              <CardHeader className="pb-3">
                <CardTitle className="text-base">2 &middot; Project details</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <SubmissionForm
                  form={form}
                  setForm={setForm}
                  polygon={polygon}
                  setPolygon={setPolygon}
                  drawingMode={drawingMode}
                  setDrawingMode={setDrawingMode}
                  onLoadTemplate={onLoadTemplate}
                />
                <div className="flex items-center gap-3 flex-wrap pt-4 border-t">
                  <Button disabled={running} onClick={runPipeline}>
                    {running ? "Running…" : "Submit for verification"}
                  </Button>
                  <label className="text-xs flex items-center gap-2 text-muted-foreground cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={autoFlow}
                      onChange={(e) => setAutoFlow(e.target.checked)}
                      className="rounded"
                    />
                    Auto-post first attestation after submit
                  </label>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-3">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">3 &middot; Pipeline progress</CardTitle>
              </CardHeader>
              <CardContent>
                <PipelineSteps steps={steps} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Search className="h-4 w-4 text-primary" />
                    Satellite verification
                  </CardTitle>
                  {verify && (
                    <Badge
                      variant={
                        verify.outcome === "VERIFIED"
                          ? "success"
                          : verify.outcome === "REJECT"
                            ? "danger"
                            : "warning"
                      }
                    >
                      {verify.outcome}
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <VerificationPanel verify={verify} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <CheckCircle2 className="h-4 w-4 text-primary" />
                    Cross-registry duplicate check
                  </CardTitle>
                  {dup && (
                    <Badge
                      variant={
                        dup.highest_risk_level === "HIGH"
                          ? "danger"
                          : dup.highest_risk_level === "MEDIUM"
                            ? "warning"
                            : "success"
                      }
                    >
                      {dup.highest_risk_level}
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <DuplicatePanel dup={dup} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Link className="h-4 w-4 text-primary" />
                    Blockchain decision
                  </CardTitle>
                  {proj && (
                    <Badge
                      variant={
                        proj.state === "Issued" || proj.state === "Verified"
                          ? "success"
                          : proj.state === "Flagged"
                            ? "warning"
                            : proj.state === "Rejected"
                              ? "danger"
                              : "muted"
                      }
                    >
                      {proj.state}
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <ChainPanel onchain={onchain} attest={attest} proj={proj} dup={dup} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Terminal className="h-4 w-4 text-primary" />
                  Pipeline log
                </CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="text-xs whitespace-pre-wrap text-muted-foreground font-mono bg-muted/50 rounded-md p-3 max-h-48 overflow-auto">
                  {log.length === 0
                    ? "Nothing run yet. Fill in the form, draw a polygon, and press Submit."
                    : log.join("\n")}
                </pre>
              </CardContent>
            </Card>

            <SubmissionHistory
              history={history}
              onClear={() => { setHistory([]); saveHistory([]) }}
            />
          </div>
        </div>

        <ResultsDashboard verify={verify} dup={dup} onchain={onchain} proj={proj} />

        <footer className="mt-4 pb-4 text-xs text-muted-foreground border-t pt-4">
          <p>
            Satellite results labeled{" "}
            <code className="bg-muted px-1 py-0.5 rounded text-[11px]">synthetic</code> are
            deterministic demo stand-ins, not real observations. Registry entries shown on the map
            are a synthetic corpus &mdash; no claim about any real-world organization.
          </p>
        </footer>
      </main>
    </div>
  )
}
