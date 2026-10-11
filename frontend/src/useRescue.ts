import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import { subscribe } from './events'
import { serverNow } from './serverTime'
import type { Note, RescueOverview } from './types'

/** Run `load` now and again whenever the server says something changed. */
export function useLive<T>(load: () => Promise<T>, types: string[] = ['state', 'incident', 'notify']): {
  data: T | null; reload: () => void; connected: boolean; error: string | null
} {
  const [data, setData] = useState<T | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const loadRef = useRef(load)
  useEffect(() => { loadRef.current = load })
  const seq = useRef(0)

  const reload = useCallback(() => {
    const mine = ++seq.current
    loadRef.current()
      .then((d) => { if (mine === seq.current) { setData(d); setError(null) } })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Cannot reach the server'))
  }, [])

  const key = types.join(',')
  useEffect(() => {
    // the first load, then a refresh on every event that matters
    // oxlint-disable-next-line react/set-state-in-effect
    reload()
    const kinds = key.split(',')
    return subscribe((t) => { if (t === 'hello' || kinds.includes(t)) reload() }, setConnected)
  }, [reload, key])

  return { data, reload, connected, error }
}

export function useOverview() {
  return useLive<RescueOverview>(() => api.overview())
}

/** A person's notification feed, newest first. */
export function useNotes(to: string) {
  const r = useLive<Note[]>(async () => (await api.notifications(to)).notifications.reverse(), ['notify', 'incident'])
  return { notes: r.data ?? [], reload: r.reload }
}

/** Seconds left until a server deadline, ticking every 250 ms. */
export function useSecondsLeft(deadline: number | null | undefined): number | null {
  const [now, setNow] = useState(serverNow())
  useEffect(() => {
    if (deadline == null) return
    const id = setInterval(() => setNow(serverNow()), 250)
    return () => clearInterval(id)
  }, [deadline])
  return deadline == null ? null : Math.max(0, deadline - now)
}
