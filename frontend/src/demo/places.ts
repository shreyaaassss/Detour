// Speech-to-text often misspells a place name ("Kotrud" for Kothrud). A very close spelling is corrected, and shown,
// before it is sent; a looser one is only offered as "did you mean". A name that is nothing like a known place
// (Mumbai) is left alone, and the server refuses it.

const COMMON = new Set(['road', 'between', 'closed', 'close', 'until', 'slow', 'slower', 'adds', 'minutes', 'minute', 'delivery',
  'urgent', 'parcel', 'truck', 'broke', 'down', 'near', 'there', 'from', 'with', 'that', 'this', 'have', 'will', 'vehicle',
  'breakdown', 'clinic', 'depot', 'nagar', 'today', 'please', 'about', 'because', 'traffic', 'blocked', 'bridge'])

function distance(a: string, b: string): number {
  const row = Array.from({ length: b.length + 1 }, (_, i) => i)
  for (let i = 1; i <= a.length; i++) {
    let prev = row[0]
    row[0] = i
    for (let j = 1; j <= b.length; j++) {
      const keep = row[j]
      row[j] = Math.min(row[j] + 1, row[j - 1] + 1, prev + (a[i - 1] === b[j - 1] ? 0 : 1))
      prev = keep
    }
  }
  return row[b.length]
}
function likeness(a: string, b: string): number {
  return 1 - distance(a, b) / Math.max(a.length, b.length)
}

/** The short names people say: "Kothrud" for "Kothrud Clinic". */
export function spokenNames(names: string[]): string[] {
  const out = new Set<string>()
  for (const n of names) {
    const first = n.replace(/\(.*?\)/g, '').trim().split(/\s+/)[0]
    if (first && first.length >= 4 && !COMMON.has(first.toLowerCase())) out.add(first)
  }
  return [...out]
}

interface Near { word: string; name: string; score: number }
function nearMisses(text: string, names: string[]): Near[] {
  const known = new Set(names.map((n) => n.toLowerCase()))
  const out: Near[] = []
  for (const word of text.match(/[A-Za-z]{4,}/g) ?? []) {
    const w = word.toLowerCase()
    if (known.has(w) || COMMON.has(w)) continue
    let best: Near | null = null
    for (const name of names) {
      const score = likeness(w, name.toLowerCase())
      if (!best || score > best.score) best = { word, name, score }
    }
    if (best && best.score >= 0.5) out.push(best)
  }
  return out
}

/** Correct spellings that are almost certainly a known place. Returns the text to send. */
export function snapPlaces(text: string, names: string[]): string {
  let out = text
  for (const n of nearMisses(text, names)) if (n.score >= 0.78) out = out.replace(new RegExp(`\\b${n.word}\\b`, 'g'), n.name)
  return out
}

/** For a refused sentence: the same sentence with a doubtful word swapped for the place it resembles. */
export function didYouMean(text: string, names: string[]): { name: string; sentence: string }[] {
  const seen = new Set<string>()
  return nearMisses(text, names)
    .filter((n) => !seen.has(n.word + n.name) && seen.add(n.word + n.name))
    .map((n) => ({ name: n.name, sentence: text.replace(new RegExp(`\\b${n.word}\\b`, 'g'), n.name) }))
}
