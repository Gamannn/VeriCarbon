import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, RadialBarChart, RadialBar,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from "recharts"
import { Badge } from "@/components/ui/badge"
import { Activity } from "lucide-react"
import type { VerificationResult, DuplicateResult, OnchainResult, ProjectState } from "@/lib/types"

const GREEN = "#137a3f"
const GREEN_LIGHT = "#22c55e"
const AMBER = "#f59e0b"
const RED = "#ef4444"
const BLUE = "#3b82f6"

interface Props {
  verify: VerificationResult | null
  dup: DuplicateResult | null
  onchain: OnchainResult | null
  proj: ProjectState | null
}

function ConfidenceGauge({ bps }: { bps: number }) {
  const pct = bps / 100
  const color = pct >= 70 ? GREEN : pct >= 40 ? AMBER : RED
  const data = [{ name: "Confidence", value: pct, fill: color }]

  return (
    <div className="flex flex-col items-center">
      <ResponsiveContainer width={130} height={130}>
        <RadialBarChart
          cx="50%" cy="50%"
          innerRadius="68%" outerRadius="100%"
          startAngle={210} endAngle={-30}
          barSize={12}
          data={data}
        >
          <RadialBar background dataKey="value" cornerRadius={8} max={100} />
        </RadialBarChart>
      </ResponsiveContainer>
      <div className="relative -mt-[82px] text-center mb-4">
        <span className="text-base font-semibold" style={{ color }}>{pct.toFixed(1)}%</span>
        <p className="text-[9px] text-muted-foreground">Confidence</p>
      </div>
    </div>
  )
}

function OutcomePie({ verify }: { verify: VerificationResult }) {
  const conf = verify.confidence_bps / 100
  const data = [
    { name: "Confidence", value: conf },
    { name: "Remaining", value: 100 - conf },
  ]
  const outcomeColor =
    verify.outcome === "VERIFIED" ? GREEN
    : verify.outcome === "REJECT" ? RED
    : AMBER
  const colors = [outcomeColor, "#e5e7eb"]

  return (
    <div className="flex flex-col items-center">
      <ResponsiveContainer width={110} height={110}>
        <PieChart>
          <Pie
            data={data} cx="50%" cy="50%"
            innerRadius={35} outerRadius={50}
            paddingAngle={2} dataKey="value"
            startAngle={90} endAngle={-270}
            stroke="none"
          >
            {data.map((_, i) => <Cell key={i} fill={colors[i]} />)}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="relative -mt-[72px] text-center mb-4">
        <Badge variant={verify.outcome === "VERIFIED" ? "success" : verify.outcome === "REJECT" ? "danger" : "warning"} className="text-[10px] px-1.5 py-0.5">
          {verify.outcome}
        </Badge>
      </div>
    </div>
  )
}

function DuplicateRadar({ dup }: { dup: DuplicateResult }) {
  if (dup.matches.length === 0) return null
  const f = dup.matches[0].features
  const data = [
    { feature: "Spatial", value: +(f.polygon_overlap_ratio * 100).toFixed(0) },
    { feature: "Cells", value: +(f.cell_overlap_ratio * 100).toFixed(0) },
    { feature: "Name", value: +(f.name_similarity * 100).toFixed(0) },
    { feature: "Org", value: +(f.org_similarity * 100).toFixed(0) },
    { feature: "Area", value: +(f.area_similarity * 100).toFixed(0) },
    { feature: "Desc", value: +(f.description_similarity * 100).toFixed(0) },
  ]

  return (
    <ResponsiveContainer width="100%" height={180}>
      <RadarChart data={data} cx="50%" cy="50%" outerRadius="65%">
        <PolarGrid stroke="#e5e7eb" />
        <PolarAngleAxis dataKey="feature" fontSize={9} />
        <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
        <Radar dataKey="value" stroke={RED} fill={RED} fillOpacity={0.2} strokeWidth={2} />
        <Tooltip formatter={(v: number) => `${v}%`} />
      </RadarChart>
    </ResponsiveContainer>
  )
}

export function ResultsDashboard({ verify, dup, onchain, proj }: Props) {
  if (!verify && !dup && !onchain) return null

  const gas = onchain?.data?.tx?.gas_used ?? 0
  const cells = onchain?.data?.cell_count ?? 0
  const gasPerCell = cells > 0 ? Math.round(gas / cells) : 0

  const ndviData = verify ? [
    { name: "NDVI Mean", value: +(verify.ndvi_mean * 100).toFixed(1), fill: GREEN },
    { name: "Forest %", value: +(verify.ndvi_forest_fraction * 100).toFixed(1), fill: GREEN_LIGHT },
  ] : []

  const areaData = verify ? [
    { name: "Claimed", value: verify.claimed_area_ha, fill: BLUE },
    { name: "Vegetated", value: verify.estimated_vegetated_area_ha, fill: GREEN },
  ] : []

  const riskCounts = { HIGH: 0, MEDIUM: 0, LOW: 0 }
  dup?.matches.forEach((m) => riskCounts[m.risk_level]++)
  const riskData = [
    { name: "High", value: riskCounts.HIGH, fill: RED },
    { name: "Medium", value: riskCounts.MEDIUM, fill: AMBER },
    { name: "Low", value: riskCounts.LOW, fill: GREEN },
  ].filter((d) => d.value > 0)
  if (riskData.length === 0 && dup) riskData.push({ name: "Clear", value: 1, fill: GREEN })

  return (
    <div className="border-t pt-4">
      <div className="flex items-center gap-2 mb-3">
        <Activity className="h-4 w-4 text-primary" />
        <h2 className="text-sm font-semibold">Analytics Dashboard</h2>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {/* --- Verification outcome + confidence --- */}
        {verify && (
          <div className="rounded-lg border bg-card p-3">
            <p className="text-[11px] font-medium text-muted-foreground mb-1">Outcome</p>
            <div className="flex items-center justify-around">
              <OutcomePie verify={verify} />
              <ConfidenceGauge bps={verify.confidence_bps} />
            </div>
          </div>
        )}

        {/* --- NDVI bars --- */}
        {verify && (
          <div className="rounded-lg border bg-card p-3">
            <p className="text-[11px] font-medium text-muted-foreground mb-1">NDVI Vegetation</p>
            <ResponsiveContainer width="100%" height={130}>
              <BarChart data={ndviData} layout="vertical" margin={{ left: 0, right: 10, top: 2, bottom: 2 }}>
                <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} fontSize={10} />
                <YAxis type="category" dataKey="name" width={65} fontSize={10} />
                <Tooltip formatter={(v: number) => `${v}%`} />
                <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={20}>
                  {ndviData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* --- Area comparison --- */}
        {verify && (
          <div className="rounded-lg border bg-card p-3">
            <p className="text-[11px] font-medium text-muted-foreground mb-1">Area (hectares)</p>
            <ResponsiveContainer width="100%" height={130}>
              <BarChart data={areaData} margin={{ left: 0, right: 10, top: 2, bottom: 2 }}>
                <XAxis dataKey="name" fontSize={10} />
                <YAxis tickFormatter={(v) => `${v}`} fontSize={10} />
                <Tooltip formatter={(v: number) => `${v.toFixed(1)} ha`} />
                <Bar dataKey="value" radius={[6, 6, 0, 0]} barSize={30}>
                  {areaData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* --- Risk pie --- */}
        {dup && (
          <div className="rounded-lg border bg-card p-3">
            <p className="text-[11px] font-medium text-muted-foreground mb-1">
              Risk Distribution
            </p>
            <div className="flex items-center justify-center">
              <ResponsiveContainer width={130} height={130}>
                <PieChart>
                  <Pie data={riskData} cx="50%" cy="50%" outerRadius={52} dataKey="value" stroke="none" paddingAngle={2}>
                    {riskData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div className="text-[10px] space-y-1 ml-1">
                {riskData.map((d) => (
                  <div key={d.name} className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full inline-block" style={{ background: d.fill }} />
                    {d.name}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* --- Similarity radar (only when there's meaningful overlap) --- */}
        {dup && dup.matches.length > 0 && dup.highest_risk_level !== "LOW" && (
          <div className="rounded-lg border bg-card p-3">
            <p className="text-[11px] font-medium text-muted-foreground mb-1">
              Similarity vs {dup.matches[0].other_id}
            </p>
            <DuplicateRadar dup={dup} />
          </div>
        )}
        {dup && (dup.matches.length === 0 || dup.highest_risk_level === "LOW") && (
          <div className="rounded-lg border bg-card p-3 flex flex-col items-center justify-center">
            <p className="text-[11px] font-medium text-muted-foreground mb-2">Similarity</p>
            <div className="text-center py-4">
              <span className="text-2xl">&#10003;</span>
              <p className="text-xs text-muted-foreground mt-1">No significant overlap detected</p>
            </div>
          </div>
        )}

        {/* --- Gas & cells stat boxes --- */}
        {onchain?.data?.tx && (
          <div className="rounded-lg border bg-card p-3">
            <p className="text-[11px] font-medium text-muted-foreground mb-2">On-Chain Metrics</p>
            <div className="grid grid-cols-1 gap-2">
              <div className="bg-muted/50 rounded-md px-3 py-2 flex items-center justify-between">
                <span className="text-[10px] text-muted-foreground">H3 Cells</span>
                <span className="text-sm font-bold text-primary">{cells}</span>
              </div>
              <div className="bg-muted/50 rounded-md px-3 py-2 flex items-center justify-between">
                <span className="text-[10px] text-muted-foreground">Gas Used</span>
                <span className="text-sm font-bold text-blue-600">{gas.toLocaleString()}</span>
              </div>
              <div className="bg-muted/50 rounded-md px-3 py-2 flex items-center justify-between">
                <span className="text-[10px] text-muted-foreground">Gas / Cell</span>
                <span className="text-sm font-bold text-green-600">{gasPerCell.toLocaleString()}</span>
              </div>
            </div>
          </div>
        )}

        {/* --- Project status summary --- */}
        {proj && (
          <div className="rounded-lg border bg-card p-3">
            <p className="text-[11px] font-medium text-muted-foreground mb-2">Project Status</p>
            <div className="grid grid-cols-1 gap-2">
              <div className="bg-muted/50 rounded-md px-3 py-2 flex items-center justify-between">
                <span className="text-[10px] text-muted-foreground">State</span>
                <Badge variant={
                  proj.state === "Issued" || proj.state === "Verified" ? "success"
                  : proj.state === "Flagged" ? "warning"
                  : proj.state === "Rejected" ? "danger"
                  : "muted"
                }>{proj.state}</Badge>
              </div>
              <div className="bg-muted/50 rounded-md px-3 py-2 flex items-center justify-between">
                <span className="text-[10px] text-muted-foreground">Attestations</span>
                <span className="text-sm font-bold text-primary">{proj.attestation_count}/2</span>
              </div>
              {proj.verified_area_ha > 0 && (
                <div className="bg-muted/50 rounded-md px-3 py-2 flex items-center justify-between">
                  <span className="text-[10px] text-muted-foreground">Verified</span>
                  <span className="text-sm font-bold text-green-600">{proj.verified_area_ha} ha</span>
                </div>
              )}
              {proj.confidence_bps > 0 && (
                <div className="bg-muted/50 rounded-md px-3 py-2 flex items-center justify-between">
                  <span className="text-[10px] text-muted-foreground">Confidence</span>
                  <span className="text-sm font-bold text-blue-600">{(proj.confidence_bps / 100).toFixed(1)}%</span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
