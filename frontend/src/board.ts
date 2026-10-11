import type { Plan, Route, Scenario, Stop } from './types'

export type SegKind = 'hold' | 'drive' | 'wait' | 'service' | 'pickup'
export interface Seg { kind: SegKind; from: number; to: number; stop?: Stop; also?: string[] }

/** Break a route into what the vehicle is doing over time: holding, driving, waiting or serving. */
export function laneSegments(route: Route): Seg[] {
  const out: Seg[] = []
  let cursor = route.start_time
  for (const s of route.stops) {
    if (s.idle > 0.5) out.push({ kind: 'hold', from: cursor, to: cursor + s.idle, stop: s })
    const leave = cursor + s.idle
    if (s.arrival - leave > 0.01) out.push({ kind: 'drive', from: leave, to: s.arrival, stop: s })
    if (s.wait > 0.5) out.push({ kind: 'wait', from: s.arrival, to: s.service_start, stop: s })
    out.push({ kind: s.kind === 'pickup' ? 'pickup' : 'service', from: s.service_start, to: s.departure, stop: s })
    cursor = s.departure
  }
  return out
}

/** Visible time range: whole 30-minute marks around everything in either plan. */
export function timeDomain(scenario: Scenario, plans: (Plan | null)[]): [number, number] {
  let lo = scenario.day_start
  let hi = lo + 180
  for (const p of plans) {
    if (!p) continue
    for (const r of p.routes) {
      lo = Math.min(lo, r.start_time)
      for (const s of r.stops) hi = Math.max(hi, s.departure)
    }
  }
  for (const c of scenario.closures) hi = Math.max(hi, Math.min(c.end, hi + 60))
  return [Math.floor(lo / 30) * 30, Math.ceil((hi + 10) / 30) * 30]
}

/** Original stops that are no longer where they were (another vehicle, or a different time). */
export function movedFromOriginal(original: Route | undefined, revised: Route | undefined): Seg[] {
  if (!original) return []
  return laneSegments(original).filter((seg) => {
    if (seg.kind !== 'service') return false
    const now = revised?.stops.find((s) => s.delivery_id === seg.stop!.delivery_id && s.kind === 'delivery')
    return !now || Math.abs(now.service_start - seg.from) >= 1
  })
}

/** Pickups that share one handover (zero length, same place) are folded into the block before them. */
export function foldHandovers(segs: Seg[]): Seg[] {
  const out: Seg[] = []
  for (const s of segs) {
    const prev = out[out.length - 1]
    if (s.kind === 'pickup' && s.to - s.from < 0.01 && prev?.kind === 'pickup' && prev.stop!.location === s.stop!.location) {
      prev.also = [...(prev.also ?? []), s.stop!.delivery_id]
    } else out.push({ ...s })
  }
  return out
}
