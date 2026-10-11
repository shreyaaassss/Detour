import { nameOf } from '../format'
import type { ParseInfo, PreviewResult, Scenario, Status } from '../types'
import { Glyph, StatusChip } from './ui'

interface Props {
  preview: PreviewResult
  scenario: Scenario
  stale: boolean
  busy: boolean
  error: string | null
  parse: ParseInfo | null
  onApply: () => void
  onDiscard: () => void
  onEdit: () => void
}

const ORDER: Status[] = ['broken', 'moved', 'new', 'kept']

export function PreviewPanel({ preview, scenario, stale, busy, error, parse, onApply, onDiscard, onEdit }: Props) {
  const interesting = preview.diff.changes.filter((c) => c.status !== 'kept' && !c.completed)
  const place = (id: string) => {
    const d = scenario.deliveries.find((x) => x.id === id)
    return d ? nameOf(scenario, d.location) : ''
  }
  const cause = preview.cause.charAt(0).toUpperCase() + preview.cause.slice(1)
  const ok = preview.report.valid && !stale

  return (
    <section className="sec" aria-labelledby="prev-h">
      <div className="preview">
        <h2 className="h" id="prev-h">Review before applying</h2>
        {parse && (
          <div className="understood" style={{ marginBottom: 12 }}>
            <p className="small muted">
              {parse.method === 'llm' ? `Read by ${parse.model}, checked against your places and vehicles` : 'Read by rules, no AI'}.
              Check that this is what you meant:
            </p>
            <p><b>{parse.summary}</b></p>
            {parse.warnings.map((w) => <p key={w} className="notice warn small" style={{ marginTop: 6 }}>{w}</p>)}
            <button className="btn quiet" onClick={onEdit} style={{ paddingLeft: 0 }}>Edit the details</button>
          </div>
        )}
        {!parse && <p>{cause}.</p>}
        <div className="tally" style={{ marginTop: 10 }}>
          {ORDER.filter((s) => s === 'kept' || preview.diff.counts[s] > 0).map((s) => (
            <StatusChip key={s} status={s} count={preview.diff.counts[s]} />
          ))}
        </div>
        <div className="changes">
          {interesting.length === 0 ? <p className="muted">Every remaining delivery keeps its vehicle and time.</p> : (
            <ul>
              {interesting.sort((a, b) => ORDER.indexOf(a.status) - ORDER.indexOf(b.status)).map((c) => (
                <li key={c.delivery_id}>
                  <div className="row"><StatusChip status={c.status} /><b>{c.delivery_id}</b><span className="muted">{place(c.delivery_id)}</span></div>
                  <p className="small muted" style={{ marginTop: 2 }}>{c.reason}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
        {preview.report.valid
          ? <p className="notice ok"><Glyph name="ok" size={12} /> The independent validator passed this plan.</p>
          : <p className="notice err">The validator rejected this plan, so it cannot be applied.</p>}
        {stale && <p className="notice warn" style={{ marginTop: 8 }}>The plan changed while you were reviewing. Discard this and review again.</p>}
        {error && <p className="notice err" role="alert" style={{ marginTop: 8 }}>{error}</p>}
        <div className="row" style={{ marginTop: 14 }}>
          <button className="btn primary" disabled={!ok || busy} onClick={onApply}>Apply change</button>
          <button className="btn" onClick={onDiscard} disabled={busy}>Discard</button>
        </div>
      </div>
    </section>
  )
}
