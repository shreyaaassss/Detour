import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { startRecording, type Recording } from '../audio'
import { hush, serverVoice, voiceReady } from './voice'

// ---- speaking and listening, with the browser's own voice (typing always works too) ------------------------------
interface Rec { lang: string; interimResults: boolean; continuous: boolean; start: () => void; stop: () => void
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null
  onend: (() => void) | null; onerror: (() => void) | null }
function recCtor(): (new () => Rec) | null {
  const w = window as unknown as { SpeechRecognition?: new () => Rec; webkitSpeechRecognition?: new () => Rec }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

/** A microphone button with a live transcript, a box to type in, and the suggested line as a one-tap prompt. */
export function SayBox({ suggestions, busy, placeholder, onSay, fix }: {
  suggestions: string[]; busy: boolean; placeholder: string; onSay: (text: string) => void
  fix?: (heard: string) => string // tidy a transcript (place spellings) before it is sent
}) {
  const [text, setText] = useState('')
  const [listening, setListening] = useState(false)
  const rec = useRef<Rec | null>(null)
  const heard = useRef('')
  const Ctor = recCtor()
  const tape = useRef<Recording | null>(null)
  const [working, setWorking] = useState(false)
  const [viaServer, setViaServer] = useState(serverVoice())
  useEffect(() => { void voiceReady().then(setViaServer) }, [])
  const canListen = window.isSecureContext && (Ctor !== null || viaServer)

  function send(t: string) {
    const clean = t.trim()
    if (!clean || busy) return
    setText('')
    onSay(clean)
  }

  async function toggle() {
    hush()
    // ElevenLabs listens when the server has it: record, then transcribe. The browser's own listener is the backup.
    if (viaServer && typeof navigator.mediaDevices?.getUserMedia === 'function') {
      if (listening && tape.current) {
        setListening(false); setWorking(true)
        const { audio, heard: backup } = await tape.current.stop()
        tape.current = null
        let said = ''
        try { if (audio) said = (await api.transcribe(audio)).transcript } catch { said = '' }
        setWorking(false)
        const got = said || backup
        if (got) send(fix ? fix(got) : got); else setText('')
        return
      }
      try { tape.current = await startRecording('en', true); setText(''); setListening(true) } catch { setViaServer(false) }
      return
    }
    if (listening) { rec.current?.stop(); return }
    if (!Ctor) return
    const r = new Ctor()
    r.lang = 'en-IN'; r.interimResults = true; r.continuous = false
    heard.current = ''
    r.onresult = (e) => {
      heard.current = Array.from(e.results).map((x) => x[0].transcript).join(' ').trim()
      setText(heard.current)
    }
    r.onerror = () => setListening(false)
    r.onend = () => { setListening(false); if (heard.current) send(fix ? fix(heard.current) : heard.current) }
    rec.current = r
    try { r.start(); setListening(true) } catch { setListening(false) }
  }
  useEffect(() => () => { rec.current?.stop(); tape.current?.cancel() }, [])

  return (
    <div className="say">
      <div className="say-row">
        {canListen && (
          <button type="button" className={`say-mic ${listening ? 'live' : ''}`} onClick={() => void toggle()} disabled={busy || working}
            aria-pressed={listening} aria-label={listening ? 'Stop listening' : 'Speak'}>
            <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0014 0M12 18v3" />
            </svg>
          </button>
        )}
        <form className="say-form" onSubmit={(e) => { e.preventDefault(); send(text) }}>
          <input type="text" value={text} onChange={(e) => setText(e.target.value)} placeholder={listening ? (viaServer ? 'Listening. Tap the mic again when you are done.' : 'Listening…') : working ? 'Transcribing…' : placeholder} aria-label="What you say" disabled={busy} />
          <button className="btn primary" type="submit" disabled={busy || !text.trim()}>{busy ? 'Working…' : 'Send'}</button>
        </form>
      </div>
      {listening && <div className="say-wave" aria-hidden="true"><i /><i /><i /><i /><i /></div>}
      <div className="say-hints">
        <span>{viaServer ? 'Voice by ElevenLabs. Try saying' : 'Try saying'}</span>
        {suggestions.map((s) => <button key={s} type="button" className="say-hint" disabled={busy} onClick={() => send(s)}>“{s}”</button>)}
      </div>
    </div>
  )
}

