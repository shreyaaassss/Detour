import { createContext, useContext } from 'react'
import type { AppState, Candidate, Incident, Offer, ParseInfo, PreviewResult, Proposal, RescueConfig } from '../types'

/* The one story the demo pages share. Each page is a different person's view of it; the server holds the truth. */

export const LINES = {
  breakdown: 'My truck broke down near Hadapsar',
  unknown: 'The road between Kothrud and Mumbai is closed until 4 pm',
  closure: 'The road between Kothrud and Aundh is slow until 4 pm, it adds 25 minutes',
}
export const OFFERING = new Set(['HEAD_APPROVED', 'OFFER_PUSHED', 'CALL_ESCALATED', 'CANDIDATE_DECLINED', 'ACCEPTED'])
export const ENDED = new Set(['COMMITTED', 'EXHAUSTED'])
export const KEY = 'detour.demo'

export interface DispatchTurn { id: number; text: string; refusal?: string; suggest?: { name: string; sentence: string }[]; parse?: ParseInfo; preview?: PreviewResult; applied?: boolean; discarded?: boolean }
/** 0 nothing reported, 1 the place was not understood, 2 waiting for the driver's yes, 3 waiting for the head,
 * 4 an offer is out, 5 the rescue is settled. */
export type Phase = 0 | 1 | 2 | 3 | 4 | 5

export interface Demo {
  state: AppState | null; loading: string | null; cfg: RescueConfig | undefined
  incident: Incident | null; proposal: Proposal | null; feasible: Candidate[]; chosen: string[]; setPicks: (v: string[]) => void
  offer: Offer | null; phase: Phase; said: string | null; turns: DispatchTurn[]; seenChanges: boolean; markChangesSeen: () => void
  places: string[]; busy: boolean; error: string | null; clearError: () => void; sound: boolean; voice: boolean; setSound: (v: boolean) => void
  report: (text: string, locationId?: string) => void; confirmReport: (yes: boolean) => void; approve: () => void
  answer: (o: Offer, yes: boolean) => void; skipWait: (o: Offer) => void; reload: () => void; dispatchSay: (text: string) => void; urgent: () => void
  settle: (t: DispatchTurn, apply: boolean) => void; restart: () => void
}

export const Ctx = createContext<Demo | null>(null)
export function useDemo(): Demo {
  const d = useContext(Ctx)
  if (!d) throw new Error('useDemo outside DemoProvider')
  return d
}

