import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api, ApiError } from '../api'
import type { Incident } from '../types'
import { useDetour } from '../useDetour'
import { useOverview } from '../useRescue'
import { Ctx, ENDED, KEY, OFFERING, type Demo, type DispatchTurn, type Phase } from './store'
import { didYouMean, spokenNames } from './places'
import { hush, setVoice, speak, voiceReady, type SayRef } from './voice'

function stored(): { id?: string; said?: string; seen?: boolean } {
  try { return JSON.parse(sessionStorage.getItem(KEY) ?? '{}') } catch { return {} }
}
function store(v: { id?: string; said?: string; seen?: boolean } | null) {
  try { if (v) sessionStorage.setItem(KEY, JSON.stringify(v)); else sessionStorage.removeItem(KEY) } catch { /* private mode */ }
}

export function DemoProvider({ children }: { children: ReactNode }) {
  const { state, error: loadError, refresh } = useDetour()
  const overview = useOverview()
  const [mineId, setMineId] = useState<string | null>(() => stored().id ?? null)
  const [fresh, setFresh] = useState<Incident | null>(null) // the answer to our own last call, until the overview catches up
  const [said, setSaid] = useState<string | null>(() => stored().said ?? null)
  const [seenChanges, setSeen] = useState<boolean>(() => stored().seen ?? false)
  const [picks, setPicks] = useState<string[] | null>(null)
  const [turns, setTurns] = useState<DispatchTurn[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sound, setSoundState] = useState(true)
  const [ready, setReady] = useState<boolean>(() => { try { return sessionStorage.getItem(KEY) !== null } catch { return false } })
  const turnId = useRef(0)
  const spoken = useRef(new Set<string>())

  const live = mineId ? overview.data?.incidents.find((i) => i.id === mineId) : undefined
  const incident = live ?? (fresh && fresh.id === mineId ? fresh : null)
  const proposal = incident?.proposal ?? null
  const feasible = useMemo(() => proposal?.candidates.filter((c) => c.feasible) ?? [], [proposal])
  const chosen = picks ?? feasible.slice(0, 3).map((c) => c.vehicle_id)
  const offer = incident?.active_offer ?? null
  const lostPlace = incident?.state === 'REJECTED' && !incident.location_id
  const phase: Phase = !incident ? 0 : lostPlace ? 1 : incident.state === 'REPORTED' ? 2
    : ENDED.has(incident.state) ? 5 : OFFERING.has(incident.state) ? 4 : 3

  useEffect(() => { store({ id: mineId ?? undefined, said: said ?? undefined, seen: seenChanges }) }, [mineId, said, seenChanges])

  const act = useCallback(async (fn: () => Promise<void>) => {
    setBusy(true); setError(null)
    try { await fn() } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not reach the server. It may be waking up: try again in a moment.')
    } finally { setBusy(false) }
  }, [])

  const clear = useCallback(() => {
    hush()
    spoken.current.clear()
    setMineId(null); setFresh(null); setSaid(null); setPicks(null); setTurns([]); setSeen(false)
  }, [])

  // a new visit starts from a clean day, so yesterday's breakdown is never on screen
  const began = useRef(false)
  useEffect(() => {
    if (ready || began.current) return
    began.current = true
    void (async () => {
      for (let i = 0; i < 30; i++) {
        try { await api.reset(); break } catch { await new Promise((r) => setTimeout(r, 3000)) }
      }
      clear(); await refresh(); overview.reload(); setReady(true)
    })()
  }, [ready, clear, refresh, overview])

  const sayOnce = useCallback((key: string, text: string | undefined | null, ref?: SayRef) => {
    if (!text || spoken.current.has(key)) return
    spoken.current.add(key); speak(text, ref)
  }, [])
  const [voice, setVoiceOn] = useState(false) // does the server have the ElevenLabs voice and agent?
  useEffect(() => { void voiceReady().then(setVoiceOn) }, [])
  useEffect(() => {
    if (!incident) return
    if (incident.state === 'REPORTED') sayOnce(`rb-${incident.id}`, incident.readback.en, { what: 'readback', ref: incident.id })
    if (offer?.channel === 'push') sayOnce(`of-${offer.id}`, offer.text.en, { what: 'offer', ref: offer.id })
    if (incident.state === 'COMMITTED') sayOnce(`ok-${incident.id}`, 'Rescue committed. The plan has been updated.')
  }, [incident, offer, sayOnce])

  const places = useMemo(() => spokenNames((state?.scenario.locations ?? []).map((l) => l.name)), [state?.scenario.locations])

  const took = (i: Incident) => { setFresh(i); setMineId(i.id); overview.reload() }

  const value: Demo = {
    state: ready ? state : null,
    loading: ready && state ? null : loadError ? 'Waking the server. This can take up to a minute the first time.' : 'Setting up the day.',
    cfg: overview.data?.config, incident, proposal, feasible, chosen, setPicks, offer, phase, said, turns, seenChanges,
    markChangesSeen: () => setSeen(true),
    places, busy, error, clearError: () => setError(null), sound, voice,
    setSound: (v) => { setSoundState(v); setVoice(v) },
    report: (text, locationId) => void act(async () => {
      setSaid(text); setPicks(null)
      took((await api.report({ driver: 'Ravi', transcript: text, language: 'en', location_id: locationId })).incident)
    }),
    confirmReport: (yes) => void act(async () => {
      if (!incident) return
      if (!yes) {
        try { await api.confirmReport(incident.id, { confirmed: false }) } catch { /* it is reported again anyway */ }
        setMineId(null); setFresh(null); setSaid(null); return
      }
      took((await api.confirmReport(incident.id, { confirmed: true })).incident)
    }),
    approve: () => void act(async () => {
      if (!incident || !proposal) return
      took((await api.approve(incident.id, { approved_by: 'Head of logistics', shortlist: chosen, proposal_version: proposal.plan_version, role: 'head' })).incident)
    }),
    answer: (o, yes) => void act(async () => {
      const r = o.channel === 'call'
        ? await api.callEvent(o.id, yes ? 'confirmed' : 'declined')
        : await api.respond(o.id, yes ? 'accept' : 'decline', o.driver ?? undefined)
      took(r.incident); await refresh()
    }),
    skipWait: (o) => void act(async () => { took((await api.skipWait(o.id)).incident) }),
    reload: () => { overview.reload(); void refresh() },
    dispatchSay: (text) => void act(async () => {
      const id = ++turnId.current
      try {
        const r = await api.parseReport(text)
        setTurns((t) => [...t.map((x) => (x.preview && !x.applied ? { ...x, discarded: true } : x)), { id, text, parse: r.parse, preview: r.preview }])
        speak(r.parse.summary ?? 'Understood. Please confirm.', r.say_ref ? { what: 'said', ref: r.say_ref } : undefined)
      } catch (e) {
        if (!(e instanceof ApiError) || e.status !== 422) throw e
        setTurns((t) => [...t, { id, text, refusal: e.message, suggest: didYouMean(text, places) }])
        const ref = typeof e.extra.say_ref === 'string' ? e.extra.say_ref : null
        speak(e.message, ref ? { what: 'said', ref } : undefined)
      }
    }),
    urgent: () => void act(async () => {
      const id = ++turnId.current
      const presets = await api.presets()
      const p = await api.preview(presets.urgent_delivery)
      setTurns((t) => [...t.map((x) => (x.preview && !x.applied ? { ...x, discarded: true } : x)), { id, text: 'Urgent parcel D13 to Wanowrie by 15:00', preview: p }])
    }),
    settle: (turn, apply) => void act(async () => {
      if (apply && turn.preview) { await api.confirm(turn.preview.preview_id, 'Dispatcher'); await refresh(); speak('Applied.') }
      setTurns((t) => t.map((x) => (x.id === turn.id ? { ...x, applied: apply, discarded: !apply } : x)))
    }),
    restart: () => void act(async () => { await api.reset(); clear(); await refresh(); overview.reload() }),
  }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
