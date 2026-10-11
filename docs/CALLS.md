# The escalation call

If a rescue driver does not answer the app within 60 seconds, an automated agent rings their phone. It says it is
automated, reads the engine's own script in Hindi, and takes **one clear answer by voice or keypad**:

- accept: say **कन्फर्म** (confirm), or press **1**
- decline: say **नहीं** (no), or press **2**

An unclear answer is repeated once. A second unclear answer, or no answer, counts as no response and the next approved
driver is tried. The answer goes through exactly the same rules as a tap: one claim only, re-validation, then commit.

The call language is Hindi (`DETOUR_CALL_LANGUAGE=hi`). Use `mr` or `en`, or `driver` to follow each driver's own language.

## Safety

- **Opt-in.** Nothing is dialled unless `DETOUR_CALLS=on`.
- **Only listed numbers.** The agent can only ring numbers you put in `.env`. A malformed number is reported by name and never guessed.
- **A cap.** At most `DETOUR_MAX_CALLS` calls per run (default 6).
- **The agent says only what the engine says.** The opening line is the exact script built from the plan's facts. The agent is
  forbidden to add or change a fact, discuss anything else, or promise anything.
- **Consent.** Only ring someone who has agreed to receive an automated call. The call opens by saying it is automated.
- **The phone line is optional.** Without it, the dispatcher's *simulate the call* buttons drive the same code.

## What you need to set up

1. **A Twilio account and one phone number** (twilio.com). ElevenLabs places calls through it.
   - A *trial* Twilio account can only call numbers you have **verified** in Twilio (Console, Phone Numbers, Verified Caller IDs), and plays a
     short trial message first. That is fine for a demo. Whether a trial account can call numbers in India is for Twilio's own
     pages to say; check before the event, or upgrade the account.
   - Create a limited **API key** in Twilio (it gives an `SK...` SID and a secret) rather than using your main credentials.
2. **Connect the number in ElevenLabs.** Agents, then Phone numbers, then Import a Twilio number: enter a label, the number, the Twilio
   SID and the secret. Copy the number's id into `.env` as `ELEVENLABS_PHONE_NUMBER_ID`.
3. **Put your demo phone number in `.env`** as `PHONE_RESCUE_DRIVER=+91...` (a plus sign, country code, number, no spaces).
   For one driver only use `PHONE_MEERA=+91...`. If the number is a Twilio trial's verified one, verify it in Twilio first.
4. **A public HTTPS address** for the agent to report its answer: start your tunnel (`cloudflared tunnel --url http://localhost:5173`)
   and put its `https://...` address in `.env` as `PUBLIC_BASE_URL`. Only `/telephony/agent` is used by the agent, and it needs a
   shared secret, but the tunnel makes the whole app reachable to anyone with the address while it runs.
5. **Create the agent**, once, and again whenever the tunnel address changes:

   ```
   cd backend && uv run python -m detour.telephony.setup
   ```

   It creates (or updates) the agent and its decision tool on your ElevenLabs account and prints the connected numbers.
6. **Switch calls on** with `DETOUR_CALLS=on`, restart the server, and open the dispatcher's *Rescues* tab. *Phone calls* says what is
   still missing or that real calls are on. **Test the phone line** rings the listed number once.

The agent is already created on your account (`DeTour rescue call`). Steps 1 to 4 and 6 need you.

## How an answer gets back

The agent calls a tool, `report_decision`, which posts to `POST /telephony/agent` with the shared secret. As a safety net the
server also checks the call every second. The decision is recorded in the call's transcript even when the tool could not reach
us, so a tunnel hiccup does not lose an answer. A keypad press arrives as a lone `1` or `2`; if the agent ended the call without
reporting, a lone keypad press still counts.

## Costs

ElevenLabs bills the call by conversation time on your plan, and Twilio bills the phone call. A demo call is under a minute.

## What was tested

The agent was tested against ElevenLabs' own conversation simulator: confirm by voice, no by voice, 1, 2, an unclear answer twice, and an off-topic
question (it refuses to discuss anything but the answer). The code is tested against a faked phone line. **No real call has been placed** until a
number is connected.

## Plan B: the call in the driver's browser (no phone line)

When the 60-second app offer times out, the rescue driver's page (`/driver?as=<name>`) shows a **Talk to the assistant now** button next to the countdown. Tapping it opens a live Hindi conversation with the same ElevenLabs agent, through the phone's microphone and speaker. Nothing is dialled, so no Twilio number or paid line is involved.

- The page asks the server for the call (`POST /offers/{id}/browser-session`). The server checks the offer is open and belongs to that driver, then returns the engine's own script, the facts the agent may repeat, and a short-lived signed address. The ElevenLabs key never reaches the browser.
- Browsers cannot send keypad tones, so the page has on-screen **1 · Accept** and **2 · Decline** buttons. They send the same "1" or "2" the agent already treats as a keypad answer. Speaking works too.
- Once connected, the page tells the server the conversation id (`.../browser-session/started`). The server marks the call answered and follows the conversation until the agent records a decision, the same way it follows a phone call. This needs no public address, because it reads the conversation rather than waiting for the agent's webhook.
- The same rules apply as for a phone call: one claim, a late answer is refused, an approval is void if the plan changed, and the simulate buttons remain as the fallback.
- The microphone needs `https` (or `localhost`): use a tunnel such as `cloudflared tunnel --url http://localhost:5173` for phones.
- It uses ElevenLabs conversation minutes. `DETOUR_MAX_CALLS` caps browser calls per run too.
- Needs only `ELEVENLABS_API_KEY` and the agent from `uv run python -m detour.telephony.setup`. `DETOUR_CALLS` and phone numbers are not needed.
