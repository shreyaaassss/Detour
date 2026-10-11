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
  micOff: { en: 'The microphone is not switched on yet. Type, or use the buttons.', hi: 'माइक्रोफ़ोन अभी चालू नहीं है। लिखें या बटन दबाएँ।', mr: 'मायक्रोफोन अजून सुरू नाही. लिहा किंवा बटण दाबा.' },
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
