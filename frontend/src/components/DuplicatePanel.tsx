import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import type { DuplicateResult } from "@/lib/types"

function riskVariant(level: string) {
  switch (level) {
    case "HIGH": return "danger" as const
    case "MEDIUM": return "warning" as const
    case "LOW": return "success" as const
    default: return "muted" as const
  }
}

function barColor(value: number): string {
  if (value > 0.5) return "bg-red-500"
  if (value > 0.1) return "bg-amber-500"
  return "bg-primary"
}

function FeatureBar({ label, value, format }: { label: string; value: number; format?: (v: number) => string }) {
  const pct = Math.max(0, Math.min(1, value || 0)) * 100
  const fmt = format || ((v: number) => (v * 100).toFixed(0) + "%")
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-semibold">{fmt(value)}</span>
      </div>
      <Progress value={pct} indicatorClassName={barColor(value)} />
    </div>
  )
}

interface Props {
  dup: DuplicateResult | null
}

export function DuplicatePanel({ dup }: Props) {
  if (!dup)
    return <p className="text-sm text-muted-foreground">Awaiting duplicate scan.</p>

  if (!dup.matches || dup.matches.length === 0) {
    return (
      <div className="space-y-2 text-sm">
        <Badge variant="success">No matches</Badge>
        <p className="text-muted-foreground">
          No registry entries within 50 km blocking radius. {dup.cell_count} H3 cells will be
          checked on-chain for duplicates.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3 text-sm">
      <Badge variant={riskVariant(dup.highest_risk_level)}>
        Highest risk: {dup.highest_risk_level}
      </Badge>

      <div className="space-y-3">
        {dup.matches.map((m) => (
          <div key={m.other_id} className="rounded-lg border bg-muted/30 p-3 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-semibold">{m.other_id}</div>
                <div className="text-xs text-muted-foreground">
                  {m.other_registry} &middot; {m.other_registry_ref}
                </div>
              </div>
              <Badge variant={riskVariant(m.risk_level)}>
                risk {m.risk_score.toFixed(2)} &middot; {m.risk_level}
              </Badge>
            </div>

            <div className="space-y-2">
              <FeatureBar label="H3 cell overlap" value={m.features.cell_overlap_ratio} />
              <FeatureBar label="Polygon overlap" value={m.features.polygon_overlap_ratio} />
              <FeatureBar label="Polygon IoU" value={m.features.polygon_iou} />
              <FeatureBar label="Name similarity" value={m.features.name_similarity} />
              <FeatureBar label="Organization similarity" value={m.features.org_similarity} />
              <FeatureBar label="Description similarity" value={m.features.description_similarity} />
              <FeatureBar label="Area ratio (min/max)" value={m.features.area_similarity} />
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Centroid distance</span>
                <span className="font-semibold">
                  {m.features.centroid_distance_m < 1000
                    ? `${m.features.centroid_distance_m.toFixed(0)} m`
                    : `${(m.features.centroid_distance_m / 1000).toFixed(2)} km`}
                </span>
              </div>
            </div>

            {m.explanation?.length > 0 && (
              <ul className="text-xs text-muted-foreground list-disc list-inside space-y-0.5">
                {m.explanation.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
