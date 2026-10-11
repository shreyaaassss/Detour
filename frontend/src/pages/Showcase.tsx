import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api'
import { ComparePanel } from '../components/ComparePanel'
import { RouteLanes } from '../components/RouteLanes'
import { StatusChip } from '../components/ui'
import { hhmm } from '../format'
import { Wordmark } from '../site/SiteChrome'
import type { AppState, Incident, ParseInfo, PreviewResult, Proposal } from '../types'

/* The guided demo. The script (who says what, in what order) is fixed, so it runs the same way every time.
 * Nothing shown is canned: every step sends its line to the real server and shows what the engine answered. */

const SAY = {
  breakdown: 'My truck broke down near Hadapsar',
  unknown: 'The road between Kothrud and Mumbai is closed until 4 pm',
  closure: 'The road between Kothrud and Aundh is slow until 4 pm, it adds 25 minutes',
}

interface Data {
  state?: AppState
  incident?: Incident
  proposal?: Proposal
  refusal?: string
  parse?: ParseInfo
  preview?: PreviewResult
  usedForm?: boolean
}

type View = 'plan' | 'readback' | 'shortlist' | 'offer' | 'compare' | 'refused' | 'understood'

interface Step {
  who: string
  title: string
  line?: string // what the person says or types
  explain: string // why this step matters
  view: View
  run: (d: Data) => Promise<Partial<Data>>
}

const STEPS: Step[] = [
  {
    who: 'Morning', title: 'The day is planned', view: 'plan',
    explain: 'Deliveries are assigned to vehicles within capacity and time windows. Each stop shows its arrival time and any waiting.',
    run: async () => ({ state: await api.reset(), incident: undefined, proposal: undefined, preview: undefined, parse: undefined, refusal: undefined }),
  },
  {
    who: 'Ravi, driver of V2', title: 'A driver reports a breakdown', line: SAY.breakdown, view: 'readback',
    explain: 'The report is read and matched to a known place. The system reads it back and waits for the driver to confirm.',
    run: async () => ({ incident: (await api.report({ driver: 'Ravi', transcript: SAY.breakdown, language: 'en' })).incident }),
  },
  {
    who: 'Ravi, driver of V2', title: 'The driver confirms', line: 'Yes, that is correct', view: 'shortlist',
    explain: 'The engine ranks who can collect the stranded parcels and still deliver on time. A vehicle that would be late is ruled out, with the reason.',
    run: async (d) => {
      const incident = (await api.confirmReport(d.incident!.id, { confirmed: true })).incident
      return { incident, proposal: (await api.proposal(incident.id)).proposal }
    },
  },
  {
    who: 'Head of logistics', title: 'A person approves the shortlist', line: 'Approve these drivers, in this order', view: 'offer',
    explain: 'Nothing is sent to any driver until a person approves. The first driver then gets 60 seconds to answer.',
    run: async (d) => {
      const shortlist = d.proposal!.candidates.filter((c) => c.feasible).slice(0, 3).map((c) => c.vehicle_id)
      const r = await api.approve(d.incident!.id, { approved_by: 'Head of logistics', shortlist, proposal_version: d.proposal!.plan_version, role: 'head' })
      return { incident: r.incident }
    },
  },
  {
    who: 'Meera, driver of V4', title: 'The rescue driver accepts', line: 'Accept', view: 'compare',
    explain: 'Only now does the plan change. Every delivery is kept, moved or broken, with a reason. Completed stops stay fixed, and the failed vehicle gets no further stops.',
    run: async (d) => {
      const offer = d.incident!.active_offer
      if (!offer) throw new ApiError(409, 'no_offer', 'The offer is no longer open. Restart the demo.')
      const incident = (await api.respond(offer.id, 'accept', offer.driver ?? undefined)).incident
      return { incident, state: await api.state() }
    },
  },
  {
    who: 'Dispatcher', title: 'A report names a place we do not know', line: SAY.unknown, view: 'refused',
    explain: 'An unknown location is rejected, never guessed. Nothing changes.',
    run: async () => {
      try {
        await api.parseReport(SAY.unknown)
        return { refusal: 'The report was accepted, which was not expected.' }
      } catch (e) {
        if (e instanceof ApiError && e.status === 422) return { refusal: e.message }
        throw e
      }
    },
  },
  {
    who: 'Dispatcher', title: 'A road closure, typed in plain words', line: SAY.closure, view: 'understood',
    explain: 'AI turns the sentence into a structured change, a strict rule reader checks it, and the effect is shown. Nothing applies until the dispatcher confirms.',
    run: async (d) => {
      try {
        const r = await api.parseReport(SAY.closure)
        return { parse: r.parse, preview: r.preview, usedForm: false }
      } catch (e) {
        if (!(e instanceof ApiError) || e.status !== 422) throw e
        // the sentence could not be read just now: enter the same closure with the form instead, and say so
        const now = d.state?.as_of ?? 845
        const preview = await api.preview({ type: 'road_closure', a: 'kothrud', b: 'aundh', start: now, end: 960, added_minutes: 25, reported_at: now })
        return { preview, parse: undefined, usedForm: true }
      }
    },
  },
  {
    who: 'Dispatcher', title: 'The dispatcher confirms', line: 'Apply this change', view: 'compare',
    explain: 'The closure slows only the legs that depart inside it. The two plans are shown side by side.',
    run: async (d) => ({ state: await api.confirm(d.preview!.preview_id, 'Dispatcher'), preview: undefined }),
  },
  {
    who: 'Dispatcher', title: 'An urgent delivery arrives', line: 'Urgent parcel D13 to Wanowrie by 15:00', view: 'compare',
    explain: 'The new parcel is fitted in where it disturbs the least. If it cannot be delivered in time, that is reported with the reason.',
    run: async () => {
      const presets = await api.presets()
      const p = await api.preview(presets.urgent_delivery)
      return { state: await api.confirm(p.preview_id, 'Dispatcher') }
    },
  },
]

async function withWake<T>(fn: () => Promise<T>, onWait: (s: string | null) => void): Promise<T> {
  // a free server sleeps when idle: keep trying for up to 90 seconds while it wakes
  const started = Date.now()
  for (;;) {
    try {
      const r = await fn()
      onWait(null)
      return r
    } catch (e) {
      const asleep = !(e instanceof ApiError) || e.status >= 502 || e.code === 'bad_response'
      if (!asleep || Date.now() - started > 90_000) { onWait(null); throw e }
      onWait('Waking the server. This takes up to a minute the first time.')
      await new Promise((r) => setTimeout(r, 3000))
    }
  }
}

export default function Showcase() {
  const [done, setDone] = useState(0) // how many steps have run
  const [data, setData] = useState<Data>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [waiting, setWaiting] = useState<string | null>(null)
  const started = useRef(false)
  const stage = useRef<HTMLDivElement>(null)

  const runStep = useCallback(async (i: number, d: Data) => {
    setBusy(true); setError(null)
    try {
      let patch: Partial<Data>
      let base = d
      try {
        patch = await withWake(() => STEPS[i].run(d), setWaiting)
      } catch (e) {
        // The server lost the story so far (it restarted, or someone else reset the shared demo). The script is
        // fixed, so replay it from the start up to this step, then carry on. Anything else is a real error.
        const lost = e instanceof ApiError && [404, 409, 410].includes(e.status)
        if (!lost || i === 0) throw e
        setWaiting('Catching up. The demo was reset elsewhere, so the earlier steps are being replayed.')
        base = {}
        for (let k = 0; k < i; k++) base = { ...(k === 0 ? {} : base), ...(await withWake(() => STEPS[k].run(base), () => {})) }
        patch = await STEPS[i].run(base)
        setWaiting(null)
      }
      setData(i === 0 ? { ...patch } : { ...base, ...patch })
      setDone(i + 1)
      stage.current?.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (e) {
      setWaiting(null)
      setError(e instanceof ApiError ? e.message : 'Could not reach the server.')
    } finally {
      setBusy(false)
    }
  }, [])

  useEffect(() => {
    if (started.current) return
    started.current = true
    void runStep(0, {})
  }, [runStep])

  const current = done > 0 ? STEPS[done - 1] : null
  const next = done < STEPS.length ? STEPS[done] : null
  const { state, incident, proposal, parse, preview } = data

  return (
    <div className="show">
      <header className="sitenav">
        <div className="sitenav-in">
          <Wordmark />
          <span className="show-tag">Guided demo</span>
          <span className="grow" />
          <Link to="/dispatch" className="pill">Open the full dispatcher</Link>
        </div>
      </header>

      <div className="show-body">
        <aside className="show-script" aria-label="The script">
          <ol>
            {STEPS.map((s, i) => (
              <li key={s.title} className={i < done - 1 ? 'past' : i === done - 1 ? 'now' : ''} aria-current={i === done - 1 ? 'step' : undefined}>
                <span className="n">{i < done - 1 ? '✓' : i + 1}</span>
                <div><b>{s.title}</b><small>{s.who}</small></div>
              </li>
            ))}
          </ol>
        </aside>

        <main className="show-stage" ref={stage}>
          {!current && !error && <p className="muted">{waiting ?? 'Setting up the day.'}</p>}
          {current && (
            <div key={done} className="show-scene">
              <p className="show-who">{current.who}</p>
              <h1 className="show-title">{current.title}</h1>
              {current.line && <blockquote className="show-line">“{current.line}”</blockquote>}
              <p className="show-explain">{current.explain}</p>

              {current.view === 'plan' && state?.plan && <RouteLanes scenario={state.scenario} plan={state.plan} />}

              {current.view === 'readback' && incident && (
                <div className="show-card">
                  <p className="show-k">The system understood</p>
                  <p className="show-v">{incident.readback.en}</p>
                  <p className="muted">Place matched: <b>{incident.location_name ?? 'not found'}</b>. Vehicle: <b>{incident.vehicle_id}</b>. Parcels aboard: <b>{incident.parcels.join(', ') || 'none'}</b>.</p>
                </div>
              )}

              {current.view === 'shortlist' && proposal && (
                <ol className="show-cands">
                  {proposal.candidates.map((c) => (
                    <li key={c.vehicle_id} className={c.feasible ? '' : 'out'}>
                      <span className="rank">{c.feasible ? c.rank : '✕'}</span>
                      <div>
                        <b>{c.driver} ({c.vehicle_id})</b>
                        {c.feasible
                          ? <p>Reaches the van {hhmm(c.reach_site)}, leaves {hhmm(c.leave_site)}, delivers {proposal.primary} at <b>{hhmm(c.delivery_time)}</b> (due {hhmm(proposal.primary_due)}).</p>
                          : <p>Ruled out: {c.reason}</p>}
                      </div>
                    </li>
                  ))}
                </ol>
              )}

              {current.view === 'offer' && incident && (
                <div className="show-card">
                  <p className="show-k">Sent to {incident.active_offer?.driver ?? 'the first driver'}, with 60 seconds to answer</p>
                  <p className="show-v">{incident.active_offer?.text.en ?? incident.note}</p>
                  <p className="muted">Approved by {incident.approved_by}. If the plan changes before anyone accepts, the approval is void.</p>
                </div>
              )}

              {current.view === 'refused' && (
                <div className="show-card refuse">
                  <p className="show-k">Refused</p>
                  <p className="show-v">{data.refusal}</p>
                  <p>The plan is untouched.</p>
                </div>
              )}

              {current.view === 'understood' && preview && (
                <div className="show-card">
                  <p className="show-k">{data.usedForm ? 'Entered with the form (the sentence could not be read just now)' : parse?.method === 'llm' ? `Read by ${parse.model}, then checked by rules` : 'Read by the rule reader'}</p>
                  <p className="show-v">{parse?.summary ?? preview.cause}</p>
                  <div className="tally" style={{ margin: '12px 0' }}>
                    {(['broken', 'moved', 'new', 'kept'] as const).filter((s) => preview.diff.counts[s] > 0).map((s) => <StatusChip key={s} status={s} count={preview.diff.counts[s]} />)}
                  </div>
                  <p className="muted">This is a preview. Nothing has been applied.</p>
                </div>
              )}

              {current.view === 'compare' && state && <ComparePanel key={state.version} state={state} />}
            </div>
          )}
          {error && (
            <div className="show-card refuse" role="alert">
              <p className="show-k">That step did not go through</p>
              <p className="show-v">{error}</p>
              <div className="row">
                <button className="btn" onClick={() => runStep(done, data)}>Try again</button>
                <button className="btn" onClick={() => runStep(0, {})}>Restart the demo</button>
              </div>
            </div>
          )}
        </main>
      </div>

      <footer className="show-bar">
        {waiting ? <span role="status">{waiting}</span> : next ? (
          <button className="show-next" disabled={busy || done === 0} onClick={() => runStep(done, data)}>
            <small>Next: {next.who}</small>
            <span>{busy ? 'Working…' : next.title}</span>
          </button>
        ) : (
          <div className="show-end">
            <span>That is the whole demo.</span>
            <button className="pill" onClick={() => runStep(0, {})} disabled={busy}>Run it again</button>
            <Link to="/dispatch" className="pill">Try it yourself</Link>
          </div>
        )}
        <span className="show-count">{Math.min(done, STEPS.length)} of {STEPS.length}</span>
      </footer>
    </div>
  )
}
