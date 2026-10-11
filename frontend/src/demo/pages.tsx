import { useEffect, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ComparePanel } from '../components/ComparePanel'
import { Countdown } from '../components/Countdown'
import { RouteLanes } from '../components/RouteLanes'
import { StatusChip } from '../components/ui'
import { hhmm } from '../format'
import { LINES, useDemo } from './store'
import { SayBox } from './SayBox'

function Head({ who, title, children }: { who: string; title: string; children?: ReactNode }) {
  return (
    <header className="dhead">
      <p className="show-who">{who}</p>
      <h1 className="show-title">{title}</h1>
      {children && <p className="show-explain">{children}</p>}
    </header>
  )
}
function Bubble({ who, children }: { who: string; children: ReactNode }) {
  return <div className="turn said"><p className="turn-who">{who}</p><blockquote>{children}</blockquote></div>
}
function Card({ label, tone, children }: { label: string; tone?: 'refuse' | 'good'; children: ReactNode }) {
  return <div className={`turn sys ${tone ?? ''}`}><p className="turn-who">{label}</p>{children}</div>
}
/** Keep the newest turn in view, as a chat does. */
function useFollow(...deps: unknown[]) {
  useEffect(() => {
    const id = setTimeout(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' }), 120)
    return () => clearTimeout(id)
  }, deps) // eslint-disable-line react-hooks/exhaustive-deps
}
/** What a page shows when the story has not reached it yet. */
function NotYet({ text, to, go }: { text: string; to: string; go: string }) {
  return <div className="notyet"><p>{text}</p><Link to={to} className="btn primary big">{go}</Link></div>
}

export function PlanPage() {
  const d = useDemo()
  const s = d.state!
  if (!s.plan) return null
  const changed = s.applied.length > 0
  return (
    <section className="show-scene">
      <Head who="Dispatcher's board" title={changed ? 'The plan, as it stands now' : 'The day is planned'}>
        Five vehicles and twelve deliveries, each assigned within capacity and its time window. Every stop shows its arrival time and any waiting.
      </Head>
      <RouteLanes key={s.version} scenario={s.scenario} plan={s.plan} changes={s.diff?.changes} />
      <section className="how">
        <h2 className="h">How this plan is built, and its limits</h2>
        <p>{s.plan.solver}. Total driving: {Math.round(s.plan.total_travel)} min.</p>
        <ul>{s.plan.limits.map((l) => <li key={l}>{l}</li>)}</ul>
      </section>
    </section>
  )
}

export function DriverPage() {
  const d = useDemo()
  const i = d.incident
  useFollow(d.phase, d.said)
  return (
    <section className="show-feed">
      <Head who="Ravi's phone, driver of V2" title="Report a breakdown">
        Speak or type what happened. The system reads it back and waits for a yes. It never guesses a place it does not know.
      </Head>
      {d.phase === 0 && !d.said && <Card label="DeTour"><p className="turn-big">What happened?</p></Card>}
      {d.said && <Bubble who="Ravi">“{d.said}”</Bubble>}

      {d.phase === 1 && i && (
        <Card label="DeTour" tone="refuse">
          <p className="turn-big">{i.note}</p>
          <p className="muted">Choose the place, or say it again.</p>
          <div className="places">
            {i.known_locations.filter((l) => l.id !== 'depot').map((l) => (
              <button key={l.id} className="btn" disabled={d.busy} onClick={() => d.report(d.said ?? LINES.breakdown, l.id)}>{l.name}</button>
            ))}
          </div>
        </Card>
      )}

      {i && d.phase >= 2 && (
        <Card label="DeTour reads it back">
          <p className="turn-big">{i.readback.en}</p>
          <p className="muted">Place matched: <b>{i.location_name}</b>. Vehicle <b>{i.vehicle_id}</b>. Parcels aboard: <b>{i.parcels.join(', ') || 'none'}</b>.</p>
          {d.phase === 2 && (
            <div className="turn-actions">
              <button className="btn primary big" disabled={d.busy} onClick={() => d.confirmReport(true)}>Yes, that is correct</button>
              <button className="btn big" disabled={d.busy} onClick={() => d.confirmReport(false)}>No, that is wrong</button>
            </div>
          )}
        </Card>
      )}
      {i && d.phase >= 3 && <Bubble who="Ravi">“Yes, that is correct”</Bubble>}
      {i && d.phase === 3 && <Card label="DeTour"><p className="turn-big">Your report has gone to logistics. Stay with the vehicle.</p><p className="muted">Nobody has been promised yet, so you are not told help is coming.</p></Card>}
      {i && d.phase === 4 && <Card label="DeTour"><p className="turn-big">Logistics approved a rescue. A driver is being asked now.</p></Card>}
      {i && d.phase === 5 && (
        <Card label="DeTour" tone={i.state === 'COMMITTED' ? 'good' : 'refuse'}>
          <p className="turn-big">{i.state === 'COMMITTED' ? `Help is on the way. ${i.offers.find((o) => o.status === 'accepted')?.driver ?? 'A driver'} is coming to collect your parcels.` : 'No rescue driver is available right now. Logistics will contact you.'}</p>
          <p className="muted">You are only told this once a driver has actually accepted.</p>
        </Card>
      )}

      {d.phase <= 1 && (
        <div className="say-dock">
          <SayBox suggestions={[LINES.breakdown]} busy={d.busy} placeholder="Speak, or type what the driver says" onSay={(t) => d.report(t)} />
        </div>
      )}
    </section>
  )
}

export function HeadPage() {
  const d = useDemo()
  const p = d.proposal
  if (d.phase < 3 || !p) return (
    <section className="show-feed">
      <Head who="Head of logistics" title="Nothing needs your decision" />
      <NotYet text="When a driver reports a breakdown and confirms it, a ranked list of rescue drivers appears here." to="/demo/driver" go="Go to Driver" />
    </section>
  )
  return (
    <section className="show-feed">
      <Head who="Head of logistics" title={`${d.incident!.vehicle_id} broke down at ${d.incident!.location_name}`}>
        Urgent parcel {p.primary} is due at {p.primary_place} by {hhmm(p.primary_due)}. The engine ranked who can collect it and still deliver on time. Choose up to three, in the order to ask them.
      </Head>
      <ol className="show-cands">
        {p.candidates.map((c) => {
          const on = d.chosen.includes(c.vehicle_id)
          return (
            <li key={c.vehicle_id} className={`${c.feasible ? '' : 'out'} ${on ? 'on' : ''}`}>
              {c.feasible ? (
                <input type="checkbox" checked={on} disabled={d.phase !== 3 || d.busy} aria-label={`Ask ${c.driver}`}
                  onChange={() => d.setPicks(on ? d.chosen.filter((v) => v !== c.vehicle_id) : [...d.chosen, c.vehicle_id].slice(0, 3))} />
              ) : <span className="rank">✕</span>}
              <div>
                <b>{c.driver} ({c.vehicle_id})</b>
                {c.feasible
                  ? <p>Reaches the van {hhmm(c.reach_site)}, leaves {hhmm(c.leave_site)}, delivers {p.primary} at <b>{hhmm(c.delivery_time)}</b> (due {hhmm(p.primary_due)}).</p>
                  : <p>Ruled out: {c.reason}</p>}
              </div>
            </li>
          )
        })}
      </ol>
      {d.phase === 3 ? (
        <div className="turn-actions">
          <button className="btn primary big" disabled={d.busy || d.chosen.length === 0} onClick={d.approve}>Approve {d.chosen.length} {d.chosen.length === 1 ? 'driver' : 'drivers'}</button>
        </div>
      ) : <Card label="Decision recorded" tone="good"><p className="turn-big">Approved by {d.incident!.approved_by}.</p><p className="muted">If the plan changes before anyone accepts, this approval is void and you are asked again.</p></Card>}
    </section>
  )
}

export function RescuePage() {
  const d = useDemo()
  const i = d.incident
  if (!i || d.phase < 4) return (
    <section className="show-feed">
      <Head who="Rescue driver's phone" title="No offers right now" />
      <NotYet text="An offer appears here once the head of logistics approves a shortlist." to={d.phase === 3 ? '/demo/head' : '/demo/driver'} go={d.phase === 3 ? 'Go to Head of logistics' : 'Go to Driver'} />
    </section>
  )
  const who = d.offer?.driver ?? i.offers.at(-1)?.driver ?? 'Rescue driver'
  return (
    <section className="show-feed">
      <Head who={`${who}'s phone`} title={d.offer ? 'A rescue is being asked of you' : 'This request is settled'}>
        One driver is asked at a time, with 60 seconds to answer. Only one can claim it. A late tap is refused.
      </Head>
      {i.offers.map((o) => {
        const open = o.status === 'open'
        return (
          <Card key={o.id} label={o.channel === 'call' ? `Calling ${o.driver}: no answer in the app` : `Offer to ${o.driver}`} tone={o.status === 'accepted' ? 'good' : undefined}>
            <div className="offer">
              <div>
                <p className="turn-big">{o.text.en}</p>
                {!open && <p className="muted">{o.status === 'accepted' ? `${o.driver} accepted.` : `${o.outcome ?? o.status}. The next driver was asked.`}</p>}
              </div>
              {open && d.cfg && <Countdown deadline={o.call_state === 'in_call' ? o.conversation_deadline : o.deadline} total={o.channel === 'call' ? o.deadline - o.sent : d.cfg.push_timeout} label="seconds left" size={88} />}
            </div>
            {open && (
              <div className="turn-actions">
                <button className="btn primary big" disabled={d.busy} onClick={() => d.answer(o, true)}>{o.channel === 'call' ? 'Answers: confirm' : 'Accept'}</button>
                <button className="btn big" disabled={d.busy} onClick={() => d.answer(o, false)}>{o.channel === 'call' ? 'Answers: no' : 'Decline'}</button>
              </div>
            )}
          </Card>
        )
      })}
    </section>
  )
}

export function ChangesPage() {
  const d = useDemo()
  const s = d.state!
  const mark = d.markChangesSeen
  const settled = d.phase === 5
  useEffect(() => { if (settled) mark() }, [settled]) // eslint-disable-line react-hooks/exhaustive-deps
  if (s.applied.length === 0) return (
    <section className="show-feed">
      <Head who="Dispatcher's board" title="Nothing has changed yet" />
      <NotYet text="Once a rescue is committed, or the dispatcher applies a change, the original and revised plans appear here side by side." to="/demo/driver" go="Go to Driver" />
    </section>
  )
  return (
    <section className="show-scene">
      <Head who="Dispatcher's board" title="What changed, and why">
        Every delivery is kept, moved or broken, with a reason the dispatcher can give a customer. Completed stops stay fixed, and a failed vehicle gets no stops after it failed.
      </Head>
      <ComparePanel key={s.version} state={s} />
    </section>
  )
}

export function DispatcherPage() {
  const d = useDemo()
  const s = d.state!
  const applied = d.turns.some((t) => t.applied)
  useFollow(d.turns)
  return (
    <section className="show-feed">
      <Head who="Dispatcher" title="Report a change">
        A road closure or an urgent delivery, spoken or typed in plain words. AI turns it into a structured change, a strict rule reader checks it, and nothing applies until you confirm.
      </Head>
      {d.turns.length === 0 && <Card label="DeTour"><p className="turn-big">What changed?</p></Card>}
      {d.turns.map((t) => (
        <div key={t.id} className="turn-group">
          <Bubble who="Dispatcher">“{t.text}”</Bubble>
          {t.refusal && <Card label="Refused" tone="refuse"><p className="turn-big">{t.refusal}</p><p className="muted">Nothing was changed.</p></Card>}
          {t.preview && (
            <Card label={t.parse ? (t.parse.method === 'llm' ? `Read by ${t.parse.model}, then checked by rules` : 'Read by the rule reader') : 'Entered with the form'} tone={t.applied ? 'good' : undefined}>
              <p className="turn-big">{t.parse?.summary ?? t.preview.cause}</p>
              <div className="tally">
                {(['broken', 'moved', 'new', 'kept'] as const).filter((x) => t.preview!.diff.counts[x] > 0).map((x) => <StatusChip key={x} status={x} count={t.preview!.diff.counts[x]} />)}
              </div>
              {t.applied ? <p className="muted">Applied by the dispatcher.</p> : t.discarded ? <p className="muted">Discarded. Nothing was changed.</p> : (
                <>
                  <p className="muted">This is a preview. Nothing changes until you confirm.</p>
                  <div className="turn-actions">
                    <button className="btn primary big" disabled={d.busy} onClick={() => d.settle(t, true)}>Confirm and apply</button>
                    <button className="btn big" disabled={d.busy} onClick={() => d.settle(t, false)}>Discard</button>
                  </div>
                </>
              )}
            </Card>
          )}
        </div>
      ))}
      <div className="say-dock">
        <SayBox suggestions={[LINES.unknown, LINES.closure]} busy={d.busy} placeholder="Speak, or type what changed" onSay={d.dispatchSay} />
        <button className="btn" disabled={d.busy} onClick={d.urgent}>Add urgent delivery D13</button>
      </div>
      {applied && <div className="turn wide"><ComparePanel key={s.version} state={s} /></div>}
    </section>
  )
}
