// Speaking and listening on the phone. The server's voice (ElevenLabs) comes first; the phone's own voice is the
// fallback; and if neither works the message is still on the screen.
import { useSyncExternalStore } from 'react'
import type { Lang } from './i18n'

const SILENT = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAAA='
const KEY = 'detour.sound'
const LOCALE: Record<Lang, string> = { en: 'en-IN', hi: 'hi-IN', mr: 'mr-IN' }

let current: HTMLAudioElement | null = null
let unlocked = false
const listeners = new Set<() => void>()

function read(): boolean {
  try { return localStorage.getItem(KEY) !== 'off' } catch { return true }
}
let on = read()

export function setSound(v: boolean): void {
  on = v
  try { localStorage.setItem(KEY, v ? 'on' : 'off') } catch { /* private mode */ }
  if (!v) stopSpeaking()
  listeners.forEach((l) => l())
}
export function useSound(): boolean {
  return useSyncExternalStore((l) => { listeners.add(l); return () => listeners.delete(l) }, () => on)
}
export function soundOn(): boolean { return on }

/** Phones only let a page make sound after the person has touched it. Call this from the first tap. */
export function unlockAudio(): void {
  if (unlocked) return
  unlocked = true
  new Audio(SILENT).play().catch(() => { unlocked = false })
}

export function stopSpeaking(): void {
  current?.pause()
  current = null
  if ('speechSynthesis' in window) window.speechSynthesis.cancel()
}

export function audioUrl(what: 'readback' | 'offer' | 'note', ref: string | number, lang: Lang): string {
  return `/voice/audio?what=${what}&ref=${encodeURIComponent(String(ref))}&lang=${lang}`
}

function playUrl(url: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const a = new Audio(url)
    current = a
    a.addEventListener('playing', () => resolve(), { once: true })
    a.addEventListener('error', () => reject(new Error('audio failed')), { once: true })
    a.play().catch(reject)
  })
}

function speakWithPhone(text: string, lang: Lang): boolean {
  if (!('speechSynthesis' in window) || !text) return false
  const voices = window.speechSynthesis.getVoices()
  const want = LOCALE[lang]
  // Marathi is written in Devanagari like Hindi, so a Hindi voice is a fair stand-in when there is no Marathi one
  const voice = voices.find((v) => v.lang === want) ?? voices.find((v) => v.lang.startsWith(lang))
    ?? (lang === 'mr' ? voices.find((v) => v.lang.startsWith('hi')) : undefined)
  if (!voice && lang !== 'en') return false
  const u = new SpeechSynthesisUtterance(text)
  u.lang = voice?.lang ?? want
  if (voice) u.voice = voice
  window.speechSynthesis.speak(u)
  return true
}

export type Spoken = 'server' | 'phone' | 'silent'

/** Say it out loud: the server's voice, else the phone's voice, else nothing (the text is on screen). */
export async function say(url: string, text: string, lang: Lang): Promise<Spoken> {
  if (!on) return 'silent'
  stopSpeaking()
  try {
    await playUrl(url)
    return 'server'
  } catch {
    return speakWithPhone(text, lang) ? 'phone' : 'silent'
  }
}

/** Say it even if sound is off, because the person asked (they pressed Listen). */
export async function sayNow(url: string, text: string, lang: Lang): Promise<Spoken> {
  stopSpeaking()
  try {
    await playUrl(url)
    return 'server'
  } catch {
    return speakWithPhone(text, lang) ? 'phone' : 'silent'
  }
}

// ---- listening ---------------------------------------------------------------------------------------------
type Recognition = { start: () => void; stop: () => void; abort: () => void; lang: string; continuous: boolean
  interimResults: boolean; onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal?: boolean }> }) => void) | null
  onerror: (() => void) | null; onend: (() => void) | null }
type RecognitionCtor = new () => Recognition

function recognitionCtor(): RecognitionCtor | null {
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

export interface MicSupport {
  secure: boolean // the page is on https or localhost, so the browser will allow the microphone
  recorder: boolean // can record audio to send to the server
  browserStt: boolean // the browser can turn speech into text itself
}
export function micSupport(): MicSupport {
  return {
    secure: window.isSecureContext,
    recorder: !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== 'undefined',
    browserStt: recognitionCtor() !== null,
  }
}

export interface Recording {
  /** Stop and return what was recorded, and what the browser itself heard. */
  stop: () => Promise<{ audio: Blob | null; heard: string }>
  cancel: () => void
}

const TYPES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']

/** Record the microphone, and at the same time let the browser try to understand it, as a backup. */
export async function startRecording(lang: Lang, wantAudio: boolean): Promise<Recording> {
  const sup = micSupport()
  let stream: MediaStream | null = null
  let rec: MediaRecorder | null = null
  const chunks: Blob[] = []
  if (wantAudio && sup.recorder) {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const type = TYPES.find((t) => MediaRecorder.isTypeSupported(t))
    rec = new MediaRecorder(stream, type ? { mimeType: type } : undefined)
    rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data) }
    rec.start()
  }
  let heard = ''
  let sr: Recognition | null = null
  const Ctor = recognitionCtor()
  if (Ctor) {
    try {
      sr = new Ctor()
      sr.lang = LOCALE[lang]
      sr.continuous = true
      sr.interimResults = false
      sr.onresult = (e) => { heard = Array.from(e.results).map((r) => r[0].transcript).join(' ').trim() }
      sr.onerror = () => {}
      sr.start()
    } catch { sr = null }
  }
  const release = () => stream?.getTracks().forEach((t) => t.stop())
  return {
    cancel() { try { sr?.abort() } catch { /* already stopped */ } if (rec && rec.state !== 'inactive') rec.stop(); release() },
    stop() {
      return new Promise((resolve) => {
        try { sr?.stop() } catch { /* already stopped */ }
        const finish = () => { release(); setTimeout(() => resolve({ audio: chunks.length ? new Blob(chunks, { type: rec?.mimeType }) : null, heard }), 350) }
        if (rec && rec.state !== 'inactive') { rec.onstop = finish; rec.stop() } else finish()
      })
    },
  }
}
