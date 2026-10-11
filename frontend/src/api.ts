import type { AppState, AuditView, Disruption, Plan, PreviewResult, Presets, Report } from './types'

const ACTOR_KEY = 'detour.actor'

export function getActor(): string {
  try { return localStorage.getItem(ACTOR_KEY) || 'dispatcher' } catch { return 'dispatcher' }
}
export function setActor(name: string): void {
  try { localStorage.setItem(ACTOR_KEY, name) } catch { /* private mode: keep the default */ }
}

export class ApiError extends Error {
  status: number
  code: string
  extra: Record<string, unknown>
  constructor(status: number, code: string, message: string, extra: Record<string, unknown> = {}) {
    super(message)
    this.status = status
    this.code = code
    this.extra = extra
  }
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: { 'Content-Type': 'application/json', 'X-Actor': getActor() },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new ApiError(res.status, data.code ?? 'error', data.message ?? res.statusText, data)
  }
  return data as T
}

export const api = {
  state: () => call<AppState>('GET', '/state'),
  presets: () => call<Presets>('GET', '/presets'),
  reset: () => call<AppState>('POST', '/reset'),
  buildPlan: (mode: 'auto' | 'demo' | 'solve') => call<AppState>('POST', '/plan', { mode }),
  preview: (disruption: Disruption) => call<PreviewResult>('POST', '/disruptions/preview', { disruption }),
  confirm: (id: string, confirmedBy: string) =>
    call<AppState>('POST', `/disruptions/${id}/confirm`, { confirmed_by: confirmedBy }),
  validate: (plan?: Plan) => call<Report>('POST', '/validate', plan ? { plan } : undefined),
  audit: (limit = 300) => call<AuditView>('GET', `/audit?limit=${limit}`),
}
