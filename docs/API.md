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
| `POST /disruptions/{id}/confirm` `{"confirmed_by": "..."}` | Commit exactly the previewed plan. Refused if the plan changed since |
| `POST /disruptions` `{"disruption": {...}, "confirmed_by": "..."}` | Preview and commit in one call. A disruption with `source` `text` or `voice` needs `confirmed_by` |
| `POST /validate` `{"plan": {...}}` (optional body) | Run the independent validator on the current plan, or on a supplied one |
| `GET /audit?limit=&after=`, `GET /audit/verify` | The audit log and a hash-chain check |
| `GET /events` | Server-sent events: `hello`, `state` (refetch `/state`), `audit` |

Disruption bodies (`type` selects the shape; times are minutes since midnight):

```json
{"type": "road_closure", "a": "kothrud", "b": "aundh", "start": 840, "end": 960, "added_minutes": 25, "reported_at": 840}
{"type": "vehicle_failure", "vehicle_id": "V2", "time": 845, "location": "hadapsar"}
{"type": "urgent_delivery", "id": "D13", "location": "wanowrie", "size": 8, "window_start": 850, "window_end": 900, "time": 845}
```

Errors are `{"code": ..., "message": ...}`: `invalid_disruption` (422), `confirmation_required` (422),
`plan_invalid` (409, with violations), `stale_preview` (409), `no_plan` (409), `unknown_preview` (404).
Every refusal is written to the audit log.
