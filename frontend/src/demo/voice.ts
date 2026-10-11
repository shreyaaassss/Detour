import { api } from '../api'
import { API_BASE } from '../config'

// Answers are read aloud. When the server has ElevenLabs, its voice speaks the system's own sentences (found by
// reference, never free text). Otherwise the browser's own voice does. If neither works, the words are on screen.
let soundOn = true
let server: boolean | null = null // does the server have ElevenLabs? unknown until asked
let playing: HTMLAudioElement | null = null

export interface SayRef { what: 'readback' | 'offer' | 'note' | 'said'; ref: string }

export async function voiceReady(): Promise<boolean> {
  if (server === null) {
    try { server = (await api.voiceStatus()).enabled } catch { server = false }
  }
  return server
}
export function serverVoice(): boolean { return server === true }

export function hush() {
  playing?.pause(); playing = null
  if ('speechSynthesis' in window) window.speechSynthesis.cancel()
}
export function setVoice(on: boolean) { soundOn = on; if (!on) hush() }

function browserSay(text: string) {
  if (!('speechSynthesis' in window)) return
  try {
    const u = new SpeechSynthesisUtterance(text)
    u.lang = 'en-IN'; u.rate = 1.02
    window.speechSynthesis.speak(u)
  } catch { /* no voice on this device */ }
}

/** Say `text`. With a reference and a voice on the server, ElevenLabs says it; otherwise the browser does. */
export function speak(text: string, ref?: SayRef) {
  if (!soundOn || !text) return
  hush()
  if (server && ref) {
    const a = new Audio(`${API_BASE}/voice/audio?what=${ref.what}&ref=${encodeURIComponent(ref.ref)}&lang=en`)
    playing = a
    a.play().catch(() => { if (playing === a) { playing = null; browserSay(text) } })
    a.onerror = () => { if (playing === a) { playing = null; browserSay(text) } }
    return
  }
  browserSay(text)
}
