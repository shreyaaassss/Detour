// Mirrors the backend models. Times are minutes since midnight.

export interface Location { id: string; name: string; x: number; y: number }
export interface Vehicle {
  id: string; capacity: number; start_location: string; driver: string | null
  status: 'active' | 'failed'; failed_at: number | null; failure_location: string | null; language: string
}
export interface Delivery {
  id: string; location: string; size: number; window_start: number; window_end: number
  service_time: number; priority: boolean
  pickup: { location: string; ready_time: number; service_time: number } | null
}
export interface Closure { a: string; b: string; start: number; end: number; added_minutes: number; multiplier: number }
export interface Scenario {
  name: string; depot: string; day_start: number
  locations: Location[]; vehicles: Vehicle[]; deliveries: Delivery[]; closures: Closure[]
}

export interface Stop {
  delivery_id: string; location: string; kind: 'delivery' | 'pickup'; idle: number
  arrival: number; wait: number; service_start: number; departure: number
  load_after: number; frozen: boolean
}
export interface Route {
  vehicle_id: string; start_location: string; start_time: number
  initial_load: number; stops: Stop[]; travel_minutes: number
}
export interface Unplaced { delivery_id: string; reason: string; vehicle_id: string | null }
export interface Plan {
  scenario: string; routes: Route[]; unplaced: Unplaced[]; total_travel: number
  solver: string; limits: string[]; as_of: number | null
}

export type Status = 'kept' | 'moved' | 'broken' | 'new'
export interface Change {
  delivery_id: string; status: Status; reason: string
  old_vehicle: string | null; new_vehicle: string | null
  old_service: number | null; new_service: number | null; completed: boolean
}
export interface Diff { as_of: number; causes: string[]; changes: Change[]; counts: Record<Status, number> }

export interface Violation { code: string; message: string; vehicle_id: string | null; delivery_id: string | null }
export interface Report { valid: boolean; violations: Violation[]; checks: string[] }

export interface Applied {
  n: number; type: string; cause: string; at: number; source: string
  confirmed_by: string | null; disruption: Disruption
}

export interface AppState {
  version: number; kind: 'demo' | 'custom'; as_of: number | null
  scenario: Scenario; original: Plan | null; plan: Plan | null
  report: Report | null; diff: Diff | null; applied: Applied[]
}

export interface PreviewResult {
  preview_id: string; base_version: number; as_of: number; cause: string
  plan: Plan; scenario: Scenario; diff: Diff; report: Report
}

export type Disruption =
  | { type: 'road_closure'; a: string; b: string; start: number; end: number; added_minutes: number; reported_at: number; source?: string }
  | { type: 'vehicle_failure'; vehicle_id: string; time: number; location: string; source?: string }
  | { type: 'urgent_delivery'; id: string; location: string; size: number; window_start: number; window_end: number; time: number; source?: string }

export interface AuditEntry {
  id: number; ts: string; sim_time: number | null; actor: string; action: string
  details: Record<string, unknown>; hash: string
}
export interface AuditView { entries: AuditEntry[]; total: number; chain: { valid: boolean; entries: number; broken_at: number | null; reason: string | null } }

export type Presets = Record<string, Disruption>

export interface Candidate {
  vehicle_id: string; driver: string | null; feasible: boolean; reason: string | null
  reach_site: number | null; leave_site: number | null; delivery_time: number | null
  own_delay: number | null; impact: Record<Status, number> | null
  other_changes: { delivery_id: string; status: Status; reason: string }[]; rank: number | null
}
export interface Proposal {
  vehicle_id: string; location_id: string; failure_time: number; primary: string | null
  primary_place: string | null; primary_due: number | null; parcels: string[]
  plan_version: number; candidates: Candidate[]
}
export interface Offer {
  id: string; incident_id: string; index: number; vehicle_id: string; driver: string | null
  channel: 'push' | 'call'; sent: number; deadline: number
  status: 'open' | 'accepted' | 'declined' | 'timed_out' | 'closed'; outcome: string | null
  call_state: 'ringing' | 'in_call' | null; conversation_deadline: number | null; ambiguous: number
  text: Record<string, string>; script: Record<string, string>; language: string
}
export type IncidentState =
  | 'REPORTED' | 'DRIVER_CONFIRMED' | 'AWAITING_HEAD' | 'HEAD_APPROVED' | 'OFFER_PUSHED' | 'CALL_ESCALATED'
  | 'CANDIDATE_DECLINED' | 'ACCEPTED' | 'COMMITTED' | 'HEAD_TIMEOUT' | 'EXHAUSTED' | 'CANCELLED' | 'REJECTED'
export interface Incident {
  id: string; driver: string; vehicle_id: string; language: string; transcript: string
  source: 'text' | 'voice' | 'buttons'; location_id: string | null; location_name: string | null
  state: IncidentState; note: string; known_locations: { id: string; name: string }[]
  readback: Record<string, string>; parcels: string[]; primary: string | null; failure_time: number | null
  proposal: Proposal | null; approver_role: 'head' | 'backup'; approved_by: string | null
  shortlist: string[]; current: number; claim: { offer: string; vehicle: string; via: string } | null
  confirm_deadline: number | null; head_deadline: number | null; reprompts: number
  escalated_to_dispatcher: boolean; result: string | null
  history: { wall: number; sim: number | null; state: string; note: string }[]
  offers: Offer[]; active_offer: Offer | null
}
export interface RescueConfig {
  push_timeout: number; driver_confirm: number; head_response: number; ring_timeout: number
  conversation_limit: number; max_shortlist: number
}
export interface RescueOverview {
  server_time: number; clock: { sim: number; speed: number }; config: RescueConfig; incidents: Incident[]
}
export interface Note {
  id: number; to: string; kind: string; incident_id: string | null; text: Record<string, string>
  wall: number; sim: number | null; data: Record<string, unknown>
}
export interface CustomerMessage { delivery_id: string; status: Status; place: string; text: string; approved: boolean }

export interface ParseInfo {
  ok: boolean; method: 'llm' | 'rules'; model: string | null; summary: string | null
  disruption: Disruption | null; warnings: string[]; llm_error: string | null
  issues: { code: string; message: string; field: string | null }[]
  known_locations: { id: string; name: string }[]
}
export interface Interpreter { mode: 'llm' | 'rules'; model: string | null }

export interface VoiceStatus {
  enabled: boolean; tts_model: string | null; stt_model: string | null
  budget: { spent: number; limit: number }
  cache: { files: number; hits: number; misses: number; errors: number }
  account: { used: number; limit: number } | null
}

export interface TelephonyStatus {
  enabled: boolean; ready: boolean; missing: string[]; language: string; numbers: Record<string, string>
  placed: number; limit: number; public_url_set: boolean
  recent: { offer: string; what: string; detail: string; at: number }[]
}
