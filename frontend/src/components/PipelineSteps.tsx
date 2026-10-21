import { cn } from "@/lib/utils"
import { Check, Loader2, X, Circle } from "lucide-react"

type StepState = "done" | "active" | "fail" | "pending"

function StepIcon({ state }: { state: StepState }) {
  switch (state) {
    case "done":
      return <Check className="h-3.5 w-3.5" />
    case "active":
      return <Loader2 className="h-3.5 w-3.5 animate-spin" />
    case "fail":
      return <X className="h-3.5 w-3.5" />
    default:
      return <Circle className="h-3.5 w-3.5" />
  }
}

function stepClasses(state: StepState) {
  return cn(
    "flex items-center gap-1.5 rounded-md px-3 py-2 text-xs font-medium transition-colors",
    state === "done" && "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400",
    state === "active" && "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
    state === "fail" && "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
    state === "pending" && "text-muted-foreground"
  )
}

interface Props {
  steps: { label: string; state: StepState }[]
}

export function PipelineSteps({ steps }: Props) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
      {steps.map((step) => (
        <div key={step.label} className={stepClasses(step.state)}>
          <StepIcon state={step.state} />
          {step.label}
        </div>
      ))}
    </div>
  )
}
