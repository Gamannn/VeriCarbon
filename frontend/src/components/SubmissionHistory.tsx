import { Badge } from "@/components/ui/badge"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Hash } from "@/components/Hash"
import { Clock, ChevronDown, ChevronUp, Trash2 } from "lucide-react"
import { useState } from "react"

export interface HistoryEntry {
  id: string
  projectId: string
  name: string
  organization: string
  timestamp: number
  outcome: "VERIFIED" | "REQUIRES_REVIEW" | "REJECT" | null
  riskLevel: "LOW" | "MEDIUM" | "HIGH" | null
  chainResult: "submitted" | "rejected" | "failed" | "skipped"
  txHash: string | null
  confidencePct: number | null
  cellCount: number | null
  state: string | null
}

interface Props {
  history: HistoryEntry[]
  onClear: () => void
}

function outcomeVariant(o: string | null) {
  if (o === "VERIFIED") return "success" as const
  if (o === "REJECT") return "danger" as const
  if (o === "REQUIRES_REVIEW") return "warning" as const
  return "muted" as const
}

function chainVariant(c: string) {
  if (c === "submitted") return "success" as const
  if (c === "rejected") return "danger" as const
  if (c === "failed") return "warning" as const
  return "muted" as const
}

function timeAgo(ts: number) {
  const diff = Date.now() - ts
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  return `${hrs}h ${mins % 60}m ago`
}

export function SubmissionHistory({ history, onClear }: Props) {
  const [expanded, setExpanded] = useState(true)

  if (history.length === 0) return null

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle
            className="flex items-center gap-2 text-base cursor-pointer select-none"
            onClick={() => setExpanded((e) => !e)}
          >
            <Clock className="h-4 w-4 text-primary" />
            Recent Submissions
            <Badge variant="muted" className="ml-1 text-[10px]">{history.length}</Badge>
            {expanded
              ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
              : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
            }
          </CardTitle>
          <Button variant="ghost" size="sm" onClick={onClear} className="text-muted-foreground h-7 px-2">
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </CardHeader>
      {expanded && (
        <CardContent className="pt-0">
          <div className="divide-y">
            {history.map((entry) => (
              <div key={entry.id} className="py-2.5 first:pt-0 last:pb-0">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium truncate">{entry.name}</span>
                      <span className="text-[10px] text-muted-foreground">{timeAgo(entry.timestamp)}</span>
                    </div>
                    <div className="flex items-center gap-1.5 mt-1 text-xs text-muted-foreground">
                      <span className="truncate">{entry.projectId}</span>
                      {entry.organization && (
                        <>
                          <span>&middot;</span>
                          <span className="truncate">{entry.organization}</span>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    {entry.outcome && <Badge variant={outcomeVariant(entry.outcome)}>{entry.outcome}</Badge>}
                    {entry.riskLevel && (
                      <Badge variant={outcomeVariant(entry.riskLevel === "HIGH" ? "REJECT" : entry.riskLevel === "MEDIUM" ? "REQUIRES_REVIEW" : "VERIFIED")}>
                        {entry.riskLevel}
                      </Badge>
                    )}
                    <Badge variant={chainVariant(entry.chainResult)}>
                      {entry.chainResult === "submitted" ? "On-chain" : entry.chainResult}
                    </Badge>
                  </div>
                </div>
                {(entry.txHash || entry.confidencePct !== null || entry.cellCount !== null) && (
                  <div className="flex items-center gap-3 mt-1.5 text-[10px] text-muted-foreground">
                    {entry.confidencePct !== null && <span>Confidence: {entry.confidencePct.toFixed(1)}%</span>}
                    {entry.cellCount !== null && <span>Cells: {entry.cellCount}</span>}
                    {entry.txHash && (
                      <span className="flex items-center gap-1">
                        Tx: <Hash value={entry.txHash} />
                      </span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      )}
    </Card>
  )
}
