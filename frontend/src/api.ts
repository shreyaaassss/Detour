import { setServerTime } from './serverTime'
import type {
  AppState, AuditView, CustomerMessage, Disruption, Incident, Interpreter, Note, Offer, ParseInfo, Plan, PreviewResult, Presets,
  Proposal, Report, RescueOverview, TelephonyStatus, VoiceStatus,
} from './types'

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
  const data = await res.json().catch(() => null)
  if (data === null) {
    throw new ApiError(res.status, 'bad_response', 'The server sent something unexpected. Is the backend running?')
  }
  if (!res.ok) {
    throw new ApiError(res.status, data.code ?? 'error', data.message ?? res.statusText, data)
  }
  if (typeof data.server_time === 'number') setServerTime(data.server_time)
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

  parseReport: (text: string, source: 'text' | 'voice' = 'text') =>
    call<{ parse: ParseInfo; preview: PreviewResult }>('POST', '/disruptions/parse', { text, source }),
  interpreter: () => call<Interpreter>('GET', '/interpreter'),

  // phone line
  telephonyStatus: () => call<TelephonyStatus>('GET', '/telephony/status'),
  testCall: (driver?: string) => call<{ started: boolean; language: string }>('POST', '/telephony/test', { driver }),

  // voice
  voiceStatus: () => call<VoiceStatus>('GET', '/voice/status'),
  warmVoice: () => call<{ lines: number; generated: number; already_cached: number; characters: number; problems: string[] }>('POST', '/voice/warm'),
  voiceReport: async (driver: string, language: string, audio: Blob) => {
    const res = await fetch(`/incidents/voice?driver=${encodeURIComponent(driver)}&language=${language}`, {
      method: 'POST', headers: { 'Content-Type': audio.type || 'audio/webm', 'X-Actor': getActor() }, body: audio,
    })
    const data = await res.json().catch(() => null)
    if (data && typeof data.server_time === 'number') setServerTime(data.server_time)
    if (!res.ok) throw new ApiError(res.status, data?.code ?? 'error', data?.message ?? res.statusText, data ?? {})
    return data as { transcript: string; detected_language: string | null; incident: Incident }
  },

  // rescue
  overview: () => call<RescueOverview>('GET', '/incidents'),
  report: (b: { driver: string; transcript?: string; language?: string; location_id?: string; breakdown?: boolean; source?: string; engine?: string }) =>
    call<{ incident: Incident }>('POST', '/incidents/report', b),
  confirmReport: (id: string, b: { confirmed?: boolean; location_id?: string }) =>
    call<{ incident: Incident }>('POST', `/incidents/${id}/confirm`, b),
  proposal: (id: string) => call<{ proposal: Proposal; state: string }>('GET', `/incidents/${id}/proposal`),
  approve: (id: string, b: { approved_by: string; shortlist: string[]; proposal_version: number; role: 'head' | 'backup' }) =>
    call<{ incident: Incident }>('POST', `/incidents/${id}/approve`, b),
  rejectIncident: (id: string, by: string) => call<{ incident: Incident }>('POST', `/incidents/${id}/reject`, { by }),
  offers: (driver: string) => call<{ offers: Offer[] }>('GET', `/offers?driver=${encodeURIComponent(driver)}`),
  respond: (offerId: string, response: 'accept' | 'decline', by?: string) =>
    call<{ incident: Incident }>('POST', `/offers/${offerId}/respond`, { response, via: 'tap', by }),
  callEvent: (offerId: string, outcome: string) =>
    call<{ incident: Incident }>('POST', '/telephony/webhook', { offer_id: offerId, outcome }),
  notifications: (to: string, after = 0) =>
    call<{ notifications: Note[] }>('GET', `/notifications?to=${encodeURIComponent(to)}&after=${after}`),
  setClock: (b: { sim_time?: string; speed?: number }) => call<{ sim: number; speed: number }>('POST', '/clock', b),
  messages: () => call<{ messages: CustomerMessage[] }>('GET', '/messages'),
  approveMessage: (deliveryId: string) => call<CustomerMessage>('POST', `/messages/${deliveryId}/approve`),
}
