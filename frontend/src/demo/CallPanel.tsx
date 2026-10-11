import { useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api'
import type { Offer } from '../types'
import { decide } from './decision'
import { hush } from './voice'

type Phase = 'ringing' | 'connecting' | 'live' | 'ended'
interface Line { who: 'agent' | 'you'; text: string }
interface Session { sendUserMessage: (t: string) => void; endSession: () => Promise<void>; getId: () => string; setMicMuted: (m: boolean) => void }

/** The escalation call, held in the browser: a live conversation with the ElevenLabs voice agent. The agent opens
 * with the engine's own script, answers questions only from the engine's facts, and records one clear answer. The
 * server follows the conversation and moves the rescue on, exactly as it would for a phone call. */
export function CallPanel({ offer, busy, onChange, onSettle }: { offer: Offer; busy: boolean; onChange: () => void; onSettle: (yes: boolean) => void }) {
  const [phase, setPhase] = useState<Phase>('ringing')
  const [lang, setLang] = useState<'en' | 'hi'>('en')
  const [mode, setMode] = useState<'speaking' | 'listening'>('speaking')
  const [lines, setLines] = useState<Line[]>([])
  const [err, setErr] = useState<string | null>(null)
  const session = useRef<Session | null>(null)
  const secure = window.isSecureContext
  // Hold to talk: the microphone is closed unless the Talk button is held, and always closed while the agent speaks.
  // Otherwise the agent hears its own voice from the speakers, or other people in the room, and takes it as an answer.
  const [hold, setHold] = useState(true)
  const [talking, setTalking] = useState(false)
  const release = useRef<ReturnType<typeof setTimeout> | null>(null)
  const micOpen = phase === 'live' && mode !== 'speaking' && (!hold || talking)
  useEffect(() => { try { session.current?.setMicMuted(!micOpen) } catch { /* the call has ended */ } }, [micOpen])
  const startTalk = () => { if (release.current) clearTimeout(release.current); setTalking(true) }
  const stopTalk = () => { release.current = setTimeout(() => setTalking(false), 350) } // keep the last syllable

  useEffect(() => () => { void session.current?.endSession().catch(() => {}) }, [])
  // After the call ends the server reads the agent's recorded answer. Keep asking until the page moves on; if it
  // has not after a few seconds, the answer was not clear, and the presenter can settle it by hand.
  const [stuck, setStuck] = useState(false)
  useEffect(() => {
    if (phase !== 'ended') return
    const tick = setInterval(onChange, 1000)
    const late = setTimeout(() => setStuck(true), 9000)
    return () => { clearInterval(tick); clearTimeout(late) }
  }, [phase]) // eslint-disable-line react-hooks/exhaustive-deps

  // A clear yes or no settles the rescue at once, by rule. The agent talks; it does not get to decide.
  const settled = useRef(false)
  function settle(yes: boolean) {
    if (settled.current) return
    settled.current = true
    onSettle(yes)
  }

  async function answer() {
    if (!offer.driver) return
    setErr(null); setPhase('connecting'); hush()
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true }) // ask while the tap is fresh
      stream.getTracks().forEach((t) => t.stop())
      const cfg = await api.browserSession(offer.id, offer.driver, lang)
      const { Conversation } = await import('@elevenlabs/client')
      const conv = await Conversation.startSession({
        signedUrl: cfg.signed_url,
        connectionType: 'websocket',
        dynamicVariables: cfg.variables,
        overrides: { agent: { firstMessage: cfg.first_message, language: cfg.language as 'hi' | 'mr' | 'en' } },
        onModeChange: (m: { mode: string }) => setMode(m.mode === 'speaking' ? 'speaking' : 'listening'),
        onMessage: (m: { message: string; source: string }) => {
          const text = m.message?.trim()
          if (!text) return
          setLines((l) => [...l, { who: m.source === 'user' ? 'you' : 'agent', text }])
          if (m.source === 'user') {
            const d = decide(text)
            if (d) settle(d === 'confirmed')
          }
        },
        onDisconnect: () => { session.current = null; setPhase('ended'); onChange() },
        onError: (m: string) => setErr(m),
      })
      session.current = conv as unknown as Session
      try { session.current.setMicMuted(true) } catch { /* older client */ }
      setPhase('live')
      await api.browserStarted(offer.id, offer.driver, conv.getId())
      onChange()
    } catch (e) {
      setPhase('ringing')
      setErr(e instanceof ApiError ? e.message : e instanceof Error ? e.message : 'Could not start the call.')
    }
  }
  function press(n: '1' | '2') {
    setLines((l) => [...l, { who: 'you', text: n === '1' ? 'Pressed 1 (accept)' : 'Pressed 2 (decline)' }])
    settle(n === '1')
  }
  async function hangUp() { try { await session.current?.endSession() } catch { /* already gone */ } setPhase('ended'); onChange() }

  return (
    <div className={`call ${phase}`}>
      {phase === 'ringing' && (
        <>
          <div className="call-ring" aria-hidden="true"><span /><span /><span /></div>
          <p className="turn-big">DeTour is calling {offer.driver}.</p>
          <p className="muted">An automated voice agent. Hold the Talk button to speak: ask it anything about the job, then say confirm or no.</p>
          {secure ? (
            <div className="turn-actions">
              <button className="btn primary big" onClick={() => void answer()}>Answer the call</button>
              <div className="seg" role="group" aria-label="Call language">
                <button aria-pressed={lang === 'en'} onClick={() => setLang('en')}>English</button>
                <button aria-pressed={lang === 'hi'} onClick={() => setLang('hi')}>हिन्दी</button>
              </div>
              <span className="grow" />
              <button className="btn quiet small" disabled={busy} onClick={() => onSettle(true)}>Skip the call: confirms</button>
              <button className="btn quiet small" disabled={busy} onClick={() => onSettle(false)}>declines</button>
            </div>
          ) : <p className="muted">The microphone needs a secure (https) address.</p>}
        </>
      )}
      {phase === 'connecting' && <p className="turn-big" role="status">Connecting…</p>}
      {(phase === 'live' || phase === 'ended') && (
        <>
          <p className="call-state" role="status">
            {phase === 'ended' ? 'Call ended' : mode === 'speaking' ? 'The agent is speaking' : micOpen ? 'Listening to you' : 'Your turn. Hold the button and speak.'}
            {phase === 'live' && <span className={`say-wave ${mode}`} aria-hidden="true"><i /><i /><i /><i /><i /></span>}
          </p>
          <ol className="call-lines" aria-label="Conversation">
            {lines.map((l, i) => <li key={i} className={l.who}><small>{l.who === 'agent' ? 'Agent' : offer.driver}</small>{l.text}</li>)}
          </ol>
          {phase === 'live' && (
            <>
              {hold && (
                <button className={`talk ${talking ? 'on' : ''}`} disabled={mode === 'speaking'}
                  onPointerDown={startTalk} onPointerUp={stopTalk} onPointerLeave={() => talking && stopTalk()} onPointerCancel={stopTalk}
                  onKeyDown={(e) => { if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) { e.preventDefault(); startTalk() } }}
                  onKeyUp={(e) => { if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); stopTalk() } }}>
                  {mode === 'speaking' ? 'Wait for the agent to finish' : talking ? 'Listening… release when done' : 'Hold to talk'}
                </button>
              )}
              <div className="turn-actions">
                <button className="btn primary big" onClick={() => press('1')}>1 · Accept</button>
                <button className="btn big" onClick={() => press('2')}>2 · Decline</button>
                <button className="btn quiet" onClick={() => void hangUp()}>Hang up</button>
                <label className="check small"><input type="checkbox" checked={!hold} onChange={(e) => setHold(!e.target.checked)} /> Open mic (quiet room, headphones)</label>
              </div>
            </>
          )}
        </>
      )}
      {phase === 'ended' && !stuck && <p className="call-state" role="status">Recording the answer…</p>}
      {phase === 'ended' && stuck && (
        <div className="turn-actions">
          <span className="muted">The call ended without a clear answer.</span>
          <button className="btn" disabled={busy} onClick={() => onSettle(true)}>Record: confirmed</button>
          <button className="btn" disabled={busy} onClick={() => onSettle(false)}>Record: declined</button>
        </div>
      )}
      {err && <p className="formerr" role="alert">{err}</p>}
    </div>
  )
}
