// Words on the driver's screen. Messages about the situation come from the server already translated.
export type Lang = 'en' | 'hi' | 'mr'
export const LANGS: { id: Lang; label: string }[] = [
  { id: 'en', label: 'English' },
  { id: 'hi', label: 'हिन्दी' },
  { id: 'mr', label: 'मराठी' },
]

const UI = {
  title: { en: 'Report a problem', hi: 'समस्या बताएँ', mr: 'समस्या सांगा' },
  whatHappened: { en: 'What happened?', hi: 'क्या हुआ?', mr: 'काय झाले?' },
  placeholder: { en: 'For example: my truck broke down near Hadapsar', hi: 'जैसे: मेरी गाड़ी हडपसर के पास खराब हो गई', mr: 'उदा. माझी गाडी हडपसर जवळ बिघडली' },
  send: { en: 'Send report', hi: 'रिपोर्ट भेजें', mr: 'अहवाल पाठवा' },
  brokeDown: { en: 'Vehicle broke down', hi: 'गाड़ी खराब हो गई', mr: 'गाडी बिघडली' },
  whereAreYou: { en: 'Where are you?', hi: 'आप कहाँ हैं?', mr: 'तुम्ही कुठे आहात?' },
  correct: { en: 'Yes, that is right', hi: 'हाँ, सही है', mr: 'हो, बरोबर आहे' },
  changePlace: { en: 'Change the place', hi: 'जगह बदलें', mr: 'ठिकाण बदला' },
  cancel: { en: 'Cancel', hi: 'रद्द करें', mr: 'रद्द करा' },
  accept: { en: 'Accept', hi: 'स्वीकार करें', mr: 'स्वीकारा' },
  decline: { en: 'Decline', hi: 'अस्वीकार करें', mr: 'नाकारा' },
  secondsLeft: { en: 'seconds left', hi: 'सेकंड बचे', mr: 'सेकंद उरले' },
  calling: { en: 'We are calling you now. Please answer the phone.', hi: 'हम आपको अभी कॉल कर रहे हैं। कृपया फ़ोन उठाएँ।', mr: 'आम्ही तुम्हाला आत्ता कॉल करत आहोत. कृपया फोन उचला.' },
  again: { en: 'Report again', hi: 'फिर से रिपोर्ट करें', mr: 'पुन्हा अहवाल द्या' },
  updates: { en: 'Updates', hi: 'अपडेट', mr: 'अपडेट्स' },
  tapToSpeak: { en: 'Tap and say what happened', hi: 'टैप करें और बताएँ क्या हुआ', mr: 'टॅप करा आणि काय झाले ते सांगा' },
  recording: { en: 'Listening. Tap again to send.', hi: 'सुन रहे हैं। भेजने के लिए फिर टैप करें।', mr: 'ऐकत आहे. पाठवण्यासाठी पुन्हा टॅप करा.' },
  sending: { en: 'Working out what you said…', hi: 'आपकी बात समझ रहे हैं…', mr: 'तुम्ही काय म्हणालात ते समजून घेत आहे…' },
  youSaid: { en: 'You said', hi: 'आपने कहा', mr: 'तुम्ही म्हणालात' },
  listen: { en: 'Listen', hi: 'सुनें', mr: 'ऐका' },
  micHttps: { en: 'The microphone needs a secure link (https). Type instead, or ask for the secure link.', hi: 'माइक्रोफ़ोन के लिए सुरक्षित लिंक (https) चाहिए। लिखें, या सुरक्षित लिंक माँगें।', mr: 'मायक्रोफोनसाठी सुरक्षित लिंक (https) हवी. लिहा किंवा सुरक्षित लिंक मागा.' },
  micDenied: { en: 'The microphone is blocked. Allow it in the browser, or type.', hi: 'माइक्रोफ़ोन बंद है। ब्राउज़र में अनुमति दें, या लिखें।', mr: 'मायक्रोफोन बंद आहे. ब्राउझरमध्ये परवानगी द्या, किंवा लिहा.' },
  didntHear: { en: 'I could not hear that. Try again, or type it.', hi: 'मैं सुन नहीं पाया। फिर कोशिश करें, या लिखें।', mr: 'मला ऐकू आले नाही. पुन्हा प्रयत्न करा किंवा लिहा.' },
  soundOn: { en: 'Sound on', hi: 'आवाज़ चालू', mr: 'आवाज सुरू' },
  soundOff: { en: 'Sound off', hi: 'आवाज़ बंद', mr: 'आवाज बंद' },
  confirmTitle: { en: 'Is this correct?', hi: 'क्या यह सही है?', mr: 'हे बरोबर आहे का?' },
  noUpdates: { en: 'Nothing yet.', hi: 'अभी कुछ नहीं।', mr: 'अजून काही नाही.' },
  iAm: { en: 'I am', hi: 'मैं हूँ', mr: 'मी आहे' },
} satisfies Record<string, Record<Lang, string>>

export type UiKey = keyof typeof UI
export const UI_KEYS = Object.keys(UI) as UiKey[]
export function ui(key: UiKey, lang: Lang): string {
  return UI[key][lang]
}
export function pick(text: Record<string, string> | undefined, lang: Lang): string {
  return text?.[lang] ?? text?.en ?? ''
}
