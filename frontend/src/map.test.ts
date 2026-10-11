import { describe, expect, it } from 'vitest'
import { layout, offsets, placeLabels } from './map'
import type { Plan, Scenario } from './types'

const sc = { locations: [{ id: 'a', name: 'A', x: 10, y: 10 }, { id: 'b', name: 'B', x: 30, y: 50 }] } as Scenario

describe('layout', () => {
  it('puts north up and keeps a margin', () => {
    const l = layout(sc, 5, 5)
    expect(l.width).toBe(30)
    expect(l.height).toBe(50)
    expect(l.at('b').y).toBeLessThan(l.at('a').y) // larger y is further north, so nearer the top
    expect(l.at('a')).toEqual({ x: 5, y: 45 })
  })
})

describe('offsets', () => {
  it('separates stops that share a location', () => {
    const stop = (id: string) => ({ delivery_id: id, location: 'a', kind: 'delivery' })
    const plan = { routes: [{ vehicle_id: 'V1', stops: [stop('D1'), stop('D2'), stop('D3')] }] } as unknown as Plan
    const o = offsets([plan])
    const pts = ['D1', 'D2', 'D3'].map((d) => o.get(`p|V1|delivery|${d}`)!)
    expect(pts[0]).toEqual({ x: 0, y: 0 })
    expect(new Set(pts.map((p) => `${p.x.toFixed(2)},${p.y.toFixed(2)}`)).size).toBe(3)
  })
})

describe('placeLabels', () => {
  it('keeps neighbouring names from overlapping', () => {
    const items = [0, 1, 2, 3].map((i) => ({ id: `p${i}`, x: 10 + i * 4, y: 10, text: 'Wanowrie' }))
    const placed = placeLabels(items)
    const boxes = items.map((it) => {
      const p = placed.get(it.id)!
      const w = it.text.length * 2.6 * 0.52
      const x0 = p.anchor === 'start' ? p.x : p.anchor === 'end' ? p.x - w : p.x - w / 2
      return { x0, x1: x0 + w, y0: p.y - 2, y1: p.y + 0.6 }
    })
    let overlaps = 0
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i], b = boxes[j]
      if (a.x0 < b.x1 && a.x1 > b.x0 && a.y0 < b.y1 && a.y1 > b.y0) overlaps++
    }
    expect(overlaps).toBe(0)
  })
})
