# DeTour

Fleet planning and replanning with a voice-driven breakdown rescue flow. VORTEXA 3.0, problem S-01 (ReRoute).
Spec: [docs/PRD.md](docs/PRD.md). Problem booklet: [docs/](docs/). How the engine models the day: [docs/ENGINE.md](docs/ENGINE.md). API: [docs/API.md](docs/API.md). The rescue flow and demo script: [docs/RESCUE.md](docs/RESCUE.md). Typed reports: [docs/INTERPRETING.md](docs/INTERPRETING.md). Voice: [docs/VOICE.md](docs/VOICE.md). The phone call: [docs/CALLS.md](docs/CALLS.md).

## Layout
- `backend/`: FastAPI. Engine, independent validator, incident state machine, audit log.
- `frontend/`: Vite + React (driver, head and dispatcher views).

## Run
```
cp .env.example .env                                   # then fill in keys (not needed for the demo)
cd backend && uv sync && uv run uvicorn detour.main:app --reload     # API on :8000
cd frontend && npm install && npm run dev                            # dispatcher UI on :5173/dispatch
cd backend && uv run pytest        cd frontend && npm test
```
Add `?theme=light` to the URL to force the light theme.
Phone demo: `cloudflared tunnel --url http://localhost:5173`, then set `PUBLIC_BASE_URL` in `.env`.

## Submission report
`docs/DeTour_Report.pdf` is the Problem Understanding, Solution Proposal & System Architecture report. Its source is `docs/report/report.html`; rebuild it with `python3 docs/report/build.py --team-id ... --team-name "..."` (needs Google Chrome).

## Phases
0 scaffold, 1 engine, 2 validator, 3 disruptions and diff, 4 audit and API, 5 dispatcher UI,
6 rescue flow, 7 text parsing, 8 voice, 9 escalation call, 10 hardening.
