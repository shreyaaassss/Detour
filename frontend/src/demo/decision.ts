// What a driver's short reply on the call means. A plain rule decides, not a language model: a clear yes or no
// settles it, and anything else (a question, a longer sentence, a mix of both) is left for the agent to handle.

const YES = ['confirm', 'confirmed', 'yes', 'yeah', 'yep', 'okay', 'ok', 'accept', 'accepted', 'sure', 'haan', 'han', 'ha', 'theek', 'thik',
  'कन्फर्म', 'कंफर्म', 'कन्फ़र्म', 'हाँ', 'हां', 'हा', 'जी', 'ठीक', 'स्वीकार', 'होय', 'हो', 'चालेल']
const NO = ['no', 'nope', 'decline', 'declined', 'cannot', "can't", 'cant', 'refuse', 'nahi', 'nahin', 'नहीं', 'नही', 'मना', 'नको', 'नाही']
const ASKING = ['when', 'what', 'where', 'why', 'how', 'who', 'which', 'will', 'would', 'can', 'could', 'do', 'does', 'is', 'are',
  'कब', 'क्या', 'कहाँ', 'कहां', 'क्यों', 'कैसे', 'कौन', 'कितना', 'कितने', 'केव्हा', 'काय', 'कुठे', 'का', 'कसे']

export function decide(reply: string): 'confirmed' | 'declined' | null {
  const text = reply.trim().toLowerCase()
  if (!text || /[?？]/.test(text)) return null
  const words = text.replace(/[.,!।'"“”‘’]/g, ' ').split(/\s+/).filter(Boolean)
  if (words.length === 0 || words.length > 5) return null // a long sentence is a conversation, not an answer
  if (words[0] === '1' && words.length === 1) return 'confirmed'
  if (words[0] === '2' && words.length === 1) return 'declined'
  const no = words.some((w) => NO.includes(w))
  const yes = words.some((w) => YES.includes(w))
  if (no) return 'declined' // "no" wins: "no, not okay" is a no
  if (ASKING.includes(words[0])) return null
  return yes ? 'confirmed' : null
}
