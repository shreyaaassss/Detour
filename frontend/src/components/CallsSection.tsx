import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '../api'
import type { TelephonyStatus } from '../types'

const LANG: Record<string, string> = { hi: 'Hindi', mr: 'Marathi', en: 'English', driver: "each driver's own language" }

/** Is the phone line ready, to whom would it ring, and a button to test it before the demo. */
export function CallsSection() {
  const [st, setSt] = useState<TelephonyStatus | null>(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const load = useCallback(() => { api.telephonyStatus().then(setSt).catch(() => setSt(null)) }, [])
  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect
    load()
    const id = setInterval(load, 6000)
    return () => clearInterval(id)
  }, [load])

  async function test() {
    setBusy(true); setMsg(null)
    try {
      await api.testCall()
      setMsg({ ok: true, text: 'Ringing now. Answer it and press 1 or say confirm. The result appears below.' })
    } catch (e) {
      setMsg({ ok: false, text: e instanceof ApiError ? e.message : 'Could not reach the server' })
    } finally { setBusy(false); setTimeout(load, 1500) }
  }

  if (!st) return null
  const numbers = Object.entries(st.numbers)
  return (
    <section className="sec" aria-labelledby="calls-h">
      <h3 className="h" id="calls-h">Phone calls</h3>
      {st.ready ? (
        <>
          <p className="small" style={{ maxWidth: '68ch' }}>
            Real calls are <b>on</b>. If a driver does not answer the app in time, an automated agent rings them in {LANG[st.language] ?? st.language}
            {' '}and takes one answer: say confirm or press 1 to accept, say no or press 2 to decline.
            Numbers: {numbers.map(([who, n]) => `${who === '*' ? 'every rescue driver' : who} ${n}`).join(', ')}.
            {' '}{st.placed} of {st.limit} calls used this run.
          </p>
          <div className="row" style={{ marginTop: 8 }}>
            <button className="btn" onClick={test} disabled={busy}>Test the phone line</button>
            <span className="small muted">Rings the listed number once with a short test. Only press it if its owner expects the call.</span>
          </div>
          {!st.public_url_set && <p className="notice warn small" style={{ marginTop: 8 }}>
            PUBLIC_BASE_URL is not set, so the agent cannot report its answer straight to us. Answers are still picked up by checking the call,
            a few seconds later.</p>}
        </>
      ) : (
        <>
          <p className="small muted" style={{ maxWidth: '68ch' }}>
            Real calls are off, so the <b>simulate the call</b> buttons below stand in. They use exactly the same steps. To switch real calls on, still needed:
          </p>
          <ul className="small">{st.missing.map((m) => <li key={m}>{m}</li>)}</ul>
        </>
      )}
      {msg && <p className={`notice ${msg.ok ? 'ok' : 'warn'} small`} role="status" style={{ marginTop: 8 }}>{msg.text}</p>}
      {st.recent.length > 0 && (
        <details style={{ marginTop: 8 }}>
          <summary>Recent calls</summary>
          <ul>{st.recent.map((r, i) => <li key={i}>{r.what}{r.detail ? `: ${r.detail}` : ''}</li>)}</ul>
        </details>
      )}
    </section>
  )
}
