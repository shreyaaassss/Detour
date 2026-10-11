import { driverOf, hhmm, nameOf, vehicleColor } from '../format'
import type { Plan, Scenario } from '../types'
import { Glyph } from './ui'

interface Props { scenario: Scenario; plan: Plan; selected: string | null; onSelect: (id: string | null) => void }

export function PlanTable({ scenario, plan, selected, onSelect }: Props) {
  const now = plan.as_of ?? -1
  const routes = plan.routes.filter((r) => selected === null || r.vehicle_id === selected)
  const dlv = (id: string) => scenario.deliveries.find((d) => d.id === id)

  return (
    <div>
      {routes.map((r) => {
        const v = scenario.vehicles.find((q) => q.id === r.vehicle_id)!
        const peak = Math.max(r.initial_load, ...r.stops.map((s) => s.load_after))
        return (
          <section key={r.vehicle_id} aria-label={`Route for ${driverOf(scenario, r.vehicle_id)}`}>
            <div className="vhead" onClick={() => onSelect(selected === r.vehicle_id ? null : r.vehicle_id)}>
              <span className="swatch" style={{ background: vehicleColor(scenario, r.vehicle_id) }} />
              <b>{driverOf(scenario, r.vehicle_id)}</b>
              <span className="muted small">
                {v.status === 'failed' ? `broke down ${hhmm(v.failed_at)}` : `${r.stops.length} stops, drives ${Math.round(r.travel_minutes)} min`}
                {`, carries up to ${peak} of ${v.capacity}`}
              </span>
            </div>
            {r.stops.length === 0 ? <p className="muted small" style={{ margin: '2px 0 0 22px' }}>No stops.</p> : (
              <table className="tbl">
                <thead><tr>
                  <th>#</th><th>Stop</th><th>Window</th><th className="r">Arrives</th><th className="r">Waits</th>
                  <th className="r">Serves</th><th className="r">Leaves</th><th className="r">Load</th><th />
                </tr></thead>
                <tbody>
                  {r.stops.map((s, i) => {
                    const d = dlv(s.delivery_id)
                    const pick = s.kind === 'pickup'
                    const done = s.frozen && s.departure <= now
                    const committed = s.frozen && !done
                    return (
                      <tr key={`${s.kind}${s.delivery_id}`} className={`${done ? 'done' : ''} ${pick ? 'pickup' : ''}`}>
                        <td>{i + 1}</td>
                        <td>
                          <b>{s.delivery_id}</b> {pick ? `collect at ${nameOf(scenario, s.location)}` : nameOf(scenario, s.location)}
                          {s.idle > 0.5 && <span className="tag" title="The vehicle stays where it is until it needs to leave">holds {Math.round(s.idle)} min first</span>}
                        </td>
                        <td>{!pick && d ? `${hhmm(d.window_start)}–${hhmm(d.window_end)}` : pick ? `from ${hhmm(s.service_start)}` : ''}</td>
                        <td className="r">{hhmm(s.arrival)}</td>
                        <td className="r">{s.wait > 0.5 ? `${Math.round(s.wait)} min` : ''}</td>
                        <td className="r">{hhmm(s.service_start)}</td>
                        <td className="r">{hhmm(s.departure)}</td>
                        <td className="r">{s.load_after}</td>
                        <td>{done ? <span className="tag">done</span> : committed ? <span className="tag"><Glyph name="lock" size={10} /> committed</span> : ''}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </section>
        )
      })}
      {plan.unplaced.length > 0 && (
        <section style={{ marginTop: 20 }}>
          <h3 className="h">Cannot be delivered</h3>
          <table className="tbl"><tbody>
            {plan.unplaced.map((u) => (
              <tr key={u.delivery_id}>
                <td><b>{u.delivery_id}</b></td>
                <td>{nameOf(scenario, dlv(u.delivery_id)?.location)}</td>
                <td className="reason">{u.reason}{u.vehicle_id ? ` (still loaded on ${u.vehicle_id})` : ''}</td>
              </tr>
            ))}
          </tbody></table>
        </section>
      )}
    </div>
  )
}
