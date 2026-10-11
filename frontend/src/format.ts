import type { Location, Scenario } from './types'

export function hhmm(t: number | null | undefined): string {
  if (t == null) return '--:--'
  const m = Math.round(t)
  return `${String(Math.floor(m / 60) % 24).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`
}

export function parseHhmm(s: string): number | null {
  const m = /^(\d{1,2}):(\d{2})$/.exec(s.trim())
  if (!m) return null
  const h = Number(m[1]), min = Number(m[2])
  return h > 23 || min > 59 ? null : h * 60 + min
}

export function minutes(n: number): string {
  const r = Math.round(n)
  return r >= 60 ? `${Math.floor(r / 60)} h ${r % 60 ? `${r % 60} min` : ''}`.trim() : `${r} min`
}

export function signed(n: number): string {
  const r = Math.round(n)
  return r > 0 ? `+${r} min` : r < 0 ? `−${-r} min` : 'no change'
}

export function nameOf(scenario: Scenario | Location[], id: string | null | undefined): string {
  if (!id) return ''
  const locs = Array.isArray(scenario) ? scenario : scenario.locations
  return locs.find((l) => l.id === id)?.name ?? id
}

export function driverOf(scenario: Scenario, vehicleId: string | null | undefined): string {
  if (!vehicleId) return ''
  const v = scenario.vehicles.find((x) => x.id === vehicleId)
  return v?.driver ? `${v.id} (${v.driver})` : (vehicleId ?? '')
}

// Colour-blind-safe line colours (Okabe-Ito, darkened for white backgrounds), one per vehicle.
const LINE = ['#0067a3', '#c4510a', '#007a5a', '#9a4b82', '#8a6d00', '#3b4a63']
export function vehicleColor(scenario: Scenario, vehicleId: string): string {
  const i = scenario.vehicles.findIndex((v) => v.id === vehicleId)
  return LINE[(i < 0 ? 0 : i) % LINE.length]
}

/** 1:42 style countdown text. */
export function mmss(seconds: number | null): string {
  if (seconds == null) return ''
  const s = Math.ceil(seconds)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}
