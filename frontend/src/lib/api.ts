const params = new URLSearchParams(window.location.search)
const API = params.get("api") || "/api"

export async function postJson<T = unknown>(path: string, body: unknown): Promise<{ ok: boolean; status: number; data: T }> {
  const r = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  const data = await r.json().catch(() => ({}) as T)
  return { ok: r.ok, status: r.status, data }
}

export async function getJson<T = unknown>(path: string): Promise<{ ok: boolean; status: number; data: T }> {
  const r = await fetch(`${API}${path}`)
  const data = await r.json().catch(() => ({}) as T)
  return { ok: r.ok, status: r.status, data }
}
