# The breakdown rescue flow

Run the backend and the frontend (see the README), then open these four screens. On a laptop use four
different browsers or devices if you can: a browser shares about six connections per server across tabs.

| Screen | URL | Who |
|---|---|---|
| Dispatcher | `/dispatch` | the laptop operator |
| Stranded driver | `/driver?as=Ravi` | Phone 1 |
| Head of logistics | `/head` (or `/head?as=backup`) | Phone 2 |
| Rescue driver | `/driver?as=Meera` | Phone 3 |

## The story, step by step

1. **Ravi reports.** On his screen he taps the microphone and speaks, or types, or taps *Vehicle broke down* and a place. The app reads it
   back in his language ("हडपसर येथे गाडी बिघडली. डिलिव्हरी D7 ची वेळ 15:00. बरोबर आहे का?"). He taps yes.
   An unknown place, or two places, is rejected and he is asked to choose from the list. Nothing is guessed.
2. **The head is alerted** with a ranked list of rescue drivers. Each is tried for real: the engine replans with that
   driver fixed as the rescuer and the independent validator checks it. With the demo data:

   | Driver | Reaches the van | Leaves | Delivers D7 | Result |
   |---|---|---|---|---|
   | Meera (V4) | 14:15 | 14:20 | 14:50 | rank 1 |
   | Sana (V3) | 14:20 | 14:25 | 14:55 | rank 2 |
   | Imran (V5) | 14:23 | 14:28 | 14:58 | rank 3 |
   | Arjun (V1) | | | 15:07 | not possible: misses the 15:00 window |

   The head sees the impact on every other delivery and approves up to three drivers, in the order to ask them.
3. **Meera gets an offer** in the app, in Hindi, with a 60-second countdown and Accept and Decline.
4. **No answer in 60 s: the call is placed.** The dispatcher's *Rescues* tab shows the ring and, until a real phone
   line is connected, buttons to **simulate the call** (picks up, says confirm, says no, no answer, voicemail,
   unclear). This is Plan B for the demo.
5. **She says confirm.** The engine re-validates (time has passed), commits the plan, and only now is Ravi told
   "Meera (V4) is on the way. ETA 14:15." The dispatcher sees the diff and a draft customer message for each
   delivery that changed.

Variants: a driver who does not answer (the next approved driver gets a fresh 60 s push), nobody accepting (D7 is
marked undeliverable and the head, dispatcher and driver are told), and a silent head (after 120 s the backup
approver is asked).

## Rules the code enforces

- **The plan does not change until a rescuer accepts and the result re-validates.** A driver's report only
  creates a proposal. (The PRD registers the failure when the driver confirms; that would change the plan, and
  promise help, before the head had approved. This is the one deliberate change.)
- **One claim only.** The first acceptance wins. A late tap, a second tap or a late call result is refused and logged.
- **Closed offers stay closed.** After 60 s the push is closed; a tap on it is refused. A call is answered on the call.
- **Approval binds to the shortlist and the plan.** If the plan changes (a closure, an urgent delivery, another
  breakdown), the approval is void, open offers are closed, drivers are told to stand down, and the head gets a
  fresh proposal.
- **No double-booking.** A driver with an open offer for one breakdown shows as busy for another.
- **If nobody accepts**, the engine does not hand D7 to someone who never agreed: it is reported undeliverable.
- **The other parcels on the broken vehicle** are placed by the engine at commit and shown in the diff. Only the
  main rescue (the most urgent parcel) needs a driver's consent.
- **Customer messages** are drafted from the plan's facts. Nothing is sent from the app.

## Simulated time

Offer timers run in real seconds, but plans are timed in simulated minutes. The simulated clock is **held at
14:05** for the demo, so every run gives the same numbers. The dispatcher can set it or run it live in the
*Rescues* tab. Accepting re-validates at the current simulated time, so a slow answer in live mode can make a
driver no longer feasible; the next approved driver is offered.

## Timers

| Timer | Default | Override |
|---|---|---|
| Push offer | 60 s (required) | `DETOUR_PUSH_TIMEOUT` |
| Driver read-back | 30 s, re-prompted up to 3 times | `DETOUR_DRIVER_CONFIRM` |
| Head response | 120 s, then the backup approver | `DETOUR_HEAD_RESPONSE` |
| Call ring | 25 s, no answer counts as declined | `DETOUR_RING_TIMEOUT` |
| Call conversation | 45 s, then treated as no response | `DETOUR_CONVERSATION_LIMIT` |

## Differences from the PRD's worked example

- The engine gives **D8 to Meera as well** (she is already collecting at Hadapsar), not to Arjun. D9 is broken as in the PRD.
- Meera's pickup is two parcels at one handover (14:15 to 14:20), then D7 at 14:50 as in the PRD.
- Spoken reports and spoken read-backs, offers and updates are in ([VOICE.md](VOICE.md)). The real phone call is Phase 9; until
  then the call is simulated from the dispatcher screen.
