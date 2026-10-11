# DeTour: slide content

For VORTEXA 3.0, problem S-01 (ReRoute: Dynamic Fleet & Delivery Replanning).

Each slide has **On the slide** (short enough to read in a few seconds), **Visual** (what to put beside it) and **Say** (speaker notes).
Keep the on-slide text as written, or shorter. Do not add claims that are not in this file: everything here is either built and tested, or labelled as intended.

---

## Slide 1: PROBLEM STATEMENT

**On the slide**

**The plan rarely survives the day.**

- A dispatcher decides which vehicle carries which deliveries, in what order, within capacity and time windows.
- Then a road slows, a vehicle breaks down, or an urgent delivery arrives.
- Today the fix is a spreadsheet and experience.
- An unchecked change can overload a vehicle, miss a window, or undo a stop already completed.
- Someone must also decide what to tell each affected customer.

**What is really hard**

- A replan starts **mid-day**: finished stops cannot change, parcels are already on vans.
- A breakdown **strands parcels**, and someone has to agree to fetch them, fast.
- Reports arrive as words, in different languages, and may name a place the system does not know.

**Visual:** the day board after a breakdown (one lane crossed out, parcels shown as dashed ghosts, a red "now" line). It shows the problem in one picture.

**Say**

Every delivery day is planned in the morning and broken by noon. We looked at what actually makes that hard. It is not only the route maths. A replan is not a fresh plan, because half the day has already happened and parcels are physically on vehicles. And a breakdown is not only a calculation: it needs a person to approve and another to agree to drive out and collect the parcels, within minutes. We built for that whole situation.

---

## Slide 2: IDEA TITLE / PROPOSED SOLUTION

**Title: DeTour: replan from where the fleet actually is, and rescue with a person in charge**

**On the slide**

- **Plans the day** within capacity and time windows, showing arrival, wait and load at every stop.
- **Replans from the state of the day** after a road slowdown, a vehicle failure or an urgent delivery. Completed stops stay fixed.
- **Checks every plan** with a separate validator before it is shown.
- **Explains every change:** each delivery is *kept*, *moved* or *broken*, with a reason you can give a customer.
- **Breakdown rescue, with humans in charge:** the driver reports by voice in their own language, the head approves a ranked shortlist, a nearby driver gets an offer with a 60-second countdown, and if they do not answer an automated agent phones them.

**One rule:** the engine decides, AI assists, people approve.

**Visual:** the rescue flow figure from the report (seven steps), or a screenshot of the head console showing the ranked shortlist.

**Say**

DeTour has two halves. The first is a planning engine that can replan from the current state and prove its answer is valid. The second is a rescue procedure for the hardest case, a breakdown. The driver speaks, the head of logistics approves exactly who to ask, the first driver gets 60 seconds to answer in the app, and then an automated call. Only when someone accepts does the plan change and the stranded driver hear that help is coming. AI never makes a decision. It reads and speaks.

---

## Slide 3: TECHNICAL APPROACH

**On the slide**

**Engine (deterministic)**
- Cheapest insertion, then local search (relocate, swap, 2-opt).
- Objective in order: fewest undeliverable, fewest moved, least driving.
- Time-dependent travel: a closure slows only the legs that depart inside it.
- Replan from state at time T: completed stops frozen, pickup and handover modelled.

**Independent validator**
- Separate module, shares no code with the planner. It re-times every route from scratch.
- A plan that fails is never shown as valid.

**AI, each with a fallback**

| Task | Service | Fallback |
|---|---|---|
| Read a typed report | OpenAI language model, checked by a strict rule reader | Rule reader alone |
| Understand a spoken report | ElevenLabs speech-to-text (Hindi, Marathi, English) | Browser speech, typing |
| Speak read-backs and offers | ElevenLabs text-to-speech | Phone's own voice |
| Escalation call | ElevenLabs voice agent in the driver's browser, spoken answer or on-screen 1 and 2 | Simulate-the-call buttons |

**Guardrails:** every place must be on the known list and named in the text. Unknown places are rejected, never guessed. Nothing applies until the dispatcher confirms.

**Stack:** Python and FastAPI, React and TypeScript, live updates over server-sent events.

**Visual:** the architecture diagram (Figure 2 in the report). It is already drawn for this.

**Say**

The core is plain, checkable code. A heuristic builds the plan and a separate validator proves it. AI is used where language is the problem: reading what a dispatcher types, understanding a driver's voice, speaking back, and making the phone call. Each AI step is wrapped. A model's answer is only a proposal that must pass checks, a place the system does not know is refused, and every step has a local fallback so the core never depends on an outside service.

---

## Slide 4: FEASIBILITY AND VIABILITY

**On the slide**

**Feasible: it already works**
- A working prototype: planning, three disruptions, validator, comparison, dispatcher, driver and head screens, voice, and the rescue flow.
- More than 260 automated tests, including about 18,000 random disruption sequences that all produced valid plans.
- Speech tested in Hindi, Marathi and English: spoken sentences were transcribed back word for word.
- The phone agent was tested against the vendor's simulator for confirm, no, keypad 1, keypad 2, unclear answers, and an off-topic question.

**Fast enough** (measured, synthetic fleets, one laptop)

| Fleet | Plan the day | Replan after a breakdown |
|---|---|---|
| Demo: 5 vehicles, 12 deliveries | 2 ms | a few ms |
| 10 vehicles, 60 deliveries | 0.3 s | 0.1 s |
| 20 vehicles, 150 deliveries | 2.3 s | 0.3 s |
| 30 vehicles, 250 deliveries | 8.3 s | 0.5 s |

**Viable**
- The core runs with **no paid service**. AI layers are optional and each has a fallback.
- The whole demo story speaks about 1,000 characters. Speech is cached, with a spending cap per run.
- Real-world path: the engine reads travel times from a matrix, so a road-network source can supply it in place of the simulated one.
- Runs on a single server. Phones need only a browser.

**Honest limits:** the solver is a heuristic (not provably optimal); travel times are simulated; state lives in one process; the escalation call runs as a live voice conversation in the driver's browser, not over a phone line.

**Visual:** the table above, plus a small badge row: "260+ tests", "18,000 random disruption sequences valid", "no paid service needed for the core".

**Say**

We did not stop at a design. It is built and tested. The speed figures are from synthetic fleets on one laptop: a 30-vehicle day plans in about eight seconds and replans in half a second, and a replan on the demo fleet is instant. Cost is small because speech is cached and capped, and because the core needs no paid service at all. We are open about the limits: it is a heuristic, the travel times are simulated, and the escalation call is a voice conversation in the driver's browser rather than a real phone line.

---

## Slide 5: IMPACT AND BENEFITS

**On the slide**

**For the dispatcher**
- A fix in seconds instead of by hand, and **proof** that it is valid.
- Every delivery explained: kept, moved or broken, with a reason and a draft customer message.

**For the stranded driver**
- Reports in their own language, by voice, with a read-back to confirm.
- Is never promised help that has not been arranged.

**For the head of logistics**
- A ranked shortlist with times and the impact on every other delivery, then a single decision.
- A backup approver if they cannot respond in time.

**For customers**
- An honest, specific message, approved by a person.

**For the business**
- Designed to cut missed windows and the errors that come from rushed manual changes (not yet measured on a real fleet).
- A complete audit trail: who approved what, and when.

**Shown in the prototype** (fictional fleet)
- Urgent medicine due at 15:00 is delivered at **14:50** by the best of three feasible rescuers. The fourth is correctly rejected: it would arrive at 15:07.
- A parcel that cannot be saved is reported at once with the exact reason: earliest possible arrival 14:57, window closes 14:55.
- Zero invalid plans in 18,000 random disruption sequences.

**Visual:** the "who benefits" list as four icons, and the 14:50 versus 15:00 rescue table on the right.

**Say**

The benefit is speed with safety. The dispatcher gets a verified fix and an explanation they can pass on. The driver is heard in their own language and not misled. The head decides quickly with the facts in front of them. We want to be precise about what we are claiming: the figures on this slide come from our fictional demonstration fleet. We have not measured savings in a real fleet, so we do not quote percentages. What we can show is that every plan is proven valid, every change is explained, and a breakdown becomes a short procedure with a clear owner.

---

## Slide 6: DIFFERENTIATOR

**On the slide**

**What others do, and what DeTour does instead**

| Typical approach | DeTour |
|---|---|
| Spreadsheet and experience | Every change checked by an independent validator and explained delivery by delivery |
| Planners that solve the whole day again | Replans from the state at time T: history frozen, parcels stay on their vans |
| Tracking dashboards | Produces the fix, proves it feasible, shows its effect on every other delivery |
| A chatbot or AI that proposes changes | AI only fills in a form; every place is verified; nothing applies until a person confirms |
| Phone calls and messages for a breakdown | A structured procedure: ranked candidates, human approval, 60-second offer, automated call, one claim, full audit |

**Also**
- **Speaks the driver's language**, Hindi, Marathi or English, for reports and read-backs.
- **Fails safe:** a late tap or call is refused, an approval is void if the plan changes, and nobody is told help is coming until it is arranged.
- **Tamper-evident audit log:** every action and refusal, hash-chained.
- **Works without paid services:** every AI step has a local fallback.

**Visual:** a single line across the bottom: **"The engine decides. AI assists. People approve."**

**Say**

Most tools either re-plan from scratch, or show you where vehicles are, or let an AI suggest things nobody can check. DeTour does the unglamorous part well: it replans from the real state of the day, proves its answer, and explains it. And for a breakdown it gives a procedure that has a clear owner at every step, in the languages the people actually speak, that fails safe rather than fails silently.

---

## Numbers you can quote (and where they come from)

| Claim | Source |
|---|---|
| Rescue ranking: Meera reaches the van 14:15, leaves 14:20, delivers 14:50; Sana delivers 14:55; Imran 14:58; Arjun would deliver 15:07 and is rejected | The engine, on the demo scenario (a test checks it) |
| D9 broken: earliest arrival 14:57, window closes 14:55 | The engine, same scenario |
| More than 260 automated tests | 257 backend plus 11 frontend, as of the last run |
| About 18,000 random disruption sequences, all valid | Property test, run with three seeds at 6,000 examples each |
| Plan 250 deliveries with 30 vehicles in 8.3 s; replan in 0.5 s | Timed on one laptop, synthetic random fleet |
| Speech round trip exact in English, Hindi, Marathi | Spoken then transcribed back, live, with the real services |
| Demo story speaks about 1,000 characters | Counted by the pre-generation step |

## Do not claim

- Percentage savings, hours saved, or cost reductions. Nothing was measured on a real fleet.
- That a real phone call over a phone line has worked. The call is a browser voice conversation; no number was dialled.
- That it has been tried on physical phones, or at large scale. The speed table is synthetic.
- That the solver is optimal. It is a heuristic and says so.

## Optional extra slides, if the template allows

- **Cover:** DeTour, the one-line description, team name and ID, problem S-01.
- **Live demo:** the 5-step story (report, shortlist, offer, call, committed plan) with the day board before and after.
- **Architecture:** the full diagram, if you want it larger than on Slide 3.
- **Team / thank you.**
