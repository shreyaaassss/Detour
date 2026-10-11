# DeTour: test and demo script for the live site

Site: https://detour-cyan.vercel.app
Server health: https://detour-api-boqr.onrender.com/health

Use Chrome on a laptop. Headphones are best for the call. One person drives at a time: the demo is shared.

## Before you start (2 minutes)

| # | Do | Expect |
|---|---|---|
| 1 | Open the server health link | `{"status":"ok", ...}`. If it takes up to a minute, the server was asleep. |
| 2 | Open `https://detour-api-boqr.onrender.com/voice/status` | `"enabled":true` |
| 3 | Open the site | Black hero, the map draws an orange route |
| 4 | Click **Start the live demo** | The Plan page, five vehicle lanes, a notification at the bottom |

If anything looks stale at any point, press **Restart** in the top bar.

## The run

Each row: what to click or say, what you should see, and the line to say to the judges.

### 1. Plan
| Do | Expect | Say |
|---|---|---|
| Look at the Plan page | Five lanes. V2 (Ravi) has D1, D7, D8, D9. Each stop shows an arrival time; D5 shows "waits 16 min". | "This is the morning plan: five vehicles, twelve deliveries, each within capacity and its time window. Every stop shows when the van arrives and any waiting." |
| Click **Go to Driver** in the notification | Ravi's phone page, "What happened?" | |

### 2. Driver (Ravi)
| Do | Expect | Say |
|---|---|---|
| Tap the mic, say **"My truck broke down near Hadapsar"**, tap the mic again. (Or tap the suggested line.) | Your words in a black bubble. Then, spoken and on screen: "Breakdown at Hadapsar, delivery D7 due 15:00. Correct?" with place matched Hadapsar, vehicle V2, parcels D7, D8, D9. | "The driver reports in his own words. The system reads it back and waits. It never guesses a place it does not know." |
| Click **Yes, that is correct** | "Your report has gone to logistics. Stay with the vehicle." Notification: go to Head of logistics. | "Notice he is not told help is coming. Nobody has agreed yet." |
| Click **Go to Head of logistics** | | |

If the place is misheard: you get "I could not find a place I know" with a **Did you mean Hadapsar?** button. Click it. That is the rule working, and worth showing.

### 3. Head of logistics
| Do | Expect | Say |
|---|---|---|
| Read the list | 1 Meera, delivers D7 at 14:50. 2 Sana, 14:55. 3 Imran, 14:58. Arjun ruled out: 15:07, after the window closes at 15:00. | "The engine ranked who can collect the parcel and still deliver by 15:00. Arjun is ruled out, with the reason. A person decides who to ask." |
| Click **Approve 3 drivers** | "Approved by Head of logistics." Notification: go to Rescue driver. | |
| Click **Go to Rescue driver** | | |

### 4. Rescue driver (Meera)
| Do | Expect | Say |
|---|---|---|
| Wait a moment | The offer on Meera's phone, read aloud, with a 60-second ring | "One driver is asked at a time, with sixty seconds to answer." |
| Click **Do not answer (skip the 60 seconds)** | "No answer in the app, so DeTour is calling." A card: "DeTour is calling Meera." | "She did not answer, so the system calls her." |
| Choose English or हिन्दी, click **Answer the call**, allow the microphone | The agent speaks the request. A transcript appears. | "This is a live voice agent. It only knows what the planning engine told it." |
| When it says "Your turn", hold **Hold to talk** and ask **"When would I reach the van?"**, then release | It answers: reach Hadapsar 14:15, leave 14:20, deliver 14:50. Then asks if you accept. | |
| Hold, ask **"Will I get paid extra?"**, release | It says it does not have that information and logistics will follow up. | "It will not invent an answer." |
| Hold, say **"Confirm"**, release | "Recording the answer…", then "Accepted. The rescue is committed. Confirmed on the call." One button. | "Only now does the plan change." |
| Click **See what changed** | | |

Alternatives worth one run each: **Accept** in the first 60 seconds (commits without a call). **Decline** (the offer moves to Sana with a new countdown).

If the room is loud: use the on-screen **1 · Accept** button instead of speaking.

### 5. What changed
| Do | Expect | Say |
|---|---|---|
| Read the tiles | **9 Kept, 2 Moved, 1 Broken.** D7: V2 (Ravi) 14:20 → V4 (Meera) 14:50. D8: → V4 (Meera) 15:08. D9 broken: window closes 14:55, earliest arrival 14:57. | "Twelve deliveries. Nine untouched. Two moved to Meera. One we cannot save, and here is exactly why. Every change has a reason the dispatcher can give the customer." |
| Open **Compare the two plans in full** | Original and revised routes side by side | "Completed stops stay fixed, and the broken-down van gets no stops after 14:05." |
| Click **Go to Dispatcher** | | |

### 6. Dispatcher
| Do | Expect | Say |
|---|---|---|
| Say or tap **"The road between Kothrud and Mumbai is closed until 4 pm"** | Refused: "I do not know the place 'Mumbai'." Nothing changed. | "An unknown location is rejected, not guessed." |
| Say or tap **"The road between Kothrud and Aundh is slow until 4 pm, it adds 25 minutes"** | "Read by gpt-4o-mini, then checked by rules." A summary and a preview with counts. | "AI turns the sentence into a structured change. A strict rule reader checks it. Nothing applies yet." |
| Click **Confirm and apply** | "Applied by the dispatcher." Tiles update: D8 now 15:33. | "The dispatcher confirms before anything changes." |
| Click **Add urgent delivery D13**, then **Confirm and apply** | A **New 1** tile: D13 on V5 (Imran) at 14:22. | "An urgent parcel is fitted in where it disturbs the least." |

That covers every requirement in the problem statement: plan with arrival and waiting, capacity, three disruptions, text interpreted and confirmed, unknown place rejected, replan from the current state, and kept, moved or broken with reasons.

## Pass or fail checklist

- [ ] Health and voice status are OK
- [ ] Plan shows arrival times and a wait
- [ ] Read-back is spoken and correct
- [ ] Shortlist shows three drivers and Arjun ruled out
- [ ] Offer countdown runs
- [ ] The agent call connects and you can hear it
- [ ] The agent answers a timing question correctly and declines the pay question
- [ ] "Confirm" commits the rescue, and only one button is shown after
- [ ] Tiles show 9 kept, 2 moved, 1 broken
- [ ] Mumbai is refused
- [ ] The Kothrud to Aundh closure is read by AI and applies only after confirm
- [ ] D13 is added
- [ ] About and Contact pages open; the contact form shows "Message received"

## If something goes wrong

| You see | Do |
|---|---|
| "no incident INC-…" or the story looks wrong | Press **Restart**. Someone else reset the shared demo, or the server restarted. |
| "Waking the server" | Wait up to a minute. Open the health link beforehand next time. |
| The call card has no **Answer the call** button | Voice is off on the server. Check the voice status link. Use **Answers: confirm**. |
| The agent hears things you did not say | Keep **Open mic** unticked and only hold the button while speaking. Use headphones. |
| A place is misheard | Click **Did you mean …?**, or tap the suggested line. |
| No sound | Check **Voice on** in the top bar, and the laptop volume. |

## Rules for the judging slot

- Do not push code or change Render settings: either restarts the server and wipes the story.
- Open the health link a few minutes before.
- One presenter clicks; everyone else watches.
- Press **Restart** before each new audience.
