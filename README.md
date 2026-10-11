# DeTour

Fleet planning and replanning with a voice-driven breakdown rescue flow. VORTEXA 3.0, problem S-01 (ReRoute).
Spec: [docs/PRD.md](docs/PRD.md). Problem booklet: [docs/](docs/). How the engine models the day: [docs/ENGINE.md](docs/ENGINE.md).

## Layout
- `backend/`: FastAPI. Engine, independent validator, incident state machine, audit log.
- `frontend/`: Vite + React (driver, head and dispatcher views).

## Run
```
cp .env.example .env        # then fill in keys
cd backend && uv sync && uv run uvicorn detour.main:app --reload
cd frontend && npm install && npm run dev
cd backend && uv run pytest
```
Phone demo: `cloudflared tunnel --url http://localhost:5173`, then set `PUBLIC_BASE_URL` in `.env`.

## Phases
0 scaffold, 1 engine, 2 validator, 3 disruptions and diff, 4 audit and API, 5 dispatcher UI,
6 rescue flow, 7 text parsing, 8 voice, 9 escalation call, 10 hardening.
