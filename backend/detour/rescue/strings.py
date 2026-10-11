"""Messages in the three languages of the demo. Every fact (place, time, parcel, ETA) is filled in by the
engine; nothing here is generated, so a message can never promise something the plan does not.
"""

from __future__ import annotations

LANGS = ("en", "hi", "mr")

TEXT: dict[str, dict[str, str]] = {
    "readback": {
        "en": "Breakdown at {place}, delivery {parcel} due {due}. Correct?",
        "hi": "{place} पर गाड़ी खराब हुई। डिलीवरी {parcel} का समय {due} है। क्या यह सही है?",
        "mr": "{place} येथे गाडी बिघडली. डिलिव्हरी {parcel} ची वेळ {due}. बरोबर आहे का?",
    },
    "readback_empty": {
        "en": "Breakdown at {place}. No parcels are left on the vehicle. Correct?",
        "hi": "{place} पर गाड़ी खराब हुई। गाड़ी में कोई पार्सल बाकी नहीं है। क्या यह सही है?",
        "mr": "{place} येथे गाडी बिघडली. गाडीत कोणतेही पार्सल शिल्लक नाही. बरोबर आहे का?",
    },
    "reprompt": {
        "en": "Please confirm the report: is it correct?",
        "hi": "कृपया रिपोर्ट की पुष्टि करें: क्या यह सही है?",
        "mr": "कृपया अहवालाची खात्री करा: हे बरोबर आहे का?",
    },
    "awaiting": {
        "en": "Request sent to logistics. Stay with the vehicle.",
        "hi": "अनुरोध लॉजिस्टिक्स को भेज दिया गया है। गाड़ी के पास ही रहें।",
        "mr": "विनंती लॉजिस्टिक्सला पाठवली आहे. गाडीजवळच थांबा.",
    },
    "on_the_way": {
        "en": "{driver} ({vehicle}) is on the way. ETA {eta}. Hand over parcel {parcel}.",
        "hi": "{driver} ({vehicle}) आ रहे हैं। पहुँचने का समय {eta}। पार्सल {parcel} सौंप दें।",
        "mr": "{driver} ({vehicle}) येत आहेत. पोहोचण्याची वेळ {eta}. पार्सल {parcel} त्यांच्याकडे सोपवा.",
    },
    "no_rescue": {
        "en": "No rescue driver is available right now. Logistics will contact you.",
        "hi": "अभी कोई बचाव ड्राइवर उपलब्ध नहीं है। लॉजिस्टिक्स आपसे संपर्क करेगा।",
        "mr": "सध्या कोणताही मदतनीस चालक उपलब्ध नाही. लॉजिस्टिक्स तुमच्याशी संपर्क करेल.",
    },
    "cancelled": {
        "en": "Logistics cancelled this request. Logistics will contact you.",
        "hi": "लॉजिस्टिक्स ने यह अनुरोध रद्द कर दिया है। लॉजिस्टिक्स आपसे संपर्क करेगा।",
        "mr": "लॉजिस्टिक्सने ही विनंती रद्द केली आहे. लॉजिस्टिक्स तुमच्याशी संपर्क करेल.",
    },
    "offer": {
        "en": "Urgent. Pick up parcel {parcel} at {site}, deliver to {dest} by {due}. Accept or decline.",
        "hi": "अत्यावश्यक। {site} से पार्सल {parcel} उठाएँ और {dest} में {due} तक पहुँचाएँ। स्वीकार करें या अस्वीकार करें।",
        "mr": "तातडीचे. {site} येथून पार्सल {parcel} घ्या आणि {dest} येथे {due} पर्यंत पोहोचवा. स्वीकारा किंवा नाकारा.",
    },
    "call_script": {
        "en": (
            "This is an automated call from DeTour logistics. Urgent: pick up parcel {parcel} from a broken-down van "
            "at {site} and deliver to {dest} by {due}. Your logistics head approved this. "
            "To accept, press 1 or say confirm. To decline, press 2 or say no."
        ),
        "hi": (
            "यह डीटूर लॉजिस्टिक्स की ऑटोमेटेड कॉल है। अत्यावश्यक: {site} में खराब गाड़ी से पार्सल {parcel} उठाएँ "
            "और {dest} में {due} तक पहुँचाएँ। लॉजिस्टिक्स प्रमुख ने इसे मंज़ूर किया है। "
            "स्वीकार करने के लिए 1 दबाएँ या कन्फर्म बोलें। मना करने के लिए 2 दबाएँ या नहीं बोलें।"
        ),
        "mr": (
            "हा डीटूर लॉजिस्टिक्सकडून आलेला स्वयंचलित कॉल आहे. तातडीचे: {site} येथे बिघडलेल्या गाडीतून पार्सल "
            "{parcel} घ्या आणि {dest} येथे {due} पर्यंत पोहोचवा. लॉजिस्टिक्स प्रमुखांनी मंजुरी दिली आहे. "
            "स्वीकारण्यासाठी 1 दाबा किंवा कन्फर्म म्हणा. नकार देण्यासाठी 2 दाबा किंवा नाही म्हणा."
        ),
    },
    "accepted_thanks": {
        "en": "Confirmed. Go to {site}, collect parcel {parcel}, deliver by {due}. Thank you.",
        "hi": "पुष्टि हो गई। {site} जाएँ, पार्सल {parcel} लें और {due} तक पहुँचाएँ। धन्यवाद।",
        "mr": "निश्चित झाले. {site} येथे जा, पार्सल {parcel} घ्या आणि {due} पर्यंत पोहोचवा. धन्यवाद.",
    },
    "stood_down": {
        "en": "This offer is closed. No action needed.",
        "hi": "यह प्रस्ताव बंद हो गया है। कोई कार्रवाई ज़रूरी नहीं।",
        "mr": "ही विनंती बंद झाली आहे. कोणतीही कृती आवश्यक नाही.",
    },
}


def say(key: str, lang: str, **facts: str) -> str:
    table = TEXT[key]
    return table.get(lang, table["en"]).format(**facts)


def say_all(key: str, **facts: str | dict[str, str]) -> dict[str, str]:
    """The same message in every language, so any screen can show the reader's own.
    A fact may be a dict of language -> text (a place name in the reader's own script)."""
    out = {}
    for lang in LANGS:
        resolved = {k: (v.get(lang, v["en"]) if isinstance(v, dict) else v) for k, v in facts.items()}
        out[lang] = say(key, lang, **resolved)
    return out


def local_names(name: str, aliases: list[str]) -> dict[str, str]:
    """A place's name per language: Devanagari for Hindi and Marathi when we know it, else the usual name."""
    deva = next((a for a in aliases if any("\u0900" <= ch <= "\u097f" for ch in a)), None)
    return {"en": name, "hi": deva or name, "mr": deva or name}
