import { driverOf, hhmm, nameOf } from '../format'
import type { Change, Plan, Scenario } from '../types'

interface Props { scenario: Scenario; plan: Plan; changes?: Change[] }

function Van() {
  return (
    <svg viewBox="0 0 28 18" width="28" height="18" aria-hidden="true">
      <rect x="1" y="2" width="17" height="10" rx="2" fill="currentColor" />
      <path d="M18 5h5l4 4v3h-9z" fill="currentColor" />
      <circle cx="7" cy="14" r="3" fill="currentColor" stroke="#fff" strokeWidth="1.5" />
      <circle cx="21" cy="14" r="3" fill="currentColor" stroke="#fff" strokeWidth="1.5" />
    </svg>
  )
}

/** One lane per vehicle: its stops in order, with arrival and waiting, and a van that drives the lane once.
 * The simple picture of the plan. The timeline and map are under More. */
export function RouteLanes({ scenario, plan, changes }: Props) {
  const now = plan.as_of ?? -1
  const byId = new Map((changes ?? []).map((c) => [c.delivery_id, c]))
  return (
    <div className="lanes">
      {plan.routes.map((r, ri) => {
        const v = scenario.vehicles.find((q) => q.id === r.vehicle_id)
        if (!v) return null
        const failed = v.status === 'failed'
        const peak = Math.max(r.initial_load, ...r.stops.map((s) => s.load_after))
        return (
          <section key={r.vehicle_id} className={`rl ${failed ? 'failed' : ''}`} aria-label={`Route for ${driverOf(scenario, r.vehicle_id)}`}>
            <header className="rl-head">
              <b>{driverOf(scenario, r.vehicle_id)}</b>
              <span className="muted small">
                {failed ? `Broke down at ${hhmm(v.failed_at)}. No stops after that.` : `${r.stops.length} stops, drives ${Math.round(r.travel_minutes)} min`}
                {!failed && `, carries at most ${peak} of ${v.capacity}`}
              </span>
            </header>
            <div className="rl-road" aria-hidden="true">
              <span className="rl-van" style={{ animationDelay: `${ri * 0.12}s` }}>{failed ? <b className="rl-x">✕</b> : <Van />}</span>
            </div>
            <ol className="rl-stops">
              <li className="rl-stop depot"><b>Depot</b><span>leaves {hhmm(r.start_time)}</span></li>
              {r.stops.map((s, i) => {
                const pick = s.kind === 'pickup'
                const done = s.frozen && s.departure <= now
                const c = byId.get(s.delivery_id)
                const cls = done ? 'done' : c && !c.completed && (c.status === 'moved' || c.status === 'new') ? c.status : ''
                return (
                  <li key={`${s.kind}${s.delivery_id}`} className={`rl-stop ${cls} ${pick ? 'pick' : ''}`} style={{ animationDelay: `${0.15 + i * 0.07}s` }}
                    title={c?.reason}>
                    <b>{pick ? `Collect ${s.delivery_id}` : s.delivery_id}</b>
                    <span>{nameOf(scenario, s.location)}</span>
                    <span>arrives {hhmm(s.arrival)}{s.wait > 0.5 ? `, waits ${Math.round(s.wait)} min` : ''}</span>
                    {done ? <em>done</em> : cls === 'moved' ? <em>moved</em> : cls === 'new' ? <em>new</em> : null}
                  </li>
                )
              })}
              {r.stops.length === 0 && <li className="rl-stop none"><span>No stops</span></li>}
            </ol>
          </section>
        )
      })}
      {plan.unplaced.length > 0 && (
        <section className="rl cannot" aria-label="Cannot be delivered">
          <header className="rl-head"><b>Cannot be delivered</b></header>
          <ul className="rl-cannot">
            {plan.unplaced.map((u) => (
              <li key={u.delivery_id}><span className="chip broken">{u.delivery_id}</span> {u.reason}{u.vehicle_id ? ` (still loaded on ${u.vehicle_id})` : ''}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
