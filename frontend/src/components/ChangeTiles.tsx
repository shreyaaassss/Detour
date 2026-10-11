import { driverOf, hhmm, nameOf, signed } from '../format'
import type { AppState, Change, Status } from '../types'
import { ComparePanel } from './ComparePanel'
import { Glyph } from './ui'

const MEANING: Record<Status, [string, string]> = {
  kept: ['Kept', 'delivered exactly as planned'],
  moved: ['Moved', 'a different vehicle or time'],
  broken: ['Broken', 'cannot be delivered in its window'],
  new: ['New', 'added during the day'],
}
const ORDER: Status[] = ['kept', 'moved', 'broken', 'new']

/** What changed, as tiles: the count of each outcome, then one tile per delivery that changed, with its reason.
 * The full side-by-side comparison is one click away. */
export function ChangeTiles({ state }: { state: AppState }) {
  const { diff, scenario } = state
  if (!diff) return null
  const dlv = (id: string) => scenario.deliveries.find((d) => d.id === id)
  const changed = diff.changes
    .filter((c) => c.status !== 'kept')
    .sort((a, b) => ['broken', 'moved', 'new'].indexOf(a.status) - ['broken', 'moved', 'new'].indexOf(b.status) || a.delivery_id.localeCompare(b.delivery_id, undefined, { numeric: true }))
  const kept = diff.changes.filter((c) => c.status === 'kept').sort((a, b) => a.delivery_id.localeCompare(b.delivery_id, undefined, { numeric: true }))
  const where = (c: Change, which: 'old' | 'new') => {
    const v = which === 'old' ? c.old_vehicle : c.new_vehicle
    const t = which === 'old' ? c.old_service : c.new_service
    return v ? <><b>{driverOf(scenario, v)}</b><span>{hhmm(t)}</span></> : <><b>{which === 'old' ? 'Not planned' : 'No vehicle'}</b><span>{which === 'new' ? 'not delivered' : ''}</span></>
  }

  return (
    <div className="tiles">
      <div className="tile-row sum" role="list" aria-label="Summary">
        {ORDER.filter((s) => s !== 'new' || diff.counts.new > 0).map((s) => (
          <div key={s} role="listitem" className={`tile sum-tile ${s}`}>
            <span className="num">{diff.counts[s]}</span>
            <span className="lab"><Glyph name={s} size={14} /> {MEANING[s][0]}</span>
            <span className="say">{MEANING[s][1]}</span>
          </div>
        ))}
      </div>

      {changed.length > 0 && (
        <>
          <h2 className="tile-h">The deliveries that changed</h2>
          <div className="tile-row">
            {changed.map((c) => {
              const d = dlv(c.delivery_id)
              const shift = c.old_service != null && c.new_service != null && Math.abs(c.new_service - c.old_service) >= 1 ? signed(c.new_service - c.old_service) : null
              return (
                <article key={c.delivery_id} className={`tile chg ${c.status}`}>
                  <header>
                    <span className="id">{c.delivery_id}</span>
                    <span className={`chip ${c.status}`}><Glyph name={c.status} size={12} /> {MEANING[c.status][0]}</span>
                  </header>
                  <p className="to">{nameOf(scenario, d?.location)}{d ? `, due ${hhmm(d.window_start)} to ${hhmm(d.window_end)}` : ''}</p>
                  <div className="swap">
                    <div className="was"><small>Was</small>{where(c, 'old')}</div>
                    <span className="arrow" aria-hidden="true">→</span>
                    <div className="now"><small>Now{shift ? ` (${shift})` : ''}</small>{where(c, 'new')}</div>
                  </div>
                  <p className="why">{c.reason}</p>
                </article>
              )
            })}
          </div>
        </>
      )}

      {kept.length > 0 && (
        <>
          <h2 className="tile-h">Kept as planned</h2>
          <div className="tile-row mini">
            {kept.map((c) => (
              <div key={c.delivery_id} className={`tile mini-tile ${c.completed ? 'done' : ''}`}>
                <b>{c.delivery_id}</b><span>{c.new_vehicle ?? c.old_vehicle} at {hhmm(c.new_service ?? c.old_service)}</span>
              </div>
            ))}
          </div>
        </>
      )}

      <details className="fullcompare">
        <summary>Compare the two plans in full, route by route</summary>
        <ComparePanel state={state} />
      </details>
    </div>
  )
}
