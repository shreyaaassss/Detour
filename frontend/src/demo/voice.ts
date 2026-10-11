// The browser's own voice reads the important answers aloud. If a device has none, the words are still on screen.
let soundOn = true
export function setVoice(on: boolean) { soundOn = on; if (!on && 'speechSynthesis' in window) window.speechSynthesis.cancel() }
export function speak(text: string) {
  if (!soundOn || !('speechSynthesis' in window)) return
  try {
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text)
    u.lang = 'en-IN'; u.rate = 1.02
    window.speechSynthesis.speak(u)
  } catch { /* no voice on this device: the words are on screen */ }
}

