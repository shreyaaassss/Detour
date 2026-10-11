import { useEffect, useState } from 'react'
import { api } from '../api'
import { hhmm, parseHhmm } from '../format'
import { serverNow } from '../serverTime'
import type { RescueOverview } from '../types'
import { RescueStatus } from './RescueStatus'
import { VoiceSection } from './VoiceSection'

const DONE = ['COMMITTED', 'EXHAUSTED', 'CANCELLED', 'REJECTED']

/** The simulated time of day, which runs on when the clock is live. */
function useSimNow(ov: RescueOverview | null): number | null {
  const [, tick] = useState(0)
  useEffect(() => {
    if (!ov || ov.clock.speed === 0) return
    const id = setInterval(() => tick((n) => n + 1), 1000)
    return () => clearInterval(id)
  }, [ov])
  if (!ov) return null
  return ov.clock.sim + ((serverNow() - ov.server_time) / 60) * ov.clock.speed
}

export function RescuePanel({ ov, reload }: { ov: RescueOverview | null; reload: () => void }) {
  const sim = useSimNow(ov)
  const [time, setTime] = useState('')
  const [err, setErr] = useState<string | null>(null)
  if (!ov) return <p className="empty">Loading.</p>
  const live = ov.clock.speed > 0
  const open = ov.incidents.filter((i) => !DONE.includes(i.state))
  const done = ov.incidents.filter((i) => DONE.includes(i.state))

  async function setClock(b: { sim_time?: string; speed?: number }) {
    setErr(null)
    try { await api.setClock(b); reload() } catch (e) { setErr(e instanceof Error ? e.message : 'Could not set the clock') }
  }

  return (
    <div>
      <section className="sec">
        <h3 className="h">Simulated time</h3>
        <div className="row">
          <span className="clock" aria-label="Simulated time">{hhmm(sim)}</span>
          <span className="muted small">{live ? 'running live, one minute per minute' : 'held, so every run gives the same numbers'}</span>
          <div className="spacer" />
          <label className="row small muted">Set to
            <input type="text" value={time} placeholder="14:05" style={{ width: 80 }} inputMode="numeric" onChange={(e) => setTime(e.target.value)}
              aria-label="Set the simulated time as HH:MM" />
          </label>
          <button className="btn" disabled={parseHhmm(time) == null} onClick={() => { void setClock({ sim_time: time }); setTime('') }}>Set</button>
          <button className="btn" onClick={() => setClock({ speed: live ? 0 : 1 })}>{live ? 'Hold the clock' : 'Run live'}</button>
        </div>
        {err && <p className="notice err" role="alert" style={{ marginTop: 8 }}>{err}</p>}
        <p className="small muted" style={{ marginTop: 8 }}>
          Offer timers always run in real seconds: {ov.config.push_timeout} s to answer the app, then a call that rings
          {' '}{ov.config.ring_timeout} s and talks for up to {ov.config.conversation_limit} s. The head has {ov.config.head_response} s before the backup is asked.
        </p>
      </section>

      <VoiceSection />

      <h3 className="h">Rescues in progress</h3>
      {open.length === 0 && <p className="empty">No open rescues. Open the driver screen at /driver, report a breakdown, and it appears here.</p>}
      {open.map((i) => (
        <section key={i.id} className="sec"><RescueStatus inc={i} cfg={ov.config} simulate /></section>
      ))}
      {done.length > 0 && (
        <>
          <h3 className="h">Finished</h3>
          {done.map((i) => <section key={i.id} className="sec"><RescueStatus inc={i} cfg={ov.config} /></section>)}
        </>
      )}
    </div>
  )
}
