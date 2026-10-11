import { useState } from 'react'
import { api, ApiError } from '../api'
import { Countdown } from '../components/Countdown'
import { RescueStatus } from '../components/RescueStatus'
import { StateChip, StatusChip } from '../components/ui'
import { hhmm, minutes } from '../format'
import type { Candidate, Incident, RescueConfig } from '../types'
import { useNotes, useOverview } from '../useRescue'
import { useDetour } from '../useDetour'

const NAME_KEY = 'detour.approver'

export default function Head() {
  const { connected } = useDetour()
  const ov = useOverview()
  const [role, setRole] = useState<'head' | 'backup'>(() => (new URLSearchParams(location.search).get('as') === 'backup' ? 'backup' : 'head'))
  const [name, setName] = useState(() => {
    try { return localStorage.getItem(NAME_KEY) ?? '' } catch { return '' }
  })
  const who = name.trim() || (role === 'head' ? 'Head of logistics' : 'Backup approver')
  const { notes } = useNotes(`role:${role}`)
  const cfg = ov.data?.config
  const incidents = ov.data?.incidents ?? []
  const waiting = incidents.filter((i) => i.state === 'AWAITING_HEAD')
  const running = incidents.filter((i) => ['HEAD_APPROVED', 'OFFER_PUSHED', 'CALL_ESCALATED', 'ACCEPTED', 'CANDIDATE_DECLINED'].includes(i.state))
  const finished = incidents.filter((i) => ['COMMITTED', 'EXHAUSTED', 'CANCELLED'].includes(i.state))

  return (
    <div className="phone wide">
      <header className="phonebar">
        <div className="seg" role="group" aria-label="Role">
          <button aria-pressed={role === 'head'} onClick={() => setRole('head')}>Head of logistics</button>
          <button aria-pressed={role === 'backup'} onClick={() => setRole('backup')}>Backup approver</button>
        </div>
        <label className="field" style={{ flex: 1 }}>Your name
          <input type="text" value={name} placeholder={who} onChange={(e) => { setName(e.target.value); try { localStorage.setItem(NAME_KEY, e.target.value) } catch { /* private mode */ } }} />
        </label>
        <span className="live" role="status"><span className={`dot ${connected ? 'on' : ''}`} /></span>
      </header>
      <main className="phonebody">
        {!cfg ? <p className="muted">{ov.error ? `Cannot reach the server: ${ov.error}` : 'Loading.'}</p> : (
          <>
            {waiting.length === 0 && running.length === 0 && (
              <section className="bigcard"><p className="offertext">Nothing needs your decision.</p>
                <p className="muted">When a driver reports a breakdown you will get an alert here with a ranked list of rescue drivers.</p></section>
            )}
            {waiting.map((i) => (
              <Decision key={`${i.id}-${i.proposal?.plan_version}`} inc={i} role={role} who={who} cfg={cfg} onChanged={ov.reload}
                alert={notes.find((n) => n.incident_id === i.id && n.kind === 'head_alert')?.text.en} />
            ))}
            {running.map((i) => (
              <section key={i.id} className="bigcard"><h2 className="h">Rescue in progress</h2><RescueStatus inc={i} cfg={cfg} /></section>
            ))}
            {finished.length > 0 && (
              <section aria-labelledby="done-h2"><h2 className="h" id="done-h2">Finished</h2>
                <ul className="feed">{finished.map((i) => <li key={i.id}><StateChip state={i.state} /> <b>{i.vehicle_id}</b> {i.result}</li>)}</ul></section>
            )}
          </>
        )}
      </main>
    </div>
  )
}

function Decision({ inc, role, who, cfg, onChanged, alert }: {
  inc: Incident; role: 'head' | 'backup'; who: string; cfg: RescueConfig; onChanged: () => void; alert?: string
}) {
  const p = inc.proposal
  const feasible = p?.candidates.filter((c) => c.feasible) ?? []
  const rejected = p?.candidates.filter((c) => !c.feasible) ?? []
  const [sel, setSel] = useState<string[]>(() => feasible.slice(0, cfg.max_shortlist).map((c) => c.vehicle_id))
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  if (!p) return null

  const toggle = (v: string) => setSel((s) => (s.includes(v) ? s.filter((x) => x !== v) : s.length >= cfg.max_shortlist ? s : [...s, v]))
  const move = (v: string, d: -1 | 1) => setSel((s) => {
    const i = s.indexOf(v), j = i + d
    if (i < 0 || j < 0 || j >= s.length) return s
    const n = [...s]; [n[i], n[j]] = [n[j], n[i]]; return n
  })

  async function approve() {
    setBusy(true); setErr(null)
    try { await api.approve(inc.id, { approved_by: who, shortlist: sel, proposal_version: p!.plan_version, role }) }
    catch (e) { setErr(e instanceof ApiError ? e.message : 'Could not reach the server') }
    finally { setBusy(false); onChanged() }
  }
  async function reject() {
    setBusy(true)
    try { await api.rejectIncident(inc.id, who) } finally { setBusy(false); onChanged() }
  }

  return (
    <section className="bigcard attention" aria-labelledby={`d-${inc.id}`}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h2 className="h" id={`d-${inc.id}`} style={{ marginBottom: 2 }}>{inc.vehicle_id} ({inc.driver}) broke down at {inc.location_name}</h2>
          {alert && <p className="muted small">{alert}</p>}
        </div>
        {inc.head_deadline && <Countdown deadline={inc.head_deadline} total={cfg.head_response} label="s left" size={84} />}
      </div>
      {inc.approver_role === 'backup' && <p className="notice warn" style={{ margin: '8px 0' }}>The head did not respond in time, so this came to the backup approver.</p>}
      {inc.escalated_to_dispatcher && <p className="notice err" style={{ margin: '8px 0' }}>Nobody has approved yet. The dispatcher has been alerted.</p>}

      <div className="quote"><b>The driver said:</b> “{inc.transcript || 'Used the buttons'}”
        <div className="small muted">Read back and confirmed by the driver: {inc.readback.en}</div></div>

      <p style={{ margin: '10px 0 4px' }}>
        Main parcel <b>{p.primary}</b> for {p.primary_place}, due <b>{hhmm(p.primary_due)}</b>.
        {p.parcels.length > 1 && <> Also on the vehicle: {p.parcels.filter((x) => x !== p.primary).join(', ')}.</>}
      </p>

      {feasible.length === 0 ? (
        <p className="notice err">No driver can deliver {p.primary} in time. If you confirm, it will be marked undeliverable and the customer will need to be told.</p>
      ) : (
        <>
          <h3 className="h" style={{ marginTop: 14 }}>Choose up to {cfg.max_shortlist}, in the order to ask them</h3>
          <ol className="cands">
            {feasible.map((c) => (
              <CandidateRow key={c.vehicle_id} c={c} checked={sel.includes(c.vehicle_id)} order={sel.indexOf(c.vehicle_id) + 1}
                onToggle={() => toggle(c.vehicle_id)} onUp={() => move(c.vehicle_id, -1)} onDown={() => move(c.vehicle_id, 1)} />
            ))}
          </ol>
        </>
      )}

      {rejected.length > 0 && (
        <details style={{ marginTop: 10 }}>
          <summary>{rejected.length} not possible</summary>
          <ul>{rejected.map((c) => <li key={c.vehicle_id}><b>{c.driver} ({c.vehicle_id}):</b> {c.reason}</li>)}</ul>
        </details>
      )}

      {err && <p className="notice err" role="alert" style={{ marginTop: 10 }}>{err}</p>}
      <div className="twobtn" style={{ marginTop: 14 }}>
        <button className="btn primary huge" disabled={busy || (feasible.length > 0 && sel.length === 0)} onClick={approve}>
          {feasible.length === 0 ? 'Confirm: nobody can' : `Approve ${sel.length} driver${sel.length === 1 ? '' : 's'}`}
        </button>
        <button className="btn huge" disabled={busy} onClick={reject}>Reject</button>
      </div>
      <p className="small muted" style={{ marginTop: 8 }}>
        Your approval covers exactly these drivers and this plan. If the plan changes first, it is void and you will be asked again.
        Nothing is promised to anyone until a driver accepts.
      </p>
    </section>
  )
}

function CandidateRow({ c, checked, order, onToggle, onUp, onDown }: {
  c: Candidate; checked: boolean; order: number; onToggle: () => void; onUp: () => void; onDown: () => void
}) {
  const impact = c.impact
  return (
    <li className={`cand ${checked ? 'on' : ''}`}>
      <label className="candmain">
        <input type="checkbox" checked={checked} onChange={onToggle} aria-label={`Ask ${c.driver}`} />
        <span className="rank">{c.rank}</span>
        <span style={{ flex: 1 }}>
          <b>{c.driver} ({c.vehicle_id})</b>
          <span className="muted small" style={{ display: 'block' }}>
            Reaches the van {hhmm(c.reach_site)}, leaves {hhmm(c.leave_site)}, delivers at <b>{hhmm(c.delivery_time)}</b>
          </span>
          <span className="small" style={{ display: 'block' }}>
            {c.own_delay ? `Delays their own deliveries by up to ${minutes(c.own_delay)}.` : 'Their own deliveries are not delayed.'}
            {impact && (impact.moved > 0 || impact.broken > 0) && ` Elsewhere: ${impact.moved} moved, ${impact.broken} cannot be delivered.`}
          </span>
        </span>
      </label>
      {checked && <span className="orderbtns">
        <button className="btn quiet" onClick={onUp} aria-label={`Ask ${c.driver} earlier`}>▲</button>
        <span className="nums small">{order}</span>
        <button className="btn quiet" onClick={onDown} aria-label={`Ask ${c.driver} later`}>▼</button>
      </span>}
      {c.other_changes.length > 0 && (
        <details className="small">
          <summary>Other deliveries affected</summary>
          <ul>{c.other_changes.map((o) => <li key={o.delivery_id}><StatusChip status={o.status as 'moved' | 'broken' | 'new'} /> <b>{o.delivery_id}</b> {o.reason}</li>)}</ul>
        </details>
      )}
    </li>
  )
}
