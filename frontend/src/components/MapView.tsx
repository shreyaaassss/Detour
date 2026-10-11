import { layout, offsets, placeLabels } from '../map'
import { driverOf, hhmm, nameOf, vehicleColor } from '../format'
import type { Plan, Scenario } from '../types'

interface Props {
  scenario: Scenario
  plan: Plan
  original: Plan | null
  showOriginal: boolean
  selected: string | null
  onSelect: (id: string | null) => void
}

export function MapView({ scenario, plan, original, showOriginal, selected, onSelect }: Props) {
  const { width, height, at } = layout(scenario)
  const off = offsets(original ? [plan, original] : [plan])
  const pos = (loc: string, key: string) => {
    const b = at(loc), o = off.get(key) ?? { x: 0, y: 0 }
    return { x: b.x + o.x, y: b.y + o.y }
  }
  const labels = placeLabels(scenario.locations.map((l) => ({ id: l.id, ...at(l.id), text: l.id === scenario.depot ? `${l.name} (depot)` : l.name })), 3.2)
  const failed = scenario.vehicles.filter((v) => v.status === 'failed' && v.failure_location)

  return (
    <>
      <h2 className="h">Map</h2>
      <svg className="chart" viewBox={`0 0 ${width} ${height}`} role="img" style={{ flex: 1, minHeight: 0, maxHeight: 520 }}
        aria-label="Routes on a simulated map. Solid lines are done or committed, dashed lines are planned.">
        <rect width={width} height={height} fill="var(--paper)" rx="2" />

        {scenario.closures.map((c, i) => {
          const a = at(c.a), b = at(c.b)
          return (
            <g key={i}>
              <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="var(--closure)" strokeWidth="2.2" strokeDasharray="1.2 1.6" opacity="0.8" />
              <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 1.4} fontSize="3.1" textAnchor="middle" fontWeight="650"
                style={{ fill: 'var(--closure)' }} className="svgtext">slower +{c.added_minutes} min</text>
            </g>
          )
        })}

        {showOriginal && original?.routes.map((r) => {
          const pts = [at(r.start_location), ...r.stops.map((s) => pos(s.location, `o|${r.vehicle_id}|${s.kind}|${s.delivery_id}`))]
          return <polyline key={`o${r.vehicle_id}`} points={pts.map((p) => `${p.x},${p.y}`).join(' ')} fill="none"
            stroke="var(--ink-3)" strokeWidth="0.5" strokeDasharray="0.8 1" opacity="0.6" />
        })}

        {plan.routes.map((r) => {
          const color = vehicleColor(scenario, r.vehicle_id)
          const dim = selected !== null && selected !== r.vehicle_id
          let prev = at(r.start_location)
          return (
            <g key={r.vehicle_id} opacity={dim ? 0.2 : 1}>
              {r.stops.map((s, i) => {
                const p = pos(s.location, `p|${r.vehicle_id}|${s.kind}|${s.delivery_id}`)
                const seg = <line key={`l${i}`} x1={prev.x} y1={prev.y} x2={p.x} y2={p.y} stroke={color}
                  strokeWidth={s.frozen ? 1.5 : 1} strokeDasharray={s.frozen ? undefined : '2.2 1.4'} strokeLinecap="round" opacity={s.frozen ? 0.95 : 0.8} />
                prev = p
                return seg
              })}
              {r.stops.map((s, i) => {
                const p = pos(s.location, `p|${r.vehicle_id}|${s.kind}|${s.delivery_id}`)
                const pick = s.kind === 'pickup'
                const tip = `${r.vehicle_id} stop ${i + 1}: ${pick ? 'collect' : 'deliver'} ${s.delivery_id} at ${nameOf(scenario, s.location)}, ${hhmm(s.service_start)}`
                return (
                  <g key={`m${i}`}>
                    <title>{tip}</title>
                    {pick
                      ? <rect x={p.x - 2.3} y={p.y - 2.3} width="4.6" height="4.6" fill="var(--surface)" stroke={color} strokeWidth="0.8" />
                      : <circle cx={p.x} cy={p.y} r="2.6" fill={color} stroke="var(--surface)" strokeWidth="0.5" />}
                    <text x={p.x} y={p.y + 1.1} fontSize={pick ? 2.8 : 3.1} textAnchor="middle" fontWeight="700"
                      style={{ fill: pick ? color : '#fff' }} className="svgtext">{pick ? '↑' : i + 1}</text>
                  </g>
                )
              })}
            </g>
          )
        })}

        {scenario.locations.map((l) => {
          const p = at(l.id)
          const isDepot = l.id === scenario.depot
          const lab = labels.get(l.id)!
          return (
            <g key={l.id}>
              {isDepot && <path d={`M${p.x} ${p.y - 3.2} l3.2 3.2 l-3.2 3.2 l-3.2 -3.2z`} fill="var(--ink)" />}
              <text x={lab.x} y={lab.y} textAnchor={lab.anchor} fontSize="3.2" fontWeight={isDepot ? 700 : 500}
                style={{ fill: 'var(--ink-2)' }} className="svgtext" paintOrder="stroke" stroke="var(--paper)" strokeWidth="0.9">
                {isDepot ? `${l.name} (depot)` : l.name}
              </text>
            </g>
          )
        })}

        {failed.map((v) => {
          const p = at(v.failure_location!)
          return (
            <g key={v.id} stroke="var(--broken)" strokeWidth="1.1" strokeLinecap="round">
              <title>{`${driverOf(scenario, v.id)} broke down here at ${hhmm(v.failed_at)}`}</title>
              <circle cx={p.x} cy={p.y} r="3.4" fill="var(--surface)" />
              <line x1={p.x - 1.5} y1={p.y - 1.5} x2={p.x + 1.5} y2={p.y + 1.5} />
              <line x1={p.x + 1.5} y1={p.y - 1.5} x2={p.x - 1.5} y2={p.y + 1.5} />
            </g>
          )
        })}
      </svg>
      <div className="legend" style={{ marginTop: 8 }}>
        {scenario.vehicles.map((v) => (
          <button key={v.id} className="btn quiet" aria-pressed={selected === v.id}
            onClick={() => onSelect(selected === v.id ? null : v.id)} style={{ fontWeight: selected === v.id ? 700 : 500 }}>
            <i style={{ background: vehicleColor(scenario, v.id) }} />{v.id} {v.driver}
          </button>
        ))}
      </div>
    </>
  )
}
