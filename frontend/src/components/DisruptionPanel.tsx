import { useState, type FormEvent } from 'react'
import { api, ApiError } from '../api'
import { driverOf, hhmm, parseHhmm } from '../format'
import { describePreset } from '../presets'
import type { Disruption, PreviewResult, Presets, Scenario } from '../types'
import { Glyph } from './ui'

type Kind = Disruption['type']

interface Props {
  scenario: Scenario
  presets: Presets
  now: number
  disabled: boolean
  onPreview: (p: PreviewResult) => void
}

export function DisruptionPanel({ scenario, presets, now, disabled, onPreview }: Props) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [kind, setKind] = useState<Kind>('road_closure')

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

      <details style={{ marginTop: 14 }}>
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
              <label className="field">Road from<select name="a" defaultValue="kothrud">{locOptions}</select></label>
              <label className="field">Road to<select name="b" defaultValue="aundh">{locOptions}</select></label>
              <label className="field">Slow from<input name="start" type="text" defaultValue={hhmm(now)} inputMode="numeric" /></label>
              <label className="field">Until<input name="end" type="text" defaultValue={hhmm(now + 120)} inputMode="numeric" /></label>
              <label className="field">Extra minutes<input name="added" type="number" min={1} defaultValue={25} /></label>
              <label className="field">Reported at<input name="at" type="text" defaultValue={hhmm(now)} inputMode="numeric" /></label>
            </>)}
            {kind === 'vehicle_failure' && (<>
              <label className="field">Vehicle<select name="vehicle" defaultValue={live[0]?.id}>
                {live.map((v) => <option key={v.id} value={v.id}>{driverOf(scenario, v.id)}</option>)}</select></label>
              <label className="field">Time<input name="time" type="text" defaultValue={hhmm(now)} inputMode="numeric" /></label>
              <label className="field wide">Broke down at<select name="location" defaultValue="hadapsar">{locOptions}</select></label>
            </>)}
            {kind === 'urgent_delivery' && (<>
              <label className="field">Delivery ID<input name="id" type="text" defaultValue={nextId} /></label>
              <label className="field">Size<input name="size" type="number" min={1} defaultValue={8} /></label>
              <label className="field wide">Deliver to<select name="location" defaultValue="camp">{locOptions}</select></label>
              <label className="field">Window opens<input name="ws" type="text" defaultValue={hhmm(now + 5)} inputMode="numeric" /></label>
              <label className="field">Window closes<input name="we" type="text" defaultValue={hhmm(now + 90)} inputMode="numeric" /></label>
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
