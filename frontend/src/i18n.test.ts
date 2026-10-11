import { describe, expect, it } from 'vitest'
import { LANGS, pick, ui, UI_KEYS } from './i18n'
import { mmss } from './format'

describe('driver screen words', () => {
  it('exist in every language, and the other languages are not just English', () => {
    for (const key of UI_KEYS) {
      const en = ui(key, 'en')
      for (const { id } of LANGS) expect(ui(key, id).trim().length, `${key} in ${id}`).toBeGreaterThan(0)
      expect(ui(key, 'hi'), key).not.toBe(en)
      expect(ui(key, 'mr'), key).not.toBe(en)
    }
  })

  it('falls back to English when a message is missing in the reader\'s language', () => {
    expect(pick({ en: 'Hello', hi: 'नमस्ते' }, 'mr')).toBe('Hello')
    expect(pick({ en: 'Hello', hi: 'नमस्ते' }, 'hi')).toBe('नमस्ते')
    expect(pick(undefined, 'en')).toBe('')
  })
})

describe('countdown text', () => {
  it('shows minutes and seconds', () => {
    expect(mmss(102)).toBe('1:42')
    expect(mmss(59.2)).toBe('1:00')
    expect(mmss(null)).toBe('')
  })
})
