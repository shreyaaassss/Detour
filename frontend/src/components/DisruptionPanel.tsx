import { useEffect, useState, type FormEvent } from 'react'
import { api, ApiError } from '../api'
import { driverOf, hhmm, parseHhmm } from '../format'
import { describePreset } from '../presets'
import type { Disruption, Interpreter, ParseInfo, PreviewResult, Presets, Scenario } from '../types'
import { Glyph } from './ui'

type Kind = Disruption['type']

interface Props {
  scenario: Scenario
  presets: Presets
  now: number
  disabled: boolean
  prefill: Disruption | null
  onPreview: (p: PreviewResult, parse?: ParseInfo) => void
}

export function DisruptionPanel({ scenario, presets, now, disabled, prefill, onPreview }: Props) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [kind, setKind] = useState<Kind>(prefill?.type ?? 'road_closure')
  const [text, setText] = useState('')
  const [issues, setIssues] = useState<{ message: string }[]>([])
  const [places, setPlaces] = useState<{ id: string; name: string }[]>([])
  const [reader, setReader] = useState<Interpreter | null>(null)
  useEffect(() => { api.interpreter().then(setReader).catch(() => setReader(null)) }, [])
  const pf = prefill && prefill.type === kind ? prefill : null

  async function readWords() {
    setBusy(true); setError(null); setIssues([]); setPlaces([])
    try {
      const r = await api.parseReport(text)
      onPreview(r.preview, r.parse)
    } catch (e) {
      if (e instanceof ApiError && e.code === 'cannot_interpret') {
        setIssues((e.extra.issues as { message: string }[]) ?? [{ message: e.message }])
        setPlaces((e.extra.known_locations as { id: string; name: string }[]) ?? [])
      } else setError(e instanceof ApiError ? e.message : 'Could not reach the server')
    } finally { setBusy(false) }
  }

  async function run(d: Disruption) {
    setBusy(true)
    setError(null)
    try {
      onPreview(await api.preview(d))
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not reach the server')
    } finally {
      setBusy(false)
    }
  }

  const live = scenario.vehicles.filter((v) => v.status === 'active')

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    const get = (k: string) => String(f.get(k) ?? '')
    const time = (k: string) => parseHhmm(get(k))
    const bad = (m: string) => setError(m)
    if (kind === 'road_closure') {
      const start = time('start'), end = time('end'), at = time('at')
      if (start == null || end == null || at == null) return bad('Enter times as HH:MM, for example 14:30.')
      return run({ type: 'road_closure', a: get('a'), b: get('b'), start, end, added_minutes: Number(get('added')), reported_at: at })
    }
    if (kind === 'vehicle_failure') {
      const t = time('time')
      if (t == null) return bad('Enter the time as HH:MM, for example 14:05.')
      return run({ type: 'vehicle_failure', vehicle_id: get('vehicle'), location: get('location'), time: t })
    }
    const ws = time('ws'), we = time('we'), at = time('at')
    if (ws == null || we == null || at == null) return bad('Enter times as HH:MM, for example 15:30.')
    return run({
      type: 'urgent_delivery', id: get('id').trim(), location: get('location'), size: Number(get('size')),
      window_start: ws, window_end: we, time: at,
    })
  }

  const locOptions = scenario.locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)
  const kinds: [Kind, string][] = [['road_closure', 'Closed road'], ['vehicle_failure', 'Breakdown'], ['urgent_delivery', 'Urgent delivery']]
  const nextId = `D${scenario.deliveries.length + 1}`

  return (
    <section className="sec" aria-labelledby="dis-h">
      <h2 className="h" id="dis-h">Something changed</h2>
      <label className="field">Describe it in your own words
        <textarea rows={3} value={text} disabled={disabled || busy} onChange={(e) => setText(e.target.value)}
          placeholder="For example: the road between Kothrud and Aundh is slow until 4 pm, it adds 25 minutes" />
      </label>
      <div className="row" style={{ marginTop: 8 }}>
        <button className="btn primary" disabled={disabled || busy || !text.trim()} onClick={readWords}>Read this</button>
        <span className="small muted">
          {reader ? (reader.mode === 'llm' ? `Read with ${reader.model}, then checked by rules` : 'Read by rules, no AI') : ''}
        </span>
      </div>
      {issues.length > 0 && (
        <div className="notice warn" role="alert" style={{ marginTop: 10 }}>
          {issues.map((i) => <p key={i.message}>{i.message}</p>)}
          {places.length > 0 && <p className="small" style={{ marginTop: 6 }}>Places I know: {places.map((p) => p.name).join(', ')}.</p>}
          <p className="small" style={{ marginTop: 6 }}>Nothing was changed. You can also use the form below.</p>
        </div>
      )}
      <p className="small muted" style={{ margin: '14px 0 8px' }}>Or choose one:</p>
      <div className="stack">
        {Object.entries(presets).map(([name, d]) => {
          const p = describePreset(d, scenario)
          return (
            <button key={name} className="btn block preset" disabled={disabled || busy} onClick={() => run(d)}>
              <span className="glyph"><Glyph name={p.icon === 'vehicle_failure' ? 'breakdown' : p.icon === 'road_closure' ? 'closure' : 'urgent'} size={18} /></span>
              <span><b>{p.title}</b><span>{p.detail}</span></span>
            </button>
          )
        })}
      </div>

      <details style={{ marginTop: 14 }} open={prefill !== null}>
        <summary>Enter your own</summary>
        <div className="row" role="group" aria-label="Kind of change" style={{ marginTop: 10 }}>
          {kinds.map(([k, label]) => (
            <button key={k} type="button" className={`btn ${kind === k ? 'primary' : ''}`} aria-pressed={kind === k}
              onClick={() => { setKind(k); setError(null) }}>{label}</button>
          ))}
        </div>
        <form onSubmit={submit} key={`${kind}-${now}`} noValidate>
          <div className="formgrid">
            {kind === 'road_closure' && (<>
              <label className="field">Road from<select name="a" defaultValue={pf?.type === 'road_closure' ? pf.a : 'kothrud'}>{locOptions}</select></label>
              <label className="field">Road to<select name="b" defaultValue={pf?.type === 'road_closure' ? pf.b : 'aundh'}>{locOptions}</select></label>
              <label className="field">Slow from<input name="start" type="text" defaultValue={hhmm(pf?.type === 'road_closure' ? pf.start : now)} inputMode="numeric" /></label>
              <label className="field">Until<input name="end" type="text" defaultValue={hhmm(pf?.type === 'road_closure' ? pf.end : now + 120)} inputMode="numeric" /></label>
              <label className="field">Extra minutes<input name="added" type="number" min={1} defaultValue={pf?.type === 'road_closure' && pf.added_minutes ? pf.added_minutes : 25} /></label>
              <label className="field">Reported at<input name="at" type="text" defaultValue={hhmm(now)} inputMode="numeric" /></label>
            </>)}
            {kind === 'vehicle_failure' && (<>
              <label className="field">Vehicle<select name="vehicle" defaultValue={pf?.type === 'vehicle_failure' ? pf.vehicle_id : live[0]?.id}>
                {live.map((v) => <option key={v.id} value={v.id}>{driverOf(scenario, v.id)}</option>)}</select></label>
              <label className="field">Time<input name="time" type="text" defaultValue={hhmm(pf?.type === 'vehicle_failure' ? pf.time : now)} inputMode="numeric" /></label>
              <label className="field wide">Broke down at<select name="location" defaultValue={pf?.type === 'vehicle_failure' ? pf.location : 'hadapsar'}>{locOptions}</select></label>
            </>)}
            {kind === 'urgent_delivery' && (<>
              <label className="field">Delivery ID<input name="id" type="text" defaultValue={pf?.type === 'urgent_delivery' ? pf.id : nextId} /></label>
              <label className="field">Size<input name="size" type="number" min={1} defaultValue={pf?.type === 'urgent_delivery' ? pf.size : 8} /></label>
              <label className="field wide">Deliver to<select name="location" defaultValue={pf?.type === 'urgent_delivery' ? pf.location : 'camp'}>{locOptions}</select></label>
              <label className="field">Window opens<input name="ws" type="text" defaultValue={hhmm(pf?.type === 'urgent_delivery' ? pf.window_start : now + 5)} inputMode="numeric" /></label>
              <label className="field">Window closes<input name="we" type="text" defaultValue={hhmm(pf?.type === 'urgent_delivery' ? pf.window_end : now + 90)} inputMode="numeric" /></label>
              <label className="field wide">Added at<input name="at" type="text" defaultValue={hhmm(now)} inputMode="numeric" /></label>
            </>)}
            <div className="wide"><button className="btn primary" disabled={disabled || busy}>Review the effect</button></div>
          </div>
        </form>
      </details>
      {error && <p className="notice err" role="alert" style={{ marginTop: 12 }}>{error}</p>}
      <p className="small muted" style={{ marginTop: 12 }}>
        Nothing changes until you have reviewed the effect and applied it.
      </p>
    </section>
  )
}
