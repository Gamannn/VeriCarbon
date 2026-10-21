import { Badge } from "@/components/ui/badge"
import { Hash } from "@/components/Hash"
import type { VerificationResult } from "@/lib/types"

function badgeVariant(level: string) {
  switch (level) {
    case "VERIFIED": return "success" as const
    case "REJECT": return "danger" as const
    case "REQUIRES_REVIEW": return "warning" as const
    default: return "muted" as const
  }
}

interface Props {
  verify: VerificationResult | null
}

export function VerificationPanel({ verify }: Props) {
  if (!verify)
    return (
      <p className="text-sm text-muted-foreground">
        Press &ldquo;Submit for verification&rdquo; to run the pipeline.
      </p>
    )

  return (
    <div className="space-y-3 text-sm">
      <div className="flex items-center gap-2">
        <Badge variant={badgeVariant(verify.outcome)}>{verify.outcome}</Badge>
        <Badge variant="muted">mode: {verify.mode}</Badge>
      </div>

      <div className="grid grid-cols-2 gap-y-2 gap-x-4">
        <span className="text-muted-foreground">Vegetated area</span>
        <span>
          {verify.estimated_vegetated_area_ha.toFixed(1)} ha / {verify.claimed_area_ha} ha claimed
        </span>
        <span className="text-muted-foreground">Confidence</span>
        <span>{(verify.confidence_bps / 100).toFixed(2)}%</span>
        <span className="text-muted-foreground">NDVI mean</span>
        <span>
          {verify.ndvi_mean.toFixed(3)} ({(verify.ndvi_forest_fraction * 100).toFixed(0)}%
          forest-like)
        </span>
        <span className="text-muted-foreground">Scenes used</span>
        <span>{verify.scenes.length}</span>
      </div>

      <details className="pt-2 border-t">
        <summary className="cursor-pointer text-sm text-muted-foreground hover:text-foreground transition-colors">
          Provenance hashes (committed on-chain)
        </summary>
        <div className="pt-2 space-y-1 text-xs">
          <div>
            <span className="text-muted-foreground mr-2">dataset</span>
            <Hash value={verify.dataset_hash} />
          </div>
          <div>
            <span className="text-muted-foreground mr-2">model</span>
            <Hash value={verify.model_hash} />
          </div>
          <div>
            <span className="text-muted-foreground mr-2">result</span>
            <Hash value={verify.result_hash} />
          </div>
        </div>
      </details>

      {verify.notes.map((n, i) => (
        <p key={i} className="text-xs italic text-muted-foreground">
          {n}
        </p>
      ))}
    </div>
  )
}
