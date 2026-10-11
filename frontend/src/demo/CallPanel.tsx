import { useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api'
import type { Offer } from '../types'
import { hush } from './voice'

type Phase = 'ringing' | 'connecting' | 'live' | 'ended'
interface Line { who: 'agent' | 'you'; text: string }
interface Session { sendUserMessage: (t: string) => void; endSession: () => Promise<void>; getId: () => string }

/** The escalation call, held in the browser: a live conversation with the ElevenLabs voice agent. The agent opens
 * with the engine's own script, answers questions only from the engine's facts, and records one clear answer. The
 * server follows the conversation and moves the rescue on, exactly as it would for a phone call. */
export function CallPanel({ offer, onChange }: { offer: Offer; onChange: () => void }) {
  const [phase, setPhase] = useState<Phase>('ringing')
  const [lang, setLang] = useState<'en' | 'hi'>('en')
  const [mode, setMode] = useState<'speaking' | 'listening'>('speaking')
  const [lines, setLines] = useState<Line[]>([])
  const [err, setErr] = useState<string | null>(null)
  const session = useRef<Session | null>(null)
  const secure = window.isSecureContext

  useEffect(() => () => { void session.current?.endSession().catch(() => {}) }, [])

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
          if (m.message?.trim()) setLines((l) => [...l, { who: m.source === 'user' ? 'you' : 'agent', text: m.message.trim() }])
        },
        onDisconnect: () => { session.current = null; setPhase('ended'); onChange() },
        onError: (m: string) => setErr(m),
      })
      session.current = conv as unknown as Session
      setPhase('live')
      await api.browserStarted(offer.id, offer.driver, conv.getId())
      onChange()
    } catch (e) {
      setPhase('ringing')
      setErr(e instanceof ApiError ? e.message : e instanceof Error ? e.message : 'Could not start the call.')
    }
  }
  function press(n: '1' | '2') {
    session.current?.sendUserMessage(n)
    setLines((l) => [...l, { who: 'you', text: n === '1' ? 'Pressed 1 (accept)' : 'Pressed 2 (decline)' }])
  }
  async function hangUp() { try { await session.current?.endSession() } catch { /* already gone */ } setPhase('ended'); onChange() }

  return (
    <div className={`call ${phase}`}>
      {phase === 'ringing' && (
        <>
          <div className="call-ring" aria-hidden="true"><span /><span /><span /></div>
          <p className="turn-big">DeTour is calling {offer.driver}.</p>
          <p className="muted">An automated voice agent. Ask it anything about the job, then say confirm or no.</p>
          {secure ? (
            <div className="turn-actions">
              <button className="btn primary big" onClick={() => void answer()}>Answer the call</button>
              <div className="seg" role="group" aria-label="Call language">
                <button aria-pressed={lang === 'en'} onClick={() => setLang('en')}>English</button>
                <button aria-pressed={lang === 'hi'} onClick={() => setLang('hi')}>हिन्दी</button>
              </div>
            </div>
          ) : <p className="muted">The microphone needs a secure (https) address.</p>}
        </>
      )}
      {phase === 'connecting' && <p className="turn-big" role="status">Connecting…</p>}
      {(phase === 'live' || phase === 'ended') && (
        <>
          <p className="call-state" role="status">
            {phase === 'ended' ? 'Call ended' : mode === 'speaking' ? 'The agent is speaking' : 'Listening to you'}
            {phase === 'live' && <span className={`say-wave ${mode}`} aria-hidden="true"><i /><i /><i /><i /><i /></span>}
          </p>
          <ol className="call-lines" aria-label="Conversation">
            {lines.map((l, i) => <li key={i} className={l.who}><small>{l.who === 'agent' ? 'Agent' : offer.driver}</small>{l.text}</li>)}
          </ol>
          {phase === 'live' && (
            <div className="turn-actions">
              <button className="btn primary big" onClick={() => press('1')}>1 · Accept</button>
              <button className="btn big" onClick={() => press('2')}>2 · Decline</button>
              <button className="btn quiet" onClick={() => void hangUp()}>Hang up</button>
            </div>
          )}
        </>
      )}
      {err && <p className="formerr" role="alert">{err}</p>}
    </div>
  )
}
