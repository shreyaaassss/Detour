import { describe, expect, it } from 'vitest'
import { didYouMean, snapPlaces, spokenNames } from './places'

const NAMES = spokenNames(['Swargate Depot (depot)', 'Hadapsar', 'Kothrud Clinic', 'Aundh', 'Baner', 'Wanowrie', 'Kondhwa', 'Katraj', 'Shivajinagar', 'Camp', 'Viman Nagar', 'Kharadi'])

describe('place names heard by speech-to-text', () => {
  it('uses the short names people say', () => {
    expect(NAMES).toContain('Kothrud')
    expect(NAMES).toContain('Hadapsar')
    expect(NAMES).not.toContain('Clinic')
  })
  it('corrects a spelling that is almost a known place', () => {
    expect(snapPlaces('The road between Kotrud and Aundh is slow', NAMES)).toBe('The road between Kothrud and Aundh is slow')
    expect(snapPlaces('My truck broke down near Hadapser', NAMES)).toBe('My truck broke down near Hadapsar')
  })
  it('never turns an unknown place into a known one', () => {
    const s = 'The road between Kothrud and Mumbai is closed until 4 pm'
    expect(snapPlaces(s, NAMES)).toBe(s)
    expect(didYouMean(s, NAMES)).toEqual([])
  })
  it('only offers a looser match as a question', () => {
    const s = 'The road between Potharood and Aundh is closed'
    expect(snapPlaces(s, NAMES)).toBe(s)
    expect(didYouMean(s, NAMES)[0]).toEqual({ name: 'Kothrud', sentence: 'The road between Kothrud and Aundh is closed' })
  })
  it('leaves ordinary words alone', () => {
    const s = 'The road between Kothrud and Aundh is slow until 4 pm, it adds 25 minutes'
    expect(snapPlaces(s, NAMES)).toBe(s)
    expect(didYouMean(s, NAMES)).toEqual([])
  })
})
