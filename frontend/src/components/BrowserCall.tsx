import { useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api'
import { ui, type Lang } from '../i18n'
import type { Offer } from '../types'

type Phase = 'idle' | 'connecting' | 'live' | 'ended'
type Mode = 'speaking' | 'listening'

interface Session { sendUserMessage: (t: string) => void; endSession: () => Promise<void>; getId: () => string }

/** Plan B for the phone line: the same call agent, spoken to through this phone's microphone and speaker.
 * Browsers cannot send real keypad tones, so 1 and 2 are on-screen buttons that send the same "1" / "2" the agent
 * expects from a keypad. The outcome reaches the app through the server, exactly as a phone call's would. */
export function BrowserCall({ offer, lang }: { offer: Offer; lang: Lang }) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [mode, setMode] = useState<Mode>('speaking')
  const [err, setErr] = useState<string | null>(null)
  const session = useRef<Session | null>(null)
  const secure = typeof window !== 'undefined' && window.isSecureContext

  useEffect(() => () => { void session.current?.endSession().catch(() => {}) }, [])

  async function start() {
    if (!offer.driver) return
    setErr(null); setPhase('connecting')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true }) // ask while the tap is fresh
      stream.getTracks().forEach((t) => t.stop())
      const cfg = await api.browserSession(offer.id, offer.driver)
      const { Conversation } = await import('@elevenlabs/client')
      const conv = await Conversation.startSession({
        signedUrl: cfg.signed_url,
        connectionType: 'websocket',
        dynamicVariables: cfg.variables,
        overrides: { agent: { firstMessage: cfg.first_message, language: cfg.language as 'hi' | 'mr' | 'en' } },
        onModeChange: (m: { mode: string }) => setMode(m.mode === 'speaking' ? 'speaking' : 'listening'),
        onDisconnect: () => { session.current = null; setPhase('ended') },
        onError: (m: string) => setErr(m),
      })
      session.current = conv as unknown as Session
      setPhase('live')
      await api.browserStarted(offer.id, offer.driver, conv.getId())
    } catch (e) {
      setPhase('idle')
      setErr(e instanceof ApiError ? e.message : e instanceof Error ? e.message : 'Could not start the call')
    }
  }

  function press(n: '1' | '2') { session.current?.sendUserMessage(n) }
  async function hangUp() { try { await session.current?.endSession() } catch { /* already gone */ } setPhase('ended') }

  if (!secure) return <p className="muted" role="note">{ui('callSecure', lang)}</p>
  return (
    <div className="stack">
      {phase === 'idle' && <button className="btn primary big" onClick={start}>{ui('talkNow', lang)}</button>}
      {phase === 'connecting' && <p role="status">{ui('connecting', lang)}</p>}
      {phase === 'live' && (
        <>
          <p role="status">{ui('onCall', lang)} {mode === 'speaking' ? ui('assistantSpeaking', lang) : ui('assistantListening', lang)}</p>
          <div className="row">
            <button className="btn primary big" onClick={() => press('1')}>{ui('press1', lang)}</button>
            <button className="btn big" onClick={() => press('2')}>{ui('press2', lang)}</button>
          </div>
          <button className="btn quiet" onClick={hangUp}>{ui('endCall', lang)}</button>
        </>
      )}
      {err && <p className="error" role="alert">{err}</p>}
    </div>
  )
}
