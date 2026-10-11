import type { IncidentState, Status } from './types'

export const STATUS_LABEL: Record<Status, string> = { kept: 'Kept', moved: 'Moved', broken: 'Broken', new: 'New' }

export const STATE_LABEL: Record<IncidentState, string> = {
  REPORTED: 'Waiting for the driver to confirm',
  DRIVER_CONFIRMED: 'Driver confirmed',
  AWAITING_HEAD: 'Waiting for approval',
  HEAD_APPROVED: 'Approved',
  OFFER_PUSHED: 'Offer sent',
  CALL_ESCALATED: 'Calling the driver',
  CANDIDATE_DECLINED: 'Driver declined, trying the next',
  ACCEPTED: 'Accepted',
  COMMITTED: 'Rescue arranged',
  HEAD_TIMEOUT: 'No answer from the head',
  EXHAUSTED: 'Nobody could rescue it',
  CANCELLED: 'Cancelled',
  REJECTED: 'Report not understood',
}

