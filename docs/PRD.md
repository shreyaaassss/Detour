# DeTour — Product Requirements Document

VORTEXA 3.0 · Problem S-01 (ReRoute: Dynamic Fleet & Delivery Replanning) · Draft v1 · 11 October 2026 · Status: ready to build

## 1. Overview

DeTour is a delivery-planning and replanning system for a small fleet. It assigns deliveries to vehicles under capacity and time-window constraints, then replans from the current state when something goes wrong: a road closure, a vehicle failure, or an urgent delivery.

This PRD also defines the headline feature, a voice-driven **breakdown rescue flow**. A stranded driver reports a breakdown by voice in their own language, the head of logistics approves a rescue plan, and a nearby driver is offered the job by push notification. If that driver does not respond within **60 seconds**, an automated phone call follows.

**Goal:** a live-testable MVP that satisfies every S-01 requirement in the VORTEXA booklet and demonstrates a realistic, safe human-in-the-loop emergency workflow.

## 2. Goals and non-goals

**Goals**

- Build a valid plan: no capacity overload at any point, time windows met, waiting shown, unplaceable deliveries reported with a reason.
- Replan from the current state for all three disruption types. Completed stops stay fixed, and a failed vehicle gets no stops after its failure time.
- Show original and revised plans side by side, with every delivery classed as kept, moved, or broken, each with a reason.
- Deliver the voice breakdown rescue flow end to end, with human approval.
- Keep working when ElevenLabs, telephony, or the LLM is unavailable.

**Non-goals**

- Live maps, GPS, or traffic data. Only simulated coordinates and a simulated travel-time matrix are used.
- Real customer data, real payments, or public deployment.
- Provably optimal routing. The solver is a heuristic and its limits are stated in the UI.
- SMS to Indian numbers (needs registration). In-app notification is used for the final driver message instead.

## 3. Roles

| Role | In the demo | Responsibilities |
|---|---|---|
| Dispatcher | Laptop operator | Loads scenario, applies disruptions, reviews plan diff, approves customer messages |
| Stranded driver | Phone 1 | Reports breakdown by voice, confirms read-back, receives rescue status |
| Head of logistics | Phone 2 | Receives alert, approves the rescue shortlist |
| Rescue driver | Phone 3 | Receives push offer, accepts or declines, receives escalation call |
| Backup approver | Simulated | Takes over if the head does not respond in time |
| System | Backend | Engine, validator, state machine, audit log |

## 4. Design principles

1. **The engine decides, AI assists.** Assignment, feasibility, and timing come from deterministic code. AI transcribes, extracts, and speaks. It never assigns.
2. **Hard constraints never relax.** Capacity, time windows, closures, and frozen stops hold in every plan and every fallback.
3. **Humans approve consequential actions.** The head approves an exact ranked shortlist. If the plan changes afterwards, the approval is void.
4. **Validate everything extracted.** An unknown location is rejected, not guessed. Voice input passes the same validation as typed input.
5. **Honest messaging.** Nobody is told help is coming until the assignment is committed.
6. **Degrade gracefully.** Every voice step has a text or button fallback.
7. **Audit everything.** Every action, refusal, timeout, and escalation is recorded with actor and time.

## 5. Functional requirements

### 5.1 Planning engine

- **FR-1 Inputs:** depot, vehicles with capacity, deliveries with size, time window and service time, a location list, and a travel-time matrix. Loadable from JSON or CSV, plus a built-in demo scenario.
- **FR-2 Solver:** cheapest-insertion construction followed by local search (relocate, swap, 2-opt). Limits are documented in the UI.
- **FR-3 Time-dependent travel:** `travel(a, b, departure_time)` returns the base time, or the inflated time when the departure falls inside a closure window.
- **FR-4 Per-stop output:** arrival, waiting, service start, departure, and load after the stop.
- **FR-5 Unplaceable deliveries:** listed with the specific reason, for example the window closes before any vehicle can arrive.

### 5.2 Disruptions

- **FR-6 Road closure:** a location pair, added minutes or a multiplier, a start time and an end time.
- **FR-7 Vehicle failure:** vehicle, failure time, and location.
- **FR-8 Urgent delivery:** location, size, and time window, added mid-day.
- **FR-9 Text or voice description:** parsed into structured JSON (LLM with a rule-based fallback), previewed, then confirmed by the dispatcher before taking effect. A report naming an unknown location is rejected.
- **FR-10 Replan from state at time T:** each vehicle's position, time, and remaining load are reconstructed. Completed stops are frozen. Objective order: fewest broken deliveries, then fewest moved, then distance and lateness.

### 5.3 Plan comparison

- **FR-11** Side-by-side original and revised plans. Each delivery is classed:
  - **Kept:** same vehicle, window still met (any ETA shift is shown).
  - **Moved:** different vehicle, or materially different sequence or time.
  - **Broken:** cannot be served within its window, or cannot be served at all.
- **FR-12** Every classification carries a plain-language reason usable in a customer message.

### 5.4 Independent validator

- **FR-13** A separate module, sharing no code with the solver, re-checks any plan for capacity at every stop, time windows, closures, frozen stops, and the failed-vehicle rule.
- **FR-14** A plan that fails validation is never shown as valid, and a failing rescue assignment is never committed.

### 5.5 Audit log

- **FR-15** Append-only log of accepted changes, refusals, approvals, notifications, escalations, calls, and timeouts, each with actor, timestamp, and details. A hash chain over entries is an optional extra.

## 6. Breakdown rescue flow

### 6.1 Flow summary

1. The driver speaks the problem into the app in their language.
2. Speech-to-text produces a transcript. The system extracts the incident and validates the location against the known list.
3. The app reads the extracted incident back to the driver, who confirms.
4. The head receives a text alert with the incident summary.
5. The engine builds a ranked list of feasible rescue drivers. The head approves the shortlist (up to three) or picks another feasible driver.
6. The first candidate gets a push notification, voiced and with Accept and Decline buttons, and a **60-second countdown**.
7. If there is no response in 60 seconds, the AI calls the candidate, explains briefly, and waits for a yes or no.
8. On acceptance by tap or call, the system re-validates, commits, and updates the plan. The stranded driver is told who is coming and the ETA.
9. On decline or silence after the call, the next candidate on the approved shortlist gets the same push-then-call sequence.

### 6.2 State machine

| State | Meaning | Moves to |
|---|---|---|
| REPORTED | Voice captured, transcript extracted | DRIVER_CONFIRMED, or rejected if location unknown |
| DRIVER_CONFIRMED | Driver confirmed the read-back, location valid | AWAITING_HEAD |
| AWAITING_HEAD | Ranked proposal sent to head | HEAD_APPROVED, HEAD_TIMEOUT, CANCELLED |
| HEAD_APPROVED | Head approved shortlist of up to 3 | OFFER_PUSHED(1) |
| OFFER_PUSHED(i) | Push sent to candidate i, 60 s countdown | ACCEPTED(i), CANDIDATE_DECLINED(i), CALL_ESCALATED(i) |
| CALL_ESCALATED(i) | Automated call placed to candidate i | ACCEPTED(i), CANDIDATE_DECLINED(i) |
| CANDIDATE_DECLINED(i) | Declined, no answer, or no longer feasible | OFFER_PUSHED(i+1), or EXHAUSTED |
| ACCEPTED(i) | Candidate said yes (claim recorded) | COMMITTED, or CANDIDATE_DECLINED if re-validation fails |
| COMMITTED | Re-validated, plan updated, stranded driver notified | terminal |
| HEAD_TIMEOUT | Head did not respond in time | AWAITING_HEAD (backup approver) |
| EXHAUSTED | No approved candidate accepted | delivery marked broken, head and customer notified |
| CANCELLED | Withdrawn by the head or dispatcher | terminal |

### 6.3 Timers

| Timer | Value | Notes |
|---|---|---|
| Push offer timeout | **60 seconds** | Required. Visible countdown on the driver and dispatcher screens |
| Driver read-back confirmation | 30 s (proposed) | Then the report is re-prompted |
| Head response | 120 s (proposed) | Then escalate to the backup approver |
| Call ring timeout | 25 s (proposed) | No answer counts as declined |
| Call conversation limit | 45 s (proposed) | Then treated as no response |

All timers except the 60-second push timeout are configurable defaults.

### 6.4 Call script (keep under 20 seconds)

> This is an automated call from DeTour logistics. Urgent reassignment: pick up parcel D7 from a broken-down van at Hadapsar and deliver to Kothrud Clinic by 3 PM. Your logistics head has approved this. To accept, say confirm. To decline, say no.

The agent speaks only facts supplied by the engine. A single clear confirm or no is required. Anything ambiguous is repeated once, then treated as no response.

### 6.5 Rules

- **One claim only.** The state machine records exactly one acceptance. A tap and a call answer arriving together cannot both win.
- **Re-validate on accept.** Time has passed, so feasibility is checked again before commit. If it fails, move to the next candidate.
- **Close finished offers.** After a decline, timeout, or acceptance, the old push and call are marked closed so a late response is refused and logged.
- **Candidates must stay feasible themselves.** A rescue driver's own remaining deliveries must still meet their windows after inserting the pickup and delivery.
- **Handover is modelled.** The rescue includes a pickup stop at the breakdown location, a handover service time, then the delivery.
- **Approval binds to the shortlist.** A candidate outside the approved list needs a new approval.
- **No early promises.** Before commit, the stranded driver sees "request sent, awaiting approval".

## 7. Worked example

**Setup (simulated data).** It is 2:00 PM and the baseline plan is valid. Van V2, driven by Ravi, carries urgent medicine delivery **D7** for Kothrud Clinic, window closing at **3:00 PM**, plus D8 and D9. Ravi is near Hadapsar. Travel Hadapsar to Kothrud is 30 minutes in the simulated matrix, and handover takes 5 minutes.

**Candidate evaluation by the engine**

| Driver | Reaches Hadapsar | Leaves after handover | Delivers D7 | Result |
|---|---|---|---|---|
| Meera (V4) | 2:15 | 2:20 | 2:50 | Feasible, rank 1 |
| Sana (V3) | 2:20 | 2:25 | 2:55 | Feasible, rank 2 |
| Imran (V5) | 2:23 | 2:28 | 2:58 | Feasible, rank 3 |
| Arjun (V1) | 2:32 | 2:37 | 3:07 | Rejected: misses 3:00 PM window |

Ranking rule: earliest delivery time, ties broken by least disruption to the rescuer's own route.

**Timeline**

| Time | What happens | Who or what |
|---|---|---|
| 2:05:00 | Ravi taps the mic and says in Marathi (translated): "My truck broke down near Hadapsar and I can't make the 3 PM delivery." | Speech-to-text |
| 2:05:15 | System extracts: location Hadapsar (matches known list), vehicle V2, affected delivery D7 due 3:00 PM, reason breakdown. The app reads it back in Marathi: "Breakdown at Hadapsar, delivery D7 due 3 PM. Correct?" | Extraction, text-to-speech |
| 2:05:25 | Ravi taps Yes. App shows: "Request sent to logistics. Stay with the vehicle." A vehicle-failure disruption at 2:05 is registered. | State: DRIVER_CONFIRMED |
| 2:05:30 | Engine ranks candidates (table above) and replans V2's other deliveries. | Engine, validator |
| 2:05:35 | Head's phone gets an alert: "V2 broken down at Hadapsar carrying urgent D7 due 3 PM. Recommended: Meera (V4). 2 backups. Review now." | State: AWAITING_HEAD |
| 2:07:00 | Head opens the console, reads the transcript and read-back, sees the shortlist and the impact on other deliveries, and approves Meera, Sana, Imran. | Human approval, logged |
| 2:07:05 | Meera's app shows and speaks: "Urgent. Pick up parcel D7 at Hadapsar, deliver to Kothrud Clinic by 3 PM. Accept or Decline." A **60-second countdown** starts. | State: OFFER_PUSHED(1) |
| 2:08:05 | Meera has not tapped. The timer hits zero and the system places the call. | State: CALL_ESCALATED(1) |
| 2:08:10 | Call connects and the script plays. | Voice agent |
| 2:08:25 | Meera says: "Confirm." | State: ACCEPTED(1) |
| 2:08:27 | Re-validation passes (still arrives 2:15, delivers 2:50). Plan committed. | State: COMMITTED |
| 2:08:30 | Ravi's app: "Meera (V4) is on the way. ETA 2:15. Hand over parcel D7." | In-app notification |
| 2:08:30 | Plan view: **D7 moved** V2 to V4 (reason: vehicle breakdown). D8 **moved** V2 to V1. D9 **broken**: window closes before any vehicle can reach it. Customer messages are drafted for dispatcher approval. | Diff view |

**Variant A: first candidate does not answer.** Meera's call rings 25 seconds with no answer, so she is marked declined. Sana receives a push at 2:08:40 with a fresh 60-second countdown, and the same sequence continues.

**Variant B: nobody accepts.** After Imran, the state becomes EXHAUSTED. D7 is marked broken with the reason, and the head and dispatcher are notified so the customer can be told honestly.

**Variant C: head silent.** After 120 seconds with no response, the alert goes to the backup approver and the escalation is logged.

## 8. Screens

**Driver app**

- Large mic button and a language selector.
- Transcript with read-back and Yes or Edit.
- Status banner showing "awaiting approval", then "driver on the way".
- Offer card with spoken summary, Accept and Decline buttons, and the 60-second countdown.
- Notification feed.

**Head console**

- Incident card with transcript, extracted fields, and read-back status.
- Ranked shortlist with ETAs, plus rejected candidates and the reason for each.
- Impact summary for other deliveries.
- Actions: approve shortlist, choose another feasible driver, reject. Response timer shown.

**Dispatcher dashboard**

- Plan table and SVG map on simulated coordinates, plus a per-vehicle timeline.
- Disruption controls with preset buttons for the demo.
- Original and revised plan diff with kept, moved, broken.
- Validator badge, live escalation timers, and audit log view.

## 9. Data model

- **Location:** id, name, x, y.
- **Vehicle:** id, capacity, start location, status.
- **Driver:** id, name, vehicle, phone reference (from environment config), language.
- **Delivery:** id, location, size, window start and end, service time, priority flag.
- **Plan, Route, Stop:** vehicle, ordered stops, arrival, wait, departure, load, frozen flag.
- **Disruption:** type, parameters, effective time, source (structured, text, voice), confirmed by.
- **Incident:** id, reporter, transcript, extracted fields, state, shortlist, approved by, current candidate.
- **Offer:** incident, candidate, channel (push or call), sent at, closed at, outcome.
- **AuditEvent:** id, time, actor, action, details, previous hash (optional).

## 10. API sketch

| Endpoint | Purpose |
|---|---|
| `POST /plan` | Build initial plan from scenario |
| `POST /disruptions` | Apply a structured disruption (after preview and confirm) |
| `POST /disruptions/parse` | Parse text into a structured preview |
| `POST /incidents/voice` | Upload audio, return transcript and extracted fields |
| `POST /incidents/{id}/confirm` | Driver confirms the read-back |
| `GET /incidents/{id}/proposal` | Ranked feasible shortlist with rejected candidates |
| `POST /incidents/{id}/approve` | Head approves a shortlist |
| `POST /offers/{id}/respond` | Candidate accepts or declines (tap) |
| `POST /telephony/webhook` | Call outcome from the voice agent |
| `GET /plan/diff` | Original vs revised, with classifications |
| `POST /validate` | Run the independent validator |
| `GET /audit` | Audit log |

## 11. AI and ElevenLabs usage

| Capability | Service | Fallback |
|---|---|---|
| Voice report to text | ElevenLabs Scribe speech-to-text | Browser Web Speech API, or typed text |
| Read-back and offer speech | ElevenLabs text-to-speech, cached audio | Browser speech synthesis |
| Incident extraction | LLM with a fixed JSON schema | Keyword and regex rules plus location-list matching |
| Escalation call | ElevenLabs voice agent over a telephony provider, to three verified numbers | Web voice session in a second browser tab, or text accept and decline |
| Customer message wording | Templates filled from engine facts, optional LLM polish | Templates only |

**Rules**

- AI output never changes a plan, a time, or an assignment. Only the engine and authorized humans do.
- Extracted locations must match the known list or the report is rejected.
- ETAs in any message come from engine output, never from generated text.
- Free-tier credit limits are small, so pre-generate and cache audio, keep scripts short, and avoid long live rehearsals.
- Telephony setup details, including trial-account restrictions to verified numbers, must be confirmed against current provider and ElevenLabs documentation before the event.
- API keys and phone numbers live in environment variables and are never committed.

## 12. Edge cases

- Speech misrecognised: the read-back catches it, and the driver can edit or retype.
- Unknown or ambiguous location: rejected with a prompt to choose from known locations.
- Two vehicles fail close together: the incident queue handles them in order, and candidates are not double-assigned.
- Candidate's own route would break: marked infeasible with the reason.
- Plan changed after approval: approval is void and the head re-approves.
- Late tap after a call is already accepted: refused and logged.
- Call answered by voicemail or unclear speech: treated as no response.
- Network loss: queued messages retry, and the dispatcher can enter responses manually.
- Voice services down: the full flow still runs on text and buttons.

## 13. Demo plan

**Phones.** Phone 1 is the stranded driver, Phone 2 is the head, Phone 3 is the rescue driver and receives the real call. Extra candidates are simulated entries in the data. Both teammates must consent to automated calls, and the call opens by stating it is automated.

**Script**

1. Load the demo scenario and show the valid baseline plan with the validator badge.
2. Phone 1 reports the breakdown by voice. Show the transcript and read-back.
3. Phone 2 receives the alert and approves the shortlist.
4. Phone 3 gets the push and ignores it. The 60-second countdown is visible on the dispatcher screen.
5. The call arrives on Phone 3 and the teammate says "confirm".
6. Show the commit, the stranded driver notification, and the diff view with kept, moved, broken.
7. Open the audit log and the validator result.
8. Show the road-closure and urgent-delivery presets to cover the remaining disruptions.

**Fallbacks.** Plan B is a "simulate escalation" button that opens a web voice session in a browser tab. Plan C is a text-only accept and decline. Test all three paths before the event.

## 14. Constraints and compliance

- **Working MVP, reproducible:** built-in scenario and preset disruption buttons give identical results on every run.
- **Meaningful AI:** speech understanding, structured extraction from free-form reports, and text disruption parsing, all with human confirmation.
- **Correctness:** capacity, windows, closures, and frozen stops follow explicit rules checked by the independent validator.
- **Data:** fictional only. No real personal records or live third-party systems, apart from the consenting teammates' own phones for the demo.
- **Infrastructure:** the core demonstration works with no paid service. External services are optional and each has a local fallback.

## 15. Build plan (12 hours)

| Hours | Work |
|---|---|
| 0–2 | Data model, scenario, solver (insertion plus local search), validator |
| 2–4 | Time-dependent travel, three disruptions, replan from state, diff classification |
| 4–6 | Incident state machine, audit log, head console, driver app skeleton |
| 6–8 | Speech-to-text and text-to-speech, extraction with fallback, read-back |
| 8–10 | Offer logic with 60-second timer, call escalation, Plan B and C fallbacks |
| 10–11 | Tests, demo scenario polish, README with assumptions and limits |
| 11–12 | Full dry runs and buffer |

Priority if time runs short: planning engine, validator, disruptions, and diff come first. Then the rescue flow on buttons and text. Voice and the real call are added last.

## 16. Acceptance criteria

- [ ] A plan never exceeds capacity at any stop, and the validator confirms it.
- [ ] Unplaceable deliveries are listed with a specific reason.
- [ ] A road closure changes travel time only inside its stated period.
- [ ] After a vehicle failure, that vehicle has no stops after the failure time, and completed stops are unchanged.
- [ ] An urgent delivery is inserted or reported as unplaceable with a reason.
- [ ] A text or voice report naming an unknown location is rejected.
- [ ] No disruption interpreted from text or voice applies without confirmation.
- [ ] Every delivery in the diff is kept, moved, or broken, with a reason.
- [ ] The head approves the exact shortlist. Changing the plan voids the approval.
- [ ] The push offer shows a 60-second countdown, and the call is placed at expiry.
- [ ] Only one acceptance can commit, and re-validation runs before commit.
- [ ] The stranded driver is told a rescuer is coming only after commit.
- [ ] Every step, refusal, timeout, and escalation appears in the audit log.
- [ ] The full flow works with voice services disabled.

## 17. Assumptions and open questions

**Assumptions**

- Undelivered parcels on a failed vehicle are recoverable and can be reassigned.
- Travel times, locations, and the 30-minute and 5-minute figures in the example are simulated.
- Delivery windows are hard constraints, and missing one makes a delivery broken.

**Open questions**

- Which languages will be supported for the demo (Marathi, Hindi, English)?
- What happens to a stop in progress at the moment of failure?
- Who is the backup approver in the demo, and is the timeout value acceptable?
- Can the telephony provider call all three verified numbers within the free-trial limits?
- Should rescue drivers be required to confirm by voice only, or is a tap during the call acceptable?
