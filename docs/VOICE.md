# Voice

Drivers can speak their report, and hear the read-back, offers and updates in their own language (English, Hindi,
Marathi). Every voice step has a fallback, so a flat phone, no signal for ElevenLabs, or no key still works.

## What happens

| Step | Primary | Fallback | Last resort |
|---|---|---|---|
| Driver speaks the report | The phone records; the server sends it to **ElevenLabs Scribe** (`scribe_v1`), which detects the language | The **browser's own** speech recognition, running at the same time | Type it, or tap *Vehicle broke down* and a place |
| The report is read back | **ElevenLabs** text-to-speech (`eleven_v4_turbo`, which covers Hindi and Marathi) | The phone's own voice (Marathi falls back to a Hindi voice if there is no Marathi one) | The text is on screen |
| Offers and updates | Same | Same | Same |

The transcript goes through exactly the same checks as typed text: an unknown place is rejected, and the driver
confirms the read-back before anything is sent on.

## Rules

- **The system only speaks what the engine produced.** `GET /voice/audio` takes a *reference* (a read-back, an offer or a
  note by id) and looks the sentence up. It never accepts free text, so the voice cannot say what the plan does not back
  and cannot be used to spend credits.
- **Every sentence is saved** on disk under `backend/data/audio/`, keyed by model, voice and text. Repeats are free, also
  after a restart. Two phones asking for the same new line pay once.
- **A spending cap.** `DETOUR_VOICE_BUDGET` (default 20,000 characters per run) stops new synthesis; saved lines still
  play, and phones fall back to their own voice. One message may be at most 500 characters.
- **Audio is not kept.** A recording is sent to ElevenLabs for transcription and discarded. The audit log keeps the
  transcript, the engine used and the sizes, never the audio.
- **Prepare the demo voices.** The dispatcher's *Rescues* tab has a button that speaks the demo story once, so the live
  run is instant and free. From a terminal: `cd backend && uv run python -m detour.voice.warm`. A test checks that these
  lines are exactly the ones the real flow says.

## Phones need HTTPS for the microphone

Browsers only allow the microphone on `https://` or `localhost`. For phones, open a tunnel:

```
cloudflared tunnel --url http://localhost:5173
```

and open the printed `https://...trycloudflare.com/driver?as=Ravi` on the phone. (A tunnel makes your dev server reachable by
anyone with that address while it runs. Close it when you are done.) Without HTTPS the screen says so and the driver types.
iPhones need a tap before they will play sound; the first tap on the mic or any button unlocks it.

## Setup

In `.env`: `ELEVENLABS_API_KEY`. Optional: `DETOUR_VOICE=off`, `ELEVENLABS_TTS_MODEL`, `ELEVENLABS_STT_MODEL`,
`ELEVENLABS_VOICE_ID` (and `ELEVENLABS_VOICE_EN`, `_HI`, `_MR` per language), `DETOUR_VOICE_BUDGET`. The default voice is
"Alice", a clear premade voice. In a round-trip test, speech made with it was transcribed back word for word in all three
languages.

## Cost

With `eleven_v4_turbo` a sentence costs a handful of credits. The whole demo story is under 1,000 characters. The
dispatcher screen shows what this run has spent and what the account shows.

## API

`GET /voice/status`, `GET /voice/audio?what=readback|offer|note&ref=...&lang=en|hi|mr` (supports byte ranges, which Safari
needs), `POST /incidents/voice?driver=Ravi` (raw audio body), `POST /voice/warm`.
