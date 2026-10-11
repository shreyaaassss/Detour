import { api } from '../api'
import { hhmm } from '../format'
import type { Incident, IncidentState, RescueConfig } from '../types'
import { STATE_LABEL } from '../labels'
import { Countdown } from './Countdown'
import { StateChip } from './ui'

const CALL_OUTCOMES: [string, string][] = [
  ['answered', 'Picks up'], ['confirmed', 'Says confirm'], ['declined', 'Says no'],
  ['no_answer', 'No answer'], ['voicemail', 'Voicemail'], ['ambiguous', 'Unclear'],
]

/** Where one rescue stands, live: who is being asked, how long they have, and what has happened. */
export function RescueStatus({ inc, cfg, simulate = false }: { inc: Incident; cfg: RescueConfig; simulate?: boolean }) {
  const o = inc.active_offer
  const done = ['COMMITTED', 'EXHAUSTED', 'CANCELLED', 'REJECTED'].includes(inc.state)
  return (
    <div className="stack">
      <div className="row"><StateChip state={inc.state} />
        <b>{inc.vehicle_id} ({inc.driver})</b>
        {inc.location_name && <span className="muted">at {inc.location_name}</span>}
      </div>
      {o && (
        <div className="row" style={{ gap: 14 }}>
          {o.channel === 'push' && <Countdown deadline={o.deadline} total={cfg.push_timeout} label="s left" size={84} />}
          {o.channel === 'call' && o.call_state === 'ringing' && <Countdown deadline={o.deadline} total={o.deadline - o.sent} label="s ringing" size={84} />}
          {o.channel === 'call' && o.call_state === 'in_call' && <Countdown deadline={o.conversation_deadline} total={cfg.conversation_limit} label="s on call" size={84} />}
          <div>
            <b>{o.channel === 'push' ? 'App offer' : 'Phone call'} to {o.driver} ({o.vehicle_id})</b>
            <div className="muted small">Driver {inc.current + 1} of {inc.shortlist.length}: {inc.shortlist.join(', ')}</div>
            {o.channel === 'call' && <div className="muted small">{o.call_state === 'in_call' ? 'In the call' : 'Ringing'}</div>}
          </div>
        </div>
      )}
      {simulate && o?.channel === 'call' && (
        <div>
          <p className="small muted">Simulate the call, for a demo without a phone:</p>
          <div className="row" style={{ marginTop: 6 }}>
            {CALL_OUTCOMES.map(([k, label]) => (
              <button key={k} className="btn" onClick={() => api.callEvent(o.id, k).catch(() => {})}>{label}</button>
            ))}
          </div>
        </div>
      )}
      {inc.result && <p className={`notice ${inc.state === 'COMMITTED' ? 'ok' : 'warn'}`}>{inc.result}</p>}
      {!inc.result && inc.note && done && <p className="notice warn">{inc.note}</p>}
      <details>
        <summary>What happened so far</summary>
        <ul>
          {inc.history.map((h, i) => (
            <li key={i}><b>{STATE_LABEL[h.state as IncidentState] ?? h.state}</b>{h.note ? `: ${h.note}` : ''}{h.sim != null ? ` (plan ${hhmm(h.sim)})` : ''}</li>
          ))}
        </ul>
      </details>
    </div>
  )
}
