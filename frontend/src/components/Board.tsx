import { foldHandovers, laneSegments, movedFromOriginal, timeDomain } from '../board'
import { driverOf, hhmm, nameOf, vehicleColor } from '../format'
import type { Plan, Scenario } from '../types'
import { useWidth } from '../useWidth'
import { Glyph } from './ui'

interface Props {
  scenario: Scenario
  plan: Plan
  original: Plan | null
  showOriginal: boolean
  onToggleOriginal: (v: boolean) => void
  selected: string | null
  onSelect: (id: string | null) => void
}

const LABEL_W = 108
const LANE_H = 56
const TOP = 30

export function Board({ scenario, plan, original, showOriginal, onToggleOriginal, selected, onSelect }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [lo, hi] = timeDomain(scenario, [plan, original])
  const plotW = Math.max(200, width - LABEL_W - 8)
  const x = (t: number) => LABEL_W + ((t - lo) / (hi - lo)) * plotW
  const lanes = scenario.vehicles
  const H = TOP + lanes.length * LANE_H + 4
  const now = plan.as_of
  const ticks: number[] = []
  for (let t = lo; t <= hi; t += 30) ticks.push(t)
  const place = (id: string) => nameOf(scenario, scenario.deliveries.find((d) => d.id === id)?.location)

  return (
    <section className="board" aria-label="Day board">
      <div className="boardhead">
        <h2 className="h" style={{ margin: 0 }}>Day board</h2>
        <div className="legend" aria-hidden="true">
          <span><i style={{ background: 'var(--ink-2)' }} />Serving</span>
          <span><i style={{ background: 'transparent', border: '1.5px solid var(--ink-2)' }} />Collecting a parcel</span>
          <span><i style={{ background: 'repeating-linear-gradient(135deg, var(--moved) 0 2px, transparent 2px 4px)' }} />Waiting at customer</span>
          <span><i style={{ background: 'repeating-linear-gradient(135deg, var(--ink-3) 0 1px, transparent 1px 4px)' }} />Holding back</span>
          <span><i style={{ background: 'transparent', borderTop: '3px solid var(--ink-2)', height: 0, verticalAlign: 3 }} />Driving</span>
        </div>
        <div className="spacer" />
        {original && (
          <label className="check">
            <input type="checkbox" checked={showOriginal} onChange={(e) => onToggleOriginal(e.target.checked)} />
            Show the original plan behind
          </label>
        )}
      </div>

      <div ref={ref}>
        <svg className="chart" viewBox={`0 0 ${width} ${H}`} height={H} role="img"
          aria-label="Each vehicle's day: when it drives, waits and serves, with road closures shaded and the current time marked">
          <defs>
            <pattern id="hatch-wait" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="5" height="5" fill="var(--moved-bg)" /><rect width="2" height="5" fill="var(--moved)" opacity="0.55" />
            </pattern>
            <pattern id="hatch-hold" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="1" height="5" fill="var(--ink-3)" opacity="0.7" />
            </pattern>
            <pattern id="hatch-closure" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
              <rect width="2" height="7" fill="var(--closure)" opacity="0.14" />
            </pattern>
            <pattern id="hatch-broken" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="1.5" height="6" fill="var(--broken)" opacity="0.35" />
            </pattern>
          </defs>

          {/* time axis */}
          {ticks.map((t) => (
            <g key={t}>
              <line x1={x(t)} x2={x(t)} y1={TOP - 4} y2={H - 4} stroke="var(--line-2)" strokeWidth={t % 60 === 0 ? 1.2 : 0.7} />
              {t % 60 === 0 && x(t) + 40 < width && !(now != null && Math.abs(x(t) - x(now)) < 46) && <text className="svgtext" x={x(t) + 3} y={TOP - 11} fontSize="12" fill="var(--ink-2)" style={{ fill: 'var(--ink-2)' }}>{hhmm(t)}</text>}
            </g>
          ))}

          {/* closures across every lane */}
          {scenario.closures.map((c, i) => {
            const a = x(Math.max(c.start, lo)), b = x(Math.min(c.end, hi))
            return (
              <g key={i}>
                <rect x={a} y={TOP - 4} width={Math.max(0, b - a)} height={H - TOP} fill="url(#hatch-closure)" />
                <line x1={a} x2={a} y1={TOP - 4} y2={H - 4} stroke="var(--closure)" strokeWidth="1" strokeDasharray="3 3" />
                <text x={a + 4} y={H - 8} fontSize="11" style={{ fill: 'var(--closure)' }} className="svgtext">
                  {nameOf(scenario, c.a)}–{nameOf(scenario, c.b)} slower{c.added_minutes ? ` +${c.added_minutes} min` : ''}
                </text>
              </g>
            )
          })}

          {lanes.map((v, i) => {
            const y0 = TOP + i * LANE_H
            const color = vehicleColor(scenario, v.id)
            const route = plan.routes.find((r) => r.vehicle_id === v.id)
            const orig = original?.routes.find((r) => r.vehicle_id === v.id)
            const dim = selected !== null && selected !== v.id
            const failed = v.status === 'failed' && v.failed_at != null
            return (
              <g key={v.id} opacity={dim ? 0.3 : 1}>
                <line x1={LABEL_W} x2={LABEL_W + plotW} y1={y0 + LANE_H - 2} y2={y0 + LANE_H - 2} stroke="var(--line)" strokeWidth="0.8" />
                <g role="button" tabIndex={0} style={{ cursor: 'pointer' }} aria-label={`${driverOf(scenario, v.id)}, ${selected === v.id ? 'selected' : 'select'}`}
                  onClick={() => onSelect(selected === v.id ? null : v.id)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(selected === v.id ? null : v.id) } }}>
                  <rect x="0" y={y0 + 4} width={LABEL_W - 8} height={LANE_H - 10} fill="transparent" />
                  <rect x="0" y={y0 + 14} width="5" height="28" rx="2" fill={color} />
                  <text className="svgtext" x="14" y={y0 + 29} fontSize="15" fontWeight="700">{v.id}</text>
                  <text x="14" y={y0 + 45} fontSize="12" style={{ fill: 'var(--ink-2)' }} className="svgtext">{v.driver ?? ''}</text>
                </g>

                {showOriginal && movedFromOriginal(orig, route).map((s, k) => (
                  <g key={`o${k}`}>
                    <rect x={x(s.from)} y={y0 + 14} width={Math.max(4, x(s.to) - x(s.from))} height={22} rx="3" fill="none"
                      stroke="var(--ink-3)" strokeDasharray="3 2" strokeWidth="1.2" />
                    <text x={x(s.from) + Math.max(4, x(s.to) - x(s.from)) / 2} y={y0 + 10} fontSize="11" textAnchor="middle" style={{ fill: 'var(--ink-3)' }} className="svgtext">{s.stop?.delivery_id}</text>
                  </g>
                ))}

                {route && foldHandovers(laneSegments(route)).map((s, k) => {
                  const xa = x(s.from), xb = x(s.to), w = xb - xa
                  const stop = s.stop!
                  const tip = `${stop.delivery_id} · ${nameOf(scenario, stop.location)}\nArrive ${hhmm(stop.arrival)}, ${stop.kind === 'pickup' ? 'collect' : 'serve'} ${hhmm(stop.service_start)}–${hhmm(stop.departure)}`
                  if (s.kind === 'drive') return <line key={k} x1={xa} x2={xb} y1={y0 + 25} y2={y0 + 25} stroke={color} strokeWidth="3" strokeLinecap="round" opacity="0.75" />
                  if (s.kind === 'hold') return <rect key={k} x={xa} y={y0 + 21} width={Math.max(0, w)} height="8" fill="url(#hatch-hold)"><title>{`Holding back ${Math.round(s.to - s.from)} min`}</title></rect>
                  if (s.kind === 'wait') return <rect key={k} x={xa} y={y0 + 14} width={Math.max(0, w)} height="22" fill="url(#hatch-wait)"><title>{`Waiting ${Math.round(s.to - s.from)} min for the window to open`}</title></rect>
                  const pick = s.kind === 'pickup'
                  const d = scenario.deliveries.find((q) => q.id === stop.delivery_id)
                  return (
                    <g key={k}>
                      <title>{tip}</title>
                      {!pick && d && (
                        <g stroke={color} opacity="0.55" strokeWidth="1.6">
                          <line x1={x(d.window_start)} x2={x(d.window_end)} y1={y0 + 45} y2={y0 + 45} />
                          <line x1={x(d.window_start)} x2={x(d.window_start)} y1={y0 + 41} y2={y0 + 49} />
                          <line x1={x(d.window_end)} x2={x(d.window_end)} y1={y0 + 41} y2={y0 + 49} />
                        </g>
                      )}
                      {w < 0.5
                        ? <line x1={xa} x2={xa} y1={y0 + 12} y2={y0 + 38} stroke={color} strokeWidth="2" />
                        : <rect x={xa} y={y0 + 14} width={Math.max(4, w)} height="22" rx="3"
                            fill={pick ? 'var(--surface)' : color} stroke={color} strokeWidth="1.8" opacity={stop.frozen ? 1 : 0.9} />}
                      {w >= 0.5 && <text className="svgtext" x={xa + Math.max(4, w) / 2} y={y0 + 10} textAnchor="middle" fontSize="11.5" fontWeight="700"
                        style={{ fill: color }}>{pick ? `collect ${[stop.delivery_id, ...(s.also ?? [])].join(' + ')}` : stop.delivery_id}</text>}
                    </g>
                  )
                })}

                {failed && (() => {
                  const fx = x(v.failed_at!)
                  return (
                    <g>
                      <rect x={fx} y={y0 + 6} width={Math.max(0, LABEL_W + plotW - fx)} height={LANE_H - 12} fill="url(#hatch-broken)" />
                      <g stroke="var(--broken)" strokeWidth="2.4" strokeLinecap="round"><line x1={fx - 6} y1={y0 + 19} x2={fx + 6} y2={y0 + 31} /><line x1={fx + 6} y1={y0 + 19} x2={fx - 6} y2={y0 + 31} /></g>
                      <text x={fx - 6} y={y0 + 50} fontSize="12" fontWeight="650" style={{ fill: 'var(--broken)' }} className="svgtext">Broke down {hhmm(v.failed_at)} at {nameOf(scenario, v.failure_location)}</text>
                    </g>
                  )
                })()}
              </g>
            )
          })}

          {/* the present */}
          {now != null && (
            <g>
              <rect x={x(lo)} y={TOP - 4} width={Math.max(0, x(now) - x(lo))} height={H - TOP} fill="var(--ink)" opacity="0.04" />
              <line x1={x(now)} x2={x(now)} y1={TOP - 16} y2={H - 4} stroke="var(--now)" strokeWidth="2" />
              <text x={x(now) + 5} y={TOP - 18} fontSize="12" fontWeight="700" style={{ fill: 'var(--now)' }} className="svgtext">now {hhmm(now)}</text>
            </g>
          )}
        </svg>
      </div>

      {plan.unplaced.length > 0 && (
        <div className="cantdo" role="region" aria-label="Deliveries that cannot be made">
          {plan.unplaced.map((u) => (
            <div key={u.delivery_id} className="row small">
              <span className="chip broken"><Glyph name="broken" size={11} />Cannot deliver</span>
              <b>{u.delivery_id}</b><span>{place(u.delivery_id)}</span>
              <span className="muted">{u.reason}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
