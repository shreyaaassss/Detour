import { driverOf, hhmm, nameOf } from './format'
import type { Disruption, Scenario } from './types'

export function describePreset(d: Disruption, sc: Scenario): { title: string; detail: string; icon: Disruption['type'] } {
  if (d.type === 'vehicle_failure') {
    return { icon: d.type, title: `${driverOf(sc, d.vehicle_id)} breaks down`, detail: `At ${nameOf(sc, d.location)}, ${hhmm(d.time)}` }
  }
  if (d.type === 'road_closure') {
    return {
      icon: d.type, title: `Slow ${nameOf(sc, d.a)} to ${nameOf(sc, d.b)}`,
      detail: `+${d.added_minutes} min between ${hhmm(d.start)} and ${hhmm(d.end)}`,
    }
  }
  return { icon: d.type, title: `Urgent delivery ${d.id}`, detail: `To ${nameOf(sc, d.location)} by ${hhmm(d.window_end)}, added ${hhmm(d.time)}` }
}
