import { useState } from 'react'
import { driverOf, hhmm, nameOf, signed } from '../format'
import type { AppState, Change, Status } from '../types'
import { StatusChip } from './ui'

const ORDER: Status[] = ['broken', 'moved', 'new', 'kept']

export function ComparePanel({ state }: { state: AppState }) {
  const [view, setView] = useState<'list' | 'side'>('list')
  const [showDone, setShowDone] = useState(false)
  const { diff, scenario, original, plan } = state
  if (!diff || !original || !plan) return <p className="empty">Build a plan first, then change something to see what moves.</p>

  const place = (id: string) => nameOf(scenario, scenario.deliveries.find((d) => d.id === id)?.location)
  const done = diff.changes.filter((c) => c.completed)
  const rows = diff.changes
    .filter((c) => showDone || !c.completed)
    .sort((a, b) => ORDER.indexOf(a.status) - ORDER.indexOf(b.status) || a.delivery_id.localeCompare(b.delivery_id, undefined, { numeric: true }))
  const byId = new Map<string, Change>(diff.changes.map((c) => [c.delivery_id, c]))
  const win = (id: string) => {
    const d = scenario.deliveries.find((x) => x.id === id)
    return d ? `${hhmm(d.window_start)}–${hhmm(d.window_end)}` : ''
  }
  const unchanged = state.applied.length === 0

  return (
    <div>
      <div className="row" style={{ marginBottom: 12 }}>
        <div className="tally">
          {ORDER.filter((s) => s === 'kept' || diff.counts[s] > 0).map((s) => <StatusChip key={s} status={s} count={diff.counts[s]} />)}
        </div>
        <div className="spacer" />
        <div className="row" role="group" aria-label="View">
          <button className={`btn ${view === 'list' ? 'primary' : ''}`} aria-pressed={view === 'list'} onClick={() => setView('list')}>By delivery</button>
          <button className={`btn ${view === 'side' ? 'primary' : ''}`} aria-pressed={view === 'side'} onClick={() => setView('side')}>Side by side</button>
        </div>
      </div>
      {unchanged && <p className="muted" style={{ marginBottom: 10 }}>No changes yet. The revised plan matches the original.</p>}

      {view === 'list' ? (
        <>
          <table className="tbl">
            <thead><tr><th>Delivery</th><th>Window</th><th>Was</th><th>Now</th><th>Change</th><th>Why</th></tr></thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.delivery_id} className={c.completed ? 'done' : ''}>
                  <td><b>{c.delivery_id}</b><br /><span className="muted small">{place(c.delivery_id)}</span></td>
                  <td className="nw">{win(c.delivery_id)}</td>
                  <td className="nw">{c.old_vehicle ? <>{c.old_vehicle}<br /><span className="muted small">{hhmm(c.old_service)}</span></> : <span className="muted">not planned</span>}</td>
                  <td className="nw">{c.new_vehicle ? <>{c.new_vehicle}<br /><span className="muted small">{hhmm(c.new_service)}{c.old_service != null && c.new_service != null && Math.abs(c.new_service - c.old_service) >= 1 ? `, ${signed(c.new_service - c.old_service)}` : ''}</span></> : <span className="muted">no vehicle</span>}</td>
                  <td><StatusChip status={c.status} /></td>
                  <td className="reason">{c.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {done.length > 0 && (
            <button className="btn quiet" style={{ marginTop: 8 }} onClick={() => setShowDone(!showDone)}>
              {showDone ? 'Hide' : 'Show'} {done.length} already delivered
            </button>
          )}
        </>
      ) : (
        <div className="side">
          {[{ title: 'Original plan', routes: original.routes, which: 'old' as const }, { title: `Revised plan, as of ${hhmm(plan.as_of)}`, routes: plan.routes, which: 'new' as const }].map((col) => (
            <div key={col.title} className="sidecol">
              <h3>{col.title}</h3>
              {col.routes.map((r) => (
                <div key={r.vehicle_id} className="lane">
                  <span className="vid">{driverOf(scenario, r.vehicle_id)}</span>
                  {r.stops.length === 0 && <span className="muted small">No stops</span>}
                  {r.stops.map((s) => {
                    const c = byId.get(s.delivery_id)
                    const pick = s.kind === 'pickup'
                    let cls = ''
                    if (c && !c.completed) {
                      if (col.which === 'old') cls = c.status === 'moved' || c.status === 'broken' ? 'gone' : ''
                      else cls = c.status === 'moved' ? 'moved' : c.status === 'new' ? 'new' : ''
                    }
                    return <span key={`${s.kind}${s.delivery_id}`} className={`stopchip ${cls}`}
                      title={c?.reason}>{pick ? 'collect ' : ''}{s.delivery_id} {hhmm(s.service_start)}</span>
                  })}
                </div>
              ))}
              {col.which === 'new' && plan.unplaced.length > 0 && (
                <div className="lane"><span className="vid">Cannot be delivered</span>
                  {plan.unplaced.map((u) => <span key={u.delivery_id} className="stopchip broken" title={u.reason}>{u.delivery_id}</span>)}
                </div>
              )}
              {col.which === 'old' && <p className="muted small" style={{ marginTop: 8 }}>Faded stops were moved or could not be kept.</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
