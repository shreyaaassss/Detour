import { VOICE } from '../config'
import { useEffect, useState } from 'react'
import { say, sayNow, soundOn, stopSpeaking } from '../audio'
import { ui, type Lang } from '../i18n'
import { Glyph } from './ui'

/** Speaks `text` when it first appears (if sound is on), stops if it goes away, and offers a button to hear it again. */
function ListenInner({ id, url, text, lang, auto = true }: { id: string; url: string; text: string; lang: Lang; auto?: boolean }) {
  const [playing, setPlaying] = useState(false)

  useEffect(() => {
    if (!auto || !soundOn()) return
    void say(url, text, lang)
    return () => stopSpeaking() // also lets a repeated effect (React's double run in development) start it again cleanly
  }, [id, url, text, lang, auto])

  async function again() {
    setPlaying(true)
    await sayNow(url, text, lang)
    setTimeout(() => setPlaying(false), 800)
  }
  return (
    <button className="btn" onClick={again} aria-label={ui('listen', lang)} disabled={playing} style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
      <Glyph name="urgent" size={14} />{ui('listen', lang)}
    </button>
  )
}

export function Listen(props: Parameters<typeof ListenInner>[0]) {
  return VOICE ? <ListenInner {...props} /> : null
}
