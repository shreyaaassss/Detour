/** Where the API lives. Empty means the same address as the page (local development, or a host that forwards the API paths). */
export const API_BASE: string = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '')

/** Spoken features (listening to offers, speaking a report, the voice call). Off unless VITE_VOICE=on: the app is text-first. */
export const VOICE: boolean = import.meta.env.VITE_VOICE === 'on'
