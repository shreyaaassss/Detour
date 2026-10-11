# API

Run: `cd backend && uv run uvicorn detour.main:app --reload` (port 8000). Interactive docs at `/docs`.
Send `X-Actor: <name>` to record who acted (defaults to `dispatcher`). The audit log is written to
`backend/data/audit.jsonl` (override with `DETOUR_DATA_DIR`).

| Endpoint | Purpose |
|---|---|
| `GET /state` | Everything a screen needs: scenario, original and current plan, validator report, diff, applied changes, version |
| `GET /plan`, `GET /plan/diff` | Plans and the kept / moved / broken diff |
| `POST /plan` `{"mode": "auto\|demo\|solve"}` | Build the initial plan. `demo` is the hand-assigned baseline, `solve` runs the solver |
| `POST /scenario` | Load a custom scenario (JSON). Unknown locations are rejected |
| `POST /reset` | Back to the demo scenario and baseline (the audit log keeps its history) |
| `GET /presets` | The three demo disruptions |
| `POST /disruptions/preview` `{"disruption": {...}}` | Dry run: revised plan, diff and validator result. Changes nothing |
| `POST /disruptions/parse` `{text, source}` | Read a report in the dispatcher's own words into a preview, or refuse it with reasons ([how](INTERPRETING.md)). `GET /interpreter` says whether the model is on |
| `POST /disruptions/{id}/confirm` `{"confirmed_by": "..."}` | Commit exactly the previewed plan. Refused if the plan changed since |
| `POST /disruptions` `{"disruption": {...}, "confirmed_by": "..."}` | Preview and commit in one call. A disruption with `source` `text` or `voice` needs `confirmed_by` |
| `POST /validate` `{"plan": {...}}` (optional body) | Run the independent validator on the current plan, or on a supplied one |
| `GET /audit?limit=&after=`, `GET /audit/verify` | The audit log and a hash-chain check |
| `GET /events` | Server-sent events: `hello`, `state` (refetch `/state`), `audit` |

### Voice

| Endpoint | Purpose |
|---|---|
| `GET /voice/status` | Whether ElevenLabs is on, models, this run's spend, saved lines, account credits |
| `GET /voice/audio?what=readback\|offer\|note&ref=&lang=` | Speak something the system produced, by id. Never free text. Supports byte ranges |
| `POST /incidents/voice?driver=Ravi` (raw audio body) | A spoken report: transcript and the new incident. 503 if transcription is unavailable, so the phone falls back |
| `POST /voice/warm` | Prepare the demo story's voice lines ahead of time |

See [VOICE.md](VOICE.md).

### Rescue flow

| Endpoint | Purpose |
|---|---|
| `POST /incidents/report` `{driver, transcript, language?, location_id?, breakdown?}` | A driver reports a breakdown. Returns the incident with a read-back in three languages, or `REJECTED` with the known places |
| `POST /incidents/{id}/confirm` `{confirmed, location_id?}` | The driver confirms the read-back, corrects the place, or cancels |
| `GET /incidents`, `GET /incidents/{id}`, `GET /incidents/{id}/proposal` | Incidents (with offers and history), and the ranked proposal |
| `POST /incidents/{id}/approve` `{approved_by, shortlist, proposal_version, role}` | The head approves up to three feasible drivers. Refused if the plan changed since the proposal |
| `POST /incidents/{id}/reject` `{by}` | The head rejects the rescue |
| `GET /offers?driver=Meera`, `POST /offers/{id}/respond` `{response: accept\|decline}` | A driver's open offer, and their tap |
| `POST /telephony/webhook` `{offer_id, outcome}` | A call result: `answered`, `confirmed`, `declined`, `no_answer`, `voicemail`, `busy`, `ambiguous` |
| `GET/POST /clock` `{sim_time?: "HH:MM", speed?}` | The simulated time of day; speed 0 holds it |
| `GET /notifications?to=driver:Ravi\|role:head\|role:backup\|role:dispatcher&after=` | Messages for a person, each in en, hi and mr |
| `GET /messages`, `POST /messages/{delivery_id}/approve` | Customer message drafts and the dispatcher's sign-off |

Server-sent events add `incident` and `notify`. Responses carry `server_time` so a screen's countdown matches the
server's timers. Disruption bodies (`type` selects the shape; times are minutes since midnight):

```json
{"type": "road_closure", "a": "kothrud", "b": "aundh", "start": 840, "end": 960, "added_minutes": 25, "reported_at": 840}
{"type": "vehicle_failure", "vehicle_id": "V2", "time": 845, "location": "hadapsar"}
{"type": "urgent_delivery", "id": "D13", "location": "wanowrie", "size": 8, "window_start": 850, "window_end": 900, "time": 845}
```

Errors are `{"code": ..., "message": ...}`: `invalid_disruption` (422), `confirmation_required` (422),
`plan_invalid` (409, with violations), `stale_preview` (409), `no_plan` (409), `unknown_preview` (404).
Every refusal is written to the audit log.
