import { describe, expect, it } from 'vitest'
import { hhmm, minutes, parseHhmm, signed } from './format'

describe('format', () => {
  it('formats and parses clock times', () => {
    expect(hhmm(845)).toBe('14:05')
    expect(hhmm(null)).toBe('--:--')
    expect(hhmm(24 * 60 + 5)).toBe('00:05')
    expect(parseHhmm('14:05')).toBe(845)
    expect(parseHhmm('9:30')).toBe(570)
    expect(parseHhmm('25:00')).toBeNull()
    expect(parseHhmm('14:60')).toBeNull()
    expect(parseHhmm('noon')).toBeNull()
  })
  it('formats durations', () => {
    expect(minutes(25)).toBe('25 min')
    expect(minutes(125)).toBe('2 h 5 min')
    expect(minutes(120)).toBe('2 h')
    expect(signed(18)).toBe('+18 min')
    expect(signed(-5)).toBe('−5 min')
    expect(signed(0)).toBe('no change')
  })
})
