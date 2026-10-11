import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import { subscribe } from './events'
import type { AppState, AuditView, Presets } from './types'

export interface Live {
  state: AppState | null
  presets: Presets
  audit: AuditView | null
  connected: boolean
  error: string | null
  refresh: () => Promise<void>
  refreshAudit: () => Promise<void>
}

/** Loads the state and keeps it fresh from the server's event stream. */
export function useDetour(): Live {
  const [state, setState] = useState<AppState | null>(null)
  const [presets, setPresets] = useState<Presets>({})
  const [audit, setAudit] = useState<AuditView | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const latest = useRef(0)

  const refresh = useCallback(async () => {
    try {
      const s = await api.state()
      if (s.version >= latest.current) {
        latest.current = s.version
        setState(s)
      }
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Cannot reach the server')
    }
  }, [])

  const refreshAudit = useCallback(async () => {
    try { setAudit(await api.audit()) } catch { /* shown through the connection state */ }
  }, [])

  useEffect(() => {
    // first load from the server (an external system); the stream below keeps it fresh afterwards
    // oxlint-disable-next-line react/set-state-in-effect
    void refresh()
    void refreshAudit()
    api.presets().then(setPresets).catch(() => setPresets({}))
  }, [refresh, refreshAudit])

  useEffect(() => {
    return subscribe((type) => {
      if (type === 'hello') { void refresh(); void refreshAudit() }
      else if (type === 'state') { void refresh(); api.presets().then(setPresets).catch(() => {}) }
      else if (type === 'audit') void refreshAudit()
    }, setConnected)
  }, [refresh, refreshAudit])

  return { state, presets, audit, connected, error, refresh, refreshAudit }
}
