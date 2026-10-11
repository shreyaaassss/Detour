import { describe, expect, it } from 'vitest'
import { decide } from './decision'

describe('a reply on the call', () => {
  it('takes a clear yes in any of the three languages', () => {
    for (const s of ['Confirm.', 'confirm', 'Yes', 'Okay, I accept', 'हाँ', 'कन्फर्म', 'ठीक है', 'हाँ, ठीक है।', 'haan', 'होय', '1'])
      expect(decide(s), s).toBe('confirmed')
  })
  it('takes a clear no', () => {
    for (const s of ['No', 'no.', 'नहीं', 'I cannot', 'मना', 'No, not okay', 'नाही', '2'])
      expect(decide(s), s).toBe('declined')
  })
  it('leaves questions and conversation to the agent', () => {
    for (const s of ['When would I reach the van?', 'मैं अपने van तक कब तक पहुँचूँगी?', 'Will I get paid extra', 'what is this about', 'Hello',
      'let me think about it for a moment please', 'क्या मुझे ज़्यादा पैसे मिलेंगे', ''])
      expect(decide(s), s).toBeNull()
  })
})
