import type { Plan, Scenario } from './types'

export interface Pt { x: number; y: number }

/** Where each location sits in the SVG: y is flipped so north is up, with a margin around everything. */
export function layout(scenario: Scenario, pad = 9, padX = 20) {
  const xs = scenario.locations.map((l) => l.x), ys = scenario.locations.map((l) => l.y)
  const minX = Math.min(...xs) - padX, maxX = Math.max(...xs) + padX
  const minY = Math.min(...ys) - pad, maxY = Math.max(...ys) + pad
  const at = (id: string): Pt => {
    const l = scenario.locations.find((q) => q.id === id)
    return l ? { x: l.x - minX, y: maxY - l.y } : { x: 0, y: 0 }
  }
  return { width: maxX - minX, height: maxY - minY, at }
}

/** Several stops can share one place (a handover, two deliveries). Fan them out so every marker is visible. */
export function offsets(plans: Plan[]): Map<string, Pt> {
  const seen = new Map<string, number>()
  const out = new Map<string, Pt>()
  for (const p of plans) {
    for (const r of p.routes) {
      for (const s of r.stops) {
        const key = `${p === plans[0] ? 'p' : 'o'}|${r.vehicle_id}|${s.kind}|${s.delivery_id}`
        const k = seen.get(s.location) ?? 0
        if (p === plans[0]) seen.set(s.location, k + 1)
        const ang = k * 2.4 // golden-ish spiral so neighbours do not line up
        const rad = k === 0 ? 0 : 2.6 + Math.floor(k / 5) * 1.6
        out.set(key, { x: Math.cos(ang) * rad, y: Math.sin(ang) * rad })
      }
    }
  }
  return out
}

export interface Placed { x: number; y: number; anchor: 'start' | 'middle' | 'end' }

/** Put each name beside its point without writing over another name or another point. */
export function placeLabels(items: { id: string; x: number; y: number; text: string }[], fs = 2.6): Map<string, Placed> {
  const boxes: { x0: number; y0: number; x1: number; y1: number }[] = items.map((i) => ({ x0: i.x - 1.8, y0: i.y - 1.8, x1: i.x + 1.8, y1: i.y + 1.8 }))
  const out = new Map<string, Placed>()
  const hit = (a: (typeof boxes)[number]) => boxes.filter((b) => a.x0 < b.x1 && a.x1 > b.x0 && a.y0 < b.y1 && a.y1 > b.y0).length
  for (const it of items) {
    const w = it.text.length * fs * 0.52, h = fs
    const cands: Placed[] = [
      { x: it.x + 3, y: it.y + 0.9, anchor: 'start' },
      { x: it.x - 3, y: it.y + 0.9, anchor: 'end' },
      { x: it.x, y: it.y + 5.2, anchor: 'middle' },
      { x: it.x, y: it.y - 3.6, anchor: 'middle' },
      { x: it.x + 3, y: it.y + 4.6, anchor: 'start' },
      { x: it.x - 3, y: it.y - 2.6, anchor: 'end' },
      { x: it.x + 3, y: it.y - 2.6, anchor: 'start' },
      { x: it.x - 3, y: it.y + 4.6, anchor: 'end' },
    ]
    let best = cands[0], bestHits = Infinity, bestBox = boxes[0]
    for (const c of cands) {
      const x0 = c.anchor === 'start' ? c.x : c.anchor === 'end' ? c.x - w : c.x - w / 2
      const box = { x0, y0: c.y - h * 0.8, x1: x0 + w, y1: c.y + h * 0.25 }
      const n = hit(box)
      if (n < bestHits) { best = c; bestHits = n; bestBox = box }
      if (n === 0) break
    }
    boxes.push(bestBox)
    out.set(it.id, best)
  }
  return out
}
