import { VOICE } from '../config'
import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '../api'
import type { VoiceStatus } from '../types'

/** Is the voice on, what has it cost, and a button to prepare the demo's lines ahead of time. */
function VoiceSectionInner() {
  const [st, setSt] = useState<VoiceStatus | null>(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const load = useCallback(() => { api.voiceStatus().then(setSt).catch(() => setSt(null)) }, [])
  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect
    load()
    const id = setInterval(load, 10_000)
    return () => clearInterval(id)
  }, [load])

  async function prepare() {
    setBusy(true); setMsg(null)
    try {
      const r = await api.warmVoice()
      setMsg({
        ok: r.problems.length === 0,
        text: r.problems.length
          ? `Prepared ${r.generated + r.already_cached} of ${r.lines} lines. ${r.problems[0]}`
          : r.generated === 0 ? `All ${r.lines} lines were already prepared. Nothing was spent.`
            : `Prepared ${r.lines} lines (${r.generated} new, ${r.characters} characters).`,
      })
    } catch (e) {
      setMsg({ ok: false, text: e instanceof ApiError ? e.message : 'Could not reach the server' })
    } finally { setBusy(false); load() }
  }

  if (!st) return null
  return (
    <section className="sec" aria-labelledby="voice-h">
      <h3 className="h" id="voice-h">Voice</h3>
      {!st.enabled ? (
        <p className="small muted" style={{ maxWidth: '64ch' }}>
          ElevenLabs is off, so phones use their own built-in voice and speech recognition, or typing. To switch it on, add
          ELEVENLABS_API_KEY to .env and restart the server.
        </p>
      ) : (
        <>
          <p className="small" style={{ maxWidth: '68ch' }}>
            ElevenLabs is on ({st.tts_model} speaks, {st.stt_model} listens).
            This run has spent <b>{st.budget.spent.toLocaleString()}</b> of {st.budget.limit.toLocaleString()} characters
            {st.account && <>; the account shows {st.account.used.toLocaleString()} of {st.account.limit.toLocaleString()} credits used</>}.
            {' '}{st.cache.files} lines are saved, so repeats are free ({st.cache.hits} reused so far).
          </p>
          <div className="row" style={{ marginTop: 8 }}>
            <button className="btn" onClick={prepare} disabled={busy}>{busy ? 'Preparing' : 'Prepare the demo voices'}</button>
            <span className="small muted">Speaks the demo story once now, so the live run is instant and free.</span>
          </div>
        </>
      )}
      {msg && <p className={`notice ${msg.ok ? 'ok' : 'warn'} small`} role="status" style={{ marginTop: 8 }}>{msg.text}</p>}
    </section>
  )
}

export function VoiceSection() {
  return VOICE ? <VoiceSectionInner /> : null
}
