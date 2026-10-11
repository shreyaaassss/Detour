import { describe, expect, it } from 'vitest'
import { foldHandovers, laneSegments, timeDomain } from './board'
import type { Route, Scenario, Stop } from './types'

const stop = (o: Partial<Stop>): Stop => ({
  delivery_id: 'D1', location: 'a', kind: 'delivery', idle: 0, arrival: 0, wait: 0,
  service_start: 0, departure: 0, load_after: 0, frozen: false, ...o,
})

describe('laneSegments', () => {
  it('splits a route into hold, drive, wait and service without gaps or overlap', () => {
    const route: Route = {
      vehicle_id: 'V1', start_location: 'depot', start_time: 780, initial_load: 10, travel_minutes: 0,
      stops: [stop({ idle: 20, arrival: 810, wait: 5, service_start: 815, departure: 820 })],
    }
    const segs = laneSegments(route)
    expect(segs.map((s) => s.kind)).toEqual(['hold', 'drive', 'wait', 'service'])
    expect(segs[0]).toMatchObject({ from: 780, to: 800 })
    expect(segs[1]).toMatchObject({ from: 800, to: 810 })
    for (let i = 1; i < segs.length; i++) expect(segs[i].from).toBeCloseTo(segs[i - 1].to)
  })

  it('draws a shared handover as a zero-length pickup, not a missing one', () => {
    const route: Route = {
      vehicle_id: 'V4', start_location: 'depot', start_time: 800, initial_load: 0, travel_minutes: 0,
      stops: [
        stop({ delivery_id: 'D8', kind: 'pickup', arrival: 855, service_start: 855, departure: 860 }),
        stop({ delivery_id: 'D7', kind: 'pickup', arrival: 860, service_start: 860, departure: 860 }),
      ],
    }
    const pickups = laneSegments(route).filter((s) => s.kind === 'pickup')
    expect(pickups).toHaveLength(2)
    expect(pickups[1].to - pickups[1].from).toBe(0)
    const folded = foldHandovers(laneSegments(route)).filter((s) => s.kind === 'pickup')
    expect(folded).toHaveLength(1)
    expect(folded[0].also).toEqual(['D7'])
  })
})

describe('timeDomain', () => {
  it('rounds out to half hours and covers every stop', () => {
    const sc = { day_start: 780, closures: [] } as unknown as Scenario
    const plan = {
      routes: [{ start_time: 780, stops: [stop({ departure: 1000 })] }],
    } as unknown as import('./types').Plan
    const [lo, hi] = timeDomain(sc, [plan, null])
    expect(lo).toBe(780)
    expect(hi).toBeGreaterThanOrEqual(1000)
    expect(hi % 30).toBe(0)
  })
})
