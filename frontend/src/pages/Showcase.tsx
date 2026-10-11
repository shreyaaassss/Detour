import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api'
import { ComparePanel } from '../components/ComparePanel'
import { Countdown } from '../components/Countdown'
import { RouteLanes } from '../components/RouteLanes'
import { StatusChip } from '../components/ui'
import { hhmm } from '../format'
import { Wordmark } from '../site/SiteChrome'
import type { Incident, Offer, ParseInfo, PreviewResult } from '../types'
import { useDetour } from '../useDetour'
import { useOverview } from '../useRescue'

/* The live demo, played turn by turn on one screen. People really speak or type their lines and press the real
 * buttons; every answer on screen comes from the server. Suggested lines are only prompts for the presenter. */

const LINES = {
  breakdown: 'My truck broke down near Hadapsar',
  unknown: 'The road between Kothrud and Mumbai is closed until 4 pm',
  closure: 'The road between Kothrud and Aundh is slow until 4 pm, it adds 25 minutes',
}
const OFFERING = new Set(['HEAD_APPROVED', 'OFFER_PUSHED', 'CALL_ESCALATED', 'CANDIDATE_DECLINED', 'ACCEPTED'])
const ENDED = new Set(['COMMITTED', 'EXHAUSTED'])

// ---- speaking and listening, with the browser's own voice (typing always works too) ------------------------------
interface Rec { lang: string; interimResults: boolean; continuous: boolean; start: () => void; stop: () => void
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null
  onend: (() => void) | null; onerror: (() => void) | null }
function recCtor(): (new () => Rec) | null {
  const w = window as unknown as { SpeechRecognition?: new () => Rec; webkitSpeechRecognition?: new () => Rec }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

let soundOn = true
function speak(text: string) {
  if (!soundOn || !('speechSynthesis' in window)) return
  try {
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text)
    u.lang = 'en-IN'; u.rate = 1.02
    window.speechSynthesis.speak(u)
  } catch { /* no voice on this device: the words are on screen */ }
}

/** A microphone button with a live transcript, a box to type in, and the suggested line as a one-tap prompt. */
function SayBox({ suggestions, busy, placeholder, onSay }: { suggestions: string[]; busy: boolean; placeholder: string; onSay: (text: string) => void }) {
  const [text, setText] = useState('')
  const [listening, setListening] = useState(false)
  const rec = useRef<Rec | null>(null)
  const heard = useRef('')
  const Ctor = recCtor()
  const canListen = Ctor !== null && window.isSecureContext

  function send(t: string) {
    const clean = t.trim()
    if (!clean || busy) return
    setText('')
    onSay(clean)
  }
  function toggle() {
    if (listening) { rec.current?.stop(); return }
    if (!Ctor) return
    window.speechSynthesis?.cancel()
    const r = new Ctor()
    r.lang = 'en-IN'; r.interimResults = true; r.continuous = false
    heard.current = ''
    r.onresult = (e) => {
      heard.current = Array.from(e.results).map((x) => x[0].transcript).join(' ').trim()
      setText(heard.current)
    }
    r.onerror = () => setListening(false)
    r.onend = () => { setListening(false); if (heard.current) send(heard.current) }
    rec.current = r
    try { r.start(); setListening(true) } catch { setListening(false) }
  }
  useEffect(() => () => { rec.current?.stop() }, [])

  return (
    <div className="say">
      <div className="say-row">
        {canListen && (
          <button type="button" className={`say-mic ${listening ? 'live' : ''}`} onClick={toggle} disabled={busy}
            aria-pressed={listening} aria-label={listening ? 'Stop listening' : 'Speak'}>
            <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0014 0M12 18v3" />
            </svg>
          </button>
        )}
        <form className="say-form" onSubmit={(e) => { e.preventDefault(); send(text) }}>
          <input type="text" value={text} onChange={(e) => setText(e.target.value)} placeholder={listening ? 'Listening…' : placeholder} aria-label="What you say" disabled={busy} />
          <button className="btn primary" type="submit" disabled={busy || !text.trim()}>{busy ? 'Working…' : 'Send'}</button>
        </form>
      </div>
      {listening && <div className="say-wave" aria-hidden="true"><i /><i /><i /><i /><i /></div>}
      <div className="say-hints">
        <span>Try saying</span>
        {suggestions.map((s) => <button key={s} type="button" className="say-hint" disabled={busy} onClick={() => send(s)}>“{s}”</button>)}
      </div>
    </div>
  )
}

function Bubble({ who, children }: { who: string; children: ReactNode }) {
  return <div className="turn said"><p className="turn-who">{who}</p><blockquote>{children}</blockquote></div>
}
function Card({ label, tone, children }: { label: string; tone?: 'refuse' | 'good'; children: ReactNode }) {
  return <div className={`turn sys ${tone ?? ''}`}><p className="turn-who">{label}</p>{children}</div>
}

interface DispatchTurn { id: number; text: string; refusal?: string; parse?: ParseInfo; preview?: PreviewResult; applied?: boolean; discarded?: boolean }

export default function Showcase() {
  const { state, error: loadError, refresh } = useDetour()
  const overview = useOverview()
  const [started, setStarted] = useState(false)
  const [said, setSaid] = useState<string | null>(null) // what the driver actually said
  const [mine, setMine] = useState<Incident | null>(null)
  const [picks, setPicks] = useState<string[] | null>(null)
  const [turns, setTurns] = useState<DispatchTurn[]>([])
  const [dispatching, setDispatching] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sound, setSound] = useState(true)
  const end = useRef<HTMLDivElement>(null)
  const turnId = useRef(0)

  // the server's own view of our incident wins: timers and other screens can move it
  const incident = (mine && overview.data?.incidents.find((i) => i.id === mine.id)) ?? mine
  const cfg = overview.data?.config
  const proposal = incident?.proposal ?? null
  const feasible = proposal?.candidates.filter((c) => c.feasible) ?? []
  const chosen = picks ?? feasible.slice(0, 3).map((c) => c.vehicle_id)
  const offer = incident?.active_offer ?? null
  const ended = incident ? ENDED.has(incident.state) : false
  const lostPlace = incident?.state === 'REJECTED' && !incident.location_id

  const act = useCallback(async (fn: () => Promise<void>) => {
    setBusy(true); setError(null)
    try { await fn() } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not reach the server. It may be waking up: try again in a moment.')
    } finally { setBusy(false) }
  }, [])

  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [incident?.state, incident?.active_offer?.id, turns, started, said, dispatching, error])
  useEffect(() => { soundOn = sound; if (!sound) window.speechSynthesis?.cancel() }, [sound])

  // say the important answers aloud, once each
  const spoken = useRef(new Set<string>())
  const sayOnce = useCallback((key: string, text: string | undefined | null) => {
    if (!text || spoken.current.has(key)) return
    spoken.current.add(key); speak(text)
  }, [])
  useEffect(() => {
    if (!incident) return
    if (incident.state === 'REPORTED') sayOnce(`rb-${incident.id}`, incident.readback.en)
    if (offer?.channel === 'push') sayOnce(`of-${offer.id}`, `${offer.driver}. ${offer.text.en}`)
    if (incident.state === 'COMMITTED') sayOnce(`ok-${incident.id}`, 'Rescue committed. The plan has been updated.')
  }, [incident, offer, sayOnce])

  function restart() {
    void act(async () => {
      window.speechSynthesis?.cancel(); spoken.current.clear()
      await api.reset()
      setStarted(false); setSaid(null); setMine(null); setPicks(null); setTurns([]); setDispatching(false)
      await refresh(); overview.reload()
    })
  }

  const report = (text: string, locationId?: string) => act(async () => {
    setSaid(text)
    const r = await api.report({ driver: 'Ravi', transcript: text, language: 'en', location_id: locationId })
    setMine(r.incident); setPicks(null); overview.reload()
  })
  const confirmReport = (yes: boolean) => act(async () => {
    if (!incident) return
    if (!yes) { try { await api.confirmReport(incident.id, { confirmed: false }) } catch { /* it is being reported again anyway */ } setMine(null); setSaid(null); return }
    setMine((await api.confirmReport(incident.id, { confirmed: true })).incident); overview.reload()
  })
  const approve = () => act(async () => {
    if (!incident || !proposal) return
    const r = await api.approve(incident.id, { approved_by: 'Head of logistics', shortlist: chosen, proposal_version: proposal.plan_version, role: 'head' })
    setMine(r.incident); overview.reload()
  })
  const answer = (o: Offer, yes: boolean) => act(async () => {
    const r = o.channel === 'call'
      ? await api.callEvent(o.id, yes ? 'confirmed' : 'declined')
      : await api.respond(o.id, yes ? 'accept' : 'decline', o.driver ?? undefined)
    setMine(r.incident); overview.reload(); await refresh()
  })

  const dispatchSay = (text: string) => act(async () => {
    const id = ++turnId.current
    try {
      const r = await api.parseReport(text)
      setTurns((t) => [...t.map((x) => (x.preview && !x.applied ? { ...x, discarded: true } : x)), { id, text, parse: r.parse, preview: r.preview }])
      speak(`${r.parse.summary ?? 'Understood.'} Please confirm.`)
    } catch (e) {
      if (!(e instanceof ApiError) || e.status !== 422) throw e
      setTurns((t) => [...t, { id, text, refusal: e.message }])
      speak(e.message)
    }
  })
  const urgent = () => act(async () => {
    const id = ++turnId.current
    const presets = await api.presets()
    const p = await api.preview(presets.urgent_delivery)
    setTurns((t) => [...t.map((x) => (x.preview && !x.applied ? { ...x, discarded: true } : x)), { id, text: 'Urgent parcel D13 to Wanowrie by 15:00', preview: p }])
  })
  const settle = (turn: DispatchTurn, apply: boolean) => act(async () => {
    if (apply && turn.preview) { await api.confirm(turn.preview.preview_id, 'Dispatcher'); await refresh(); speak('Applied.') }
    setTurns((t) => t.map((x) => (x.id === turn.id ? { ...x, applied: apply, discarded: !apply } : x)))
  })

  const phase = !started ? 0 : !incident || lostPlace ? 1 : incident.state === 'REPORTED' ? 2
    : !OFFERING.has(incident.state) && !ended ? 3 : !ended ? 4 : !dispatching ? 5 : 6
  const SCRIPT = ['The day is planned', 'The driver reports', 'The driver confirms', 'The head approves', 'A rescue driver answers', 'What changed', 'The dispatcher reports changes']
  const lastApplied = [...turns].reverse().find((t) => t.applied)

  return (
    <div className="show">
      <header className="sitenav">
        <div className="sitenav-in">
          <Wordmark />
          <span className="show-tag">Live demo</span>
          <span className="grow" />
          <button className="show-top" aria-pressed={sound} onClick={() => setSound(!sound)}>{sound ? 'Voice on' : 'Voice off'}</button>
          <button className="show-top" onClick={restart} disabled={busy}>Restart</button>
          <Link to="/dispatch" className="pill">Full dispatcher</Link>
        </div>
      </header>

      <div className="show-body">
        <aside className="show-script" aria-label="Where we are">
          <ol>
            {SCRIPT.map((t, i) => (
              <li key={t} className={i < phase ? 'past' : i === phase ? 'now' : ''} aria-current={i === phase ? 'step' : undefined}>
                <span className="n">{i < phase ? '✓' : i + 1}</span><div><b>{t}</b></div>
              </li>
            ))}
          </ol>
        </aside>

        <main className="show-stage">
          {!state && <p className="muted">{loadError ? 'Waking the server. This can take up to a minute the first time.' : 'Setting up the day.'}</p>}

          {state?.plan && !started && (
            <section className="show-scene">
              <p className="show-who">Morning</p>
              <h1 className="show-title">The day is planned</h1>
              <p className="show-explain">Five vehicles, twelve deliveries. Each is assigned within capacity and its time window, with the arrival time and any waiting at every stop.</p>
              <RouteLanes scenario={state.scenario} plan={state.original ?? state.plan} />
              <div className="show-go"><button className="btn primary big" onClick={() => setStarted(true)}>A driver calls in</button></div>
            </section>
          )}

          {started && (
            <section className="show-feed">
              <h1 className="show-title">A breakdown, live</h1>

              {(!incident || lostPlace) && !said && (
                <Card label="Ravi, driver of V2, is on the line">
                  <p className="turn-big">What happened?</p>
                </Card>
              )}
              {said && <Bubble who="Ravi, driver of V2">“{said}”</Bubble>}

              {lostPlace && incident && (
                <Card label="The system" tone="refuse">
                  <p className="turn-big">{incident.note}</p>
                  <p className="muted">It will not guess. Choose the place, or say it again.</p>
                  <div className="places">
                    {incident.known_locations.filter((l) => l.id !== 'depot').map((l) => (
                      <button key={l.id} className="btn" disabled={busy} onClick={() => report(said ?? LINES.breakdown, l.id)}>{l.name}</button>
                    ))}
                  </div>
                </Card>
              )}

              {incident && !lostPlace && (
                <Card label="The system reads it back">
                  <p className="turn-big">{incident.readback.en}</p>
                  <p className="muted">Place matched: <b>{incident.location_name}</b>. Vehicle <b>{incident.vehicle_id}</b>. Parcels aboard: <b>{incident.parcels.join(', ') || 'none'}</b>.</p>
                  {incident.state === 'REPORTED' && (
                    <div className="turn-actions">
                      <button className="btn primary big" disabled={busy} onClick={() => confirmReport(true)}>Yes, that is correct</button>
                      <button className="btn big" disabled={busy} onClick={() => confirmReport(false)}>No, that is wrong</button>
                    </div>
                  )}
                </Card>
              )}

              {incident && phase >= 3 && <Bubble who="Ravi, driver of V2">“Yes, that is correct”</Bubble>}

              {incident && phase >= 3 && proposal && (
                <Card label="For the head of logistics: who can rescue D7 in time">
                  <ol className="show-cands">
                    {proposal.candidates.map((c) => {
                      const on = chosen.includes(c.vehicle_id)
                      return (
                        <li key={c.vehicle_id} className={`${c.feasible ? '' : 'out'} ${on ? 'on' : ''}`}>
                          {c.feasible ? (
                            <input type="checkbox" checked={on} disabled={phase !== 3 || busy} aria-label={`Ask ${c.driver}`}
                              onChange={() => setPicks(on ? chosen.filter((v) => v !== c.vehicle_id) : [...chosen, c.vehicle_id].slice(0, 3))} />
                          ) : <span className="rank">✕</span>}
                          <div>
                            <b>{c.driver} ({c.vehicle_id})</b>
                            {c.feasible
                              ? <p>Reaches the van {hhmm(c.reach_site)}, leaves {hhmm(c.leave_site)}, delivers {proposal.primary} at <b>{hhmm(c.delivery_time)}</b> (due {hhmm(proposal.primary_due)}).</p>
                              : <p>Ruled out: {c.reason}</p>}
                          </div>
                        </li>
                      )
                    })}
                  </ol>
                  {phase === 3 && (
                    <div className="turn-actions">
                      <button className="btn primary big" disabled={busy || chosen.length === 0} onClick={approve}>Approve {chosen.length} {chosen.length === 1 ? 'driver' : 'drivers'}</button>
                    </div>
                  )}
                </Card>
              )}

              {incident && phase >= 4 && <Bubble who="Head of logistics">“Approved. Ask them in that order.”</Bubble>}

              {incident && phase >= 4 && incident.offers.map((o) => {
                const open = o.status === 'open'
                return (
                  <Card key={o.id} label={o.channel === 'call' ? `Calling ${o.driver}: no answer in the app` : `On ${o.driver}'s phone`} tone={o.status === 'accepted' ? 'good' : undefined}>
                    <div className="offer">
                      <div>
                        <p className="turn-big">{o.text.en}</p>
                        {!open && <p className="muted">{o.status === 'accepted' ? `${o.driver} accepted.` : `${o.driver}: ${o.outcome ?? o.status}. Moving to the next driver.`}</p>}
                      </div>
                      {open && cfg && <Countdown deadline={o.call_state === 'in_call' ? o.conversation_deadline : o.deadline} total={o.channel === 'call' ? o.deadline - o.sent : cfg.push_timeout} label="seconds left" size={88} />}
                    </div>
                    {open && (
                      <div className="turn-actions">
                        <button className="btn primary big" disabled={busy} onClick={() => answer(o, true)}>{o.channel === 'call' ? 'Answers: confirm' : 'Accept'}</button>
                        <button className="btn big" disabled={busy} onClick={() => answer(o, false)}>{o.channel === 'call' ? 'Answers: no' : 'Decline'}</button>
                      </div>
                    )}
                  </Card>
                )
              })}

              {incident && ended && state && (
                <>
                  <Card label={incident.state === 'COMMITTED' ? 'Rescue committed' : 'Nobody could take it'} tone={incident.state === 'COMMITTED' ? 'good' : 'refuse'}>
                    <p className="turn-big">{incident.state === 'COMMITTED' ? 'The plan has changed. Ravi is told help is on the way.' : incident.note}</p>
                    <p className="muted">Completed stops stay fixed. The failed vehicle gets no stops after {hhmm(incident.failure_time)}. A separate checker confirms the new plan is valid.</p>
                  </Card>
                  {!lastApplied && <div className="turn wide"><ComparePanel key={state.version} state={state} /></div>}
                </>
              )}

              {ended && !dispatching && (
                <div className="show-go"><button className="btn primary big" onClick={() => setDispatching(true)}>Later that afternoon: the dispatcher</button></div>
              )}

              {dispatching && (
                <>
                  <h2 className="show-sub">The dispatcher reports changes</h2>
                  {turns.map((t) => (
                    <div key={t.id} className="turn-group">
                      <Bubble who="Dispatcher">“{t.text}”</Bubble>
                      {t.refusal && (
                        <Card label="Refused" tone="refuse">
                          <p className="turn-big">{t.refusal}</p>
                          <p className="muted">Nothing was changed.</p>
                        </Card>
                      )}
                      {t.preview && (
                        <Card label={t.parse ? (t.parse.method === 'llm' ? `Read by ${t.parse.model}, then checked by rules` : 'Read by the rule reader') : 'Entered with the form'} tone={t.applied ? 'good' : undefined}>
                          <p className="turn-big">{t.parse?.summary ?? t.preview.cause}</p>
                          <div className="tally">
                            {(['broken', 'moved', 'new', 'kept'] as const).filter((s) => t.preview!.diff.counts[s] > 0).map((s) => <StatusChip key={s} status={s} count={t.preview!.diff.counts[s]} />)}
                          </div>
                          {t.applied ? <p className="muted">Applied by the dispatcher.</p> : t.discarded ? <p className="muted">Discarded. Nothing was changed.</p> : (
                            <>
                              <p className="muted">This is a preview. Nothing changes until the dispatcher confirms.</p>
                              <div className="turn-actions">
                                <button className="btn primary big" disabled={busy} onClick={() => settle(t, true)}>Confirm and apply</button>
                                <button className="btn big" disabled={busy} onClick={() => settle(t, false)}>Discard</button>
                              </div>
                            </>
                          )}
                        </Card>
                      )}
                    </div>
                  ))}
                  {lastApplied && state && <div className="turn wide"><ComparePanel key={state.version} state={state} /></div>}
                </>
              )}

              {error && (
                <Card label="That did not go through" tone="refuse">
                  <p className="turn-big">{error}</p>
                  <div className="turn-actions"><button className="btn" onClick={() => setError(null)}>Dismiss</button><button className="btn" onClick={restart}>Restart the demo</button></div>
                </Card>
              )}
              <div ref={end} />
            </section>
          )}
        </main>
      </div>

      {started && phase <= 1 && (
        <footer className="show-dock">
          <SayBox key="driver" suggestions={[LINES.breakdown]} busy={busy} placeholder="Speak, or type what the driver says" onSay={(t) => report(t)} />
        </footer>
      )}
      {dispatching && (
        <footer className="show-dock">
          <SayBox key="dispatcher" suggestions={[LINES.unknown, LINES.closure]} busy={busy} placeholder="Speak, or type what changed" onSay={dispatchSay} />
          <button className="btn dock-extra" disabled={busy} onClick={urgent}>Add urgent delivery D13</button>
        </footer>
      )}
    </div>
  )
}
