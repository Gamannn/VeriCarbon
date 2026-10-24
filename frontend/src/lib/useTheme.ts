import { useState, useEffect } from "react"

type Theme = "light" | "dark"

function getInitial(): Theme {
  try {
    const stored = localStorage.getItem("vericarbon-theme") as Theme | null
    if (stored === "light" || stored === "dark") return stored
  } catch {}
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(getInitial)

  useEffect(() => {
    const root = document.documentElement
    root.classList.toggle("dark", theme === "dark")
    try { localStorage.setItem("vericarbon-theme", theme) } catch {}
  }, [theme])

  const toggle = () => setTheme((t) => (t === "dark" ? "light" : "dark"))

  return { theme, toggle }
}
