import { useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api'
import { micSupport, startRecording, unlockAudio, type Recording } from '../audio'
import { ui, type Lang } from '../i18n'
import type { Incident } from '../types'
import { Glyph } from './ui'

const MAX_SECONDS = 20

type Phase = 'idle' | 'recording' | 'sending'

/** Tap, say what happened, tap again. The server's speech-to-text is tried first, the browser's is the backup. */
export function Mic({ driver, lang, serverStt, onReported }: {
  driver: string; lang: Lang; serverStt: boolean | null; onReported: (i: Incident) => void
}) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [seconds, setSeconds] = useState(0)
  const [note, setNote] = useState<string | null>(null)
  const rec = useRef<Recording | null>(null)
  const sup = micSupport()
  // the server's listener needs a recording; the browser's own needs neither. Wait until we know which we have.
  const usable = serverStt !== null && sup.secure && (sup.recorder || sup.browserStt)

  useEffect(() => {
    if (phase !== 'recording') return
    const id = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(id)
  }, [phase])
  useEffect(() => { if (phase === 'recording' && seconds >= MAX_SECONDS) void finish() })
  useEffect(() => () => rec.current?.cancel(), [])

  async function begin() {
    unlockAudio() // this tap is also the permission to make sound later
    setNote(null)
    if (!sup.secure) return setNote(ui('micHttps', lang))
    try {
      rec.current = await startRecording(lang, true) // always record; whether to send it is decided when it stops
      setSeconds(0)
      setPhase('recording')
    } catch {
      setNote(ui('micDenied', lang))
    }
  }

  async function finish() {
    const r = rec.current
    if (!r) return
    rec.current = null
    setPhase('sending')
    const { audio, heard } = await r.stop()
    try {
      if (audio && serverStt === true) {
        try {
          const out = await api.voiceReport(driver, lang, audio)
          onReported(out.incident)
          return
        } catch (e) {
          if (!heard) throw e // the server could not help and the browser heard nothing either
        }
      }
      if (!heard) throw new ApiError(422, 'nothing_heard', ui('didntHear', lang))
      const { incident } = await api.report({ driver, language: lang, transcript: heard, source: 'voice', engine: 'browser' })
      onReported(incident)
    } catch (e) {
      setNote(e instanceof ApiError && e.code === 'nothing_heard' ? ui('didntHear', lang) : ui('didntHear', lang))
    } finally {
      setPhase('idle')
    }
  }

  return (
    <div style={{ textAlign: 'center' }}>
      <button className={`btn mic ${phase === 'recording' ? 'live' : ''}`} disabled={!usable || phase === 'sending'}
        onClick={phase === 'recording' ? finish : begin} aria-label={phase === 'recording' ? ui('recording', lang) : ui('tapToSpeak', lang)}>
        {phase === 'recording' ? <span className="stopsq" /> : <Glyph name="breakdown" size={28} />}
      </button>
      <p className="small" style={{ margin: '8px 0 0' }} role="status">
        {phase === 'recording' ? `${ui('recording', lang)} ${seconds}s` : phase === 'sending' ? ui('sending', lang)
          : !sup.secure ? ui('micHttps', lang) : usable ? ui('tapToSpeak', lang) : ui('didntHear', lang)}
      </p>
      {note && <p className="notice warn small" role="alert" style={{ marginTop: 8 }}>{note}</p>}
    </div>
  )
}
