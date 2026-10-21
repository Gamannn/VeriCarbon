import { Badge } from "@/components/ui/badge"
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert"
import { Hash } from "@/components/Hash"
import { ShieldAlert, ShieldCheck } from "lucide-react"
import type { OnchainResult, AttestResult, ProjectState, DuplicateResult } from "@/lib/types"

function stateVariant(state: string) {
  switch (state) {
    case "Issued": case "Verified": return "success" as const
    case "Pending": return "muted" as const
    case "Flagged": return "warning" as const
    case "Rejected": return "danger" as const
    default: return "muted" as const
  }
}

interface Props {
  onchain: OnchainResult | null
  attest: AttestResult | null
  proj: ProjectState | null
  dup: DuplicateResult | null
}

export function ChainPanel({ onchain, attest, proj, dup }: Props) {
  if (!onchain)
    return <p className="text-sm text-muted-foreground">Awaiting on-chain submission.</p>

  if (onchain.data?.error) {
    const rawErr = onchain.data.error
    const selMatch = rawErr.match(/0x5bfccfba([0-9a-f]{64})?([0-9a-f]{64})?/i)
    const cell = selMatch?.[1] ? "0x" + selMatch[1].replace(/^0+/, "") : null
    const owner = selMatch?.[2] ? "0x" + selMatch[2] : null

    return (
      <div className="space-y-3">
        <Alert variant="destructive">
          <ShieldAlert className="h-4 w-4" />
          <AlertTitle>REJECTED — Duplicate land claim</AlertTitle>
          <AlertDescription>
            The smart contract refused this submission because at least one H3 cell is already
            claimed by an active project. This block is enforced on-chain, independently of the
            project name or organization.
          </AlertDescription>
        </Alert>

        <div className="space-y-2 text-sm">
          <p className="font-semibold">Why it was rejected (from contract revert):</p>
          <div className="grid grid-cols-2 gap-y-1 text-xs">
            <span className="text-muted-foreground">Revert selector</span>
            <span className="font-mono">0x5bfccfba (CellAlreadyClaimed)</span>
            {cell && (
              <>
                <span className="text-muted-foreground">First conflicting H3 cell</span>
                <span className="font-mono">{cell}</span>
              </>
            )}
            {owner && (
              <>
                <span className="text-muted-foreground">Owned by project (hash)</span>
                <Hash value={owner} />
              </>
            )}
          </div>

          {dup?.matches && dup.matches.length > 0 && (
            <div className="mt-3">
              <p className="font-semibold text-sm mb-1">
                Off-chain evidence corroborating the rejection:
              </p>
              <ul className="text-xs text-muted-foreground list-disc list-inside space-y-0.5">
                {dup.matches.slice(0, 2).flatMap((m) =>
                  m.explanation.map((e, i) => (
                    <li key={m.other_id + "-" + i}>
                      vs {m.other_id}: {e}
                    </li>
                  ))
                )}
              </ul>
            </div>
          )}
        </div>

        <details>
          <summary className="cursor-pointer text-xs text-muted-foreground">Raw revert data</summary>
          <p className="font-mono text-[11px] text-muted-foreground break-all mt-1">{rawErr}</p>
        </details>
      </div>
    )
  }

  if (!onchain.ok && !onchain.data?.tx) {
    return (
      <div className="space-y-2 text-sm">
        <Badge variant="warning">Chain not configured</Badge>
        <p className="text-muted-foreground">
          {onchain.data?.detail ||
            "Set RPC_URL, CONTRACT_ADDRESS, BACKEND_PRIVATE_KEY in backend/.env."}
        </p>
      </div>
    )
  }

  const tx = onchain.data.tx!

  return (
    <div className="space-y-3 text-sm">
      {proj?.state === "Issued" && (
        <Alert variant="success">
          <ShieldCheck className="h-4 w-4" />
          <AlertTitle>APPROVED — Carbon claim issued</AlertTitle>
          <AlertDescription>
            Two validators attested the same verification result; the contract issued the credit.
          </AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-2 gap-y-2 gap-x-4">
        <span className="text-muted-foreground">Cells claimed on-chain</span>
        <span>{onchain.data.cell_count}</span>
        <span className="text-muted-foreground">Submit tx</span>
        <Hash value={tx.tx_hash} />
        <span className="text-muted-foreground">Submit gas used</span>
        <span>{tx.gas_used.toLocaleString()}</span>
        {attest && (
          <>
            <span className="text-muted-foreground">Attestation tx #1</span>
            <Hash value={attest.tx_hash} />
          </>
        )}
        {proj && (
          <>
            <span className="text-muted-foreground">On-chain state</span>
            <Badge variant={stateVariant(proj.state)}>{proj.state}</Badge>
            <span className="text-muted-foreground">Attestations</span>
            <span>{proj.attestation_count} of 2</span>
            {proj.verified_area_ha > 0 && (
              <>
                <span className="text-muted-foreground">Verified area</span>
                <span>{proj.verified_area_ha} ha</span>
                <span className="text-muted-foreground">Confidence</span>
                <span>{(proj.confidence_bps / 100).toFixed(2)}%</span>
              </>
            )}
          </>
        )}
      </div>
    </div>
  )
}
