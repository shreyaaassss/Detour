import { useMemo, useState } from 'react'
import { api, ApiError } from '../api'
import { Countdown } from '../components/Countdown'
import { Glyph } from '../components/ui'
import { LANGS, pick, ui, type Lang } from '../i18n'
import type { Incident, Offer } from '../types'
import { useDetour } from '../useDetour'
import { useLive, useNotes, useOverview } from '../useRescue'

const KEY_ME = 'detour.driver'
const KEY_LANG = 'detour.lang'
const store = {
  get: (k: string) => { try { return localStorage.getItem(k) } catch { return null } },
  set: (k: string, v: string) => { try { localStorage.setItem(k, v) } catch { /* private mode */ } },
}

const OPEN = new Set(['REPORTED', 'AWAITING_HEAD', 'HEAD_APPROVED', 'OFFER_PUSHED', 'CALL_ESCALATED', 'ACCEPTED', 'CANDIDATE_DECLINED'])

export default function Driver() {
  const { state, connected } = useDetour()
  const overview = useOverview()
  const drivers = useMemo(() => (state?.scenario.vehicles ?? []).filter((v) => v.driver), [state])
  const [me, setMe] = useState<string>(() => new URLSearchParams(location.search).get('as') ?? store.get(KEY_ME) ?? '')
  const mine = drivers.find((v) => v.driver === me) ?? drivers[0]
  const name = mine?.driver ?? ''
  const [langPick, setLangPick] = useState<Lang | null>(() => store.get(KEY_LANG) as Lang | null)
  const lang: Lang = langPick ?? (mine?.language as Lang) ?? 'en'

  const offers = useLive(() => (name ? api.offers(name) : Promise.resolve({ offers: [] as Offer[] })), ['incident', 'notify', 'state'])
  const { notes } = useNotes(`driver:${name}`)

  const incidents = (overview.data?.incidents ?? []).filter((i) => i.driver === name)
  const current = incidents.findLast((i) => OPEN.has(i.state)) ?? incidents.at(-1)
  const push = offers.data?.offers.find((o) => o.channel === 'push')
  const ringing = current?.active_offer?.channel === 'call' && current.active_offer.driver === name ? current.active_offer : null
  const cfg = overview.data?.config

  function chooseMe(v: string) { setMe(v); store.set(KEY_ME, v) }
  function chooseLang(l: Lang) { setLangPick(l); store.set(KEY_LANG, l) }

  return (
    <div className="phone">
      <header className="phonebar">
        <label className="field" style={{ flex: 1 }}>
          {ui('iAm', lang)}
          <select value={name} onChange={(e) => chooseMe(e.target.value)} aria-label="Driver">
            {drivers.map((v) => <option key={v.id} value={v.driver!}>{v.driver} ({v.id})</option>)}
          </select>
        </label>
        <div className="seg" role="group" aria-label="Language">
          {LANGS.map((l) => (
            <button key={l.id} aria-pressed={lang === l.id} onClick={() => chooseLang(l.id)}>{l.label}</button>
          ))}
        </div>
        <span className="live" role="status" title={connected ? 'Live' : 'Reconnecting'}><span className={`dot ${connected ? 'on' : ''}`} /></span>
      </header>

      <main className="phonebody" lang={lang}>
        {push && cfg && <OfferCard offer={push} lang={lang} total={cfg.push_timeout} onDone={() => { offers.reload(); overview.reload() }} />}
        {!push && ringing && cfg && (
          <section className="bigcard attention">
            <h2 className="h">{ui('calling', lang)}</h2>
            <Countdown deadline={ringing.call_state === 'in_call' ? ringing.conversation_deadline : ringing.deadline}
              total={ringing.call_state === 'in_call' ? cfg.conversation_limit : cfg.ring_timeout} label={ui('secondsLeft', lang)} />
          </section>
        )}
        {!push && !ringing && (
          current && OPEN.has(current.state) || current?.state === 'COMMITTED' || current?.state === 'EXHAUSTED' || current?.state === 'REJECTED' || current?.state === 'CANCELLED'
            ? <Status incident={current} lang={lang} notes={notes} reload={overview.reload} />
            : null
        )}
        {!push && !ringing && (!current || ['COMMITTED', 'EXHAUSTED', 'REJECTED', 'CANCELLED'].includes(current.state)) && state && (
          <ReportForm key={name} driver={name} lang={lang} places={state.scenario.locations.map((l) => ({ id: l.id, name: l.name }))}
            onSent={overview.reload} again={current != null} />
        )}

        <section aria-labelledby="feed-h" style={{ marginTop: 22 }}>
          <h2 className="h" id="feed-h">{ui('updates', lang)}</h2>
          {notes.length === 0 ? <p className="muted">{ui('noUpdates', lang)}</p> : (
            <ul className="feed">
              {notes.filter((n) => n.kind !== 'readback').slice(0, 8).map((n) => <li key={n.id}>{pick(n.text, lang)}</li>)}
            </ul>
          )}
        </section>
      </main>
    </div>
  )
}

function OfferCard({ offer, lang, total, onDone }: { offer: Offer; lang: Lang; total: number; onDone: () => void }) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  async function answer(r: 'accept' | 'decline') {
    setBusy(true); setErr(null)
    try { await api.respond(offer.id, r, offer.driver ?? undefined) } catch (e) { setErr(e instanceof ApiError ? e.message : 'Could not reach the server') }
    finally { setBusy(false); onDone() }
  }
  return (
    <section className="bigcard attention" aria-live="assertive">
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <p className="offertext">{pick(offer.text, lang)}</p>
        <Countdown deadline={offer.deadline} total={total} label={ui('secondsLeft', lang)} />
      </div>
      <div className="twobtn">
        <button className="btn primary huge" onClick={() => answer('accept')} disabled={busy}>{ui('accept', lang)}</button>
        <button className="btn huge" onClick={() => answer('decline')} disabled={busy}>{ui('decline', lang)}</button>
      </div>
      {err && <p className="notice err" role="alert" style={{ marginTop: 10 }}>{err}</p>}
    </section>
  )
}

function Status({ incident, lang, notes, reload }: { incident: Incident; lang: Lang; notes: ReturnType<typeof useNotes>['notes']; reload: () => void }) {
  const [busy, setBusy] = useState(false)
  const [changing, setChanging] = useState(false)
  const latest = (kind: string) => notes.find((n) => n.kind === kind && n.incident_id === incident.id)
  async function run(f: () => Promise<unknown>) { setBusy(true); try { await f() } finally { setBusy(false); setChanging(false); reload() } }

  if (incident.state === 'REPORTED') {
    return (
      <section className="bigcard attention">
        <h2 className="h">{ui('confirmTitle', lang)}</h2>
        <p className="offertext">{pick(incident.readback, lang)}</p>
        {changing ? (
          <div className="places">
            {(incident.known_locations.length ? incident.known_locations : []).map((p) => (
              <button key={p.id} className="btn" onClick={() => run(() => api.confirmReport(incident.id, { location_id: p.id }))}>{p.name}</button>
            ))}
          </div>
        ) : (
          <div className="twobtn">
            <button className="btn primary huge" disabled={busy} onClick={() => run(() => api.confirmReport(incident.id, { confirmed: true }))}>{ui('correct', lang)}</button>
            <button className="btn huge" disabled={busy} onClick={() => run(() => api.confirmReport(incident.id, { confirmed: false }))}>{ui('cancel', lang)}</button>
          </div>
        )}
      </section>
    )
  }
  if (incident.state === 'REJECTED' || incident.state === 'CANCELLED') {
    return (
      <section className="bigcard">
        <p className="notice warn">{incident.note || incident.result}</p>
      </section>
    )
  }
  if (incident.state === 'COMMITTED') {
    const t = latest('on_the_way') ?? latest('awaiting')
    return (
      <section className="bigcard good" role="status">
        <p className="offertext">{pick(t?.text, lang) || incident.result}</p>
      </section>
    )
  }
  if (incident.state === 'EXHAUSTED') {
    return <section className="bigcard" role="status"><p className="offertext">{pick(latest('no_rescue')?.text, lang)}</p></section>
  }
  // waiting: nobody is promised anything yet
  return (
    <section className="bigcard" role="status">
      <p className="offertext">{pick(latest('awaiting')?.text, lang)}</p>
      <p className="small muted" style={{ marginTop: 6 }}><Glyph name="lock" size={12} /> {incident.vehicle_id}</p>
    </section>
  )
}

function ReportForm({ driver, lang, places, onSent, again }: {
  driver: string; lang: Lang; places: { id: string; name: string }[]; onSent: () => void; again: boolean
}) {
  const [text, setText] = useState('')
  const [pickPlace, setPickPlace] = useState(false)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ note: string; places: { id: string; name: string }[] } | null>(null)

  async function send(body: Omit<Parameters<typeof api.report>[0], 'driver' | 'language'>) {
    setBusy(true)
    try {
      const { incident } = await api.report({ driver, language: lang, ...body })
      setMsg(incident.state === 'REJECTED' ? { note: incident.note, places: incident.known_locations } : null)
      setText('')
      setPickPlace(false)
      onSent()
    } catch (e) {
      setMsg({ note: e instanceof ApiError ? e.message : 'Could not reach the server', places: [] })
    } finally { setBusy(false) }
  }

  return (
    <section className="bigcard">
      <h2 className="h">{again ? ui('again', lang) : ui('title', lang)}</h2>
      <button className="btn mic" disabled aria-describedby="mic-note"><Glyph name="breakdown" size={28} /></button>
      <p className="small muted" id="mic-note" style={{ margin: '6px 0 12px' }}>{ui('micOff', lang)}</p>
      <label className="field">{ui('whatHappened', lang)}
        <textarea rows={3} value={text} placeholder={ui('placeholder', lang)} onChange={(e) => setText(e.target.value)} />
      </label>
      <div className="twobtn" style={{ marginTop: 10 }}>
        <button className="btn primary huge" disabled={busy || !text.trim()} onClick={() => send({ transcript: text, source: 'text' })}>{ui('send', lang)}</button>
        <button className="btn huge" disabled={busy} onClick={() => setPickPlace(true)}>{ui('brokeDown', lang)}</button>
      </div>
      {pickPlace && (
        <div style={{ marginTop: 12 }}>
          <p className="small muted">{ui('whereAreYou', lang)}</p>
          <div className="places">
            {places.map((p) => <button key={p.id} className="btn" disabled={busy}
              onClick={() => send({ location_id: p.id, breakdown: true, source: 'buttons', transcript: '' })}>{p.name}</button>)}
          </div>
        </div>
      )}
      {msg && (
        <div className="notice warn" role="alert" style={{ marginTop: 12 }}>
          <p>{msg.note}</p>
          {msg.places.length > 0 && (
            <div className="places" style={{ marginTop: 8 }}>
              {msg.places.map((p) => <button key={p.id} className="btn" disabled={busy}
                onClick={() => send({ location_id: p.id, breakdown: true, source: 'buttons', transcript: text || '' })}>{p.name}</button>)}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
