interface HashProps {
  value: string | null | undefined
  trim?: boolean
}

export function Hash({ value, trim = true }: HashProps) {
  if (!value) return <span className="font-mono text-xs text-muted-foreground">&mdash;</span>
  const v = value.startsWith("0x") ? value : "0x" + value
  const shown = trim && v.length > 24 ? v.slice(0, 10) + "…" + v.slice(-8) : v
  return (
    <span className="font-mono text-[11px] text-muted-foreground break-all" title={v}>
      {shown}
    </span>
  )
}
