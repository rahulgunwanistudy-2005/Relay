# Relay Frontend Execution Ledger

Running record of the frontend build. The backend is the source of truth; this
frontend makes the real backend legible. No functionality is claimed that was
not run against the live API.

## Environment (verified Phase 0)

- Postgres 16 running locally; `relay_dev` migrated to head `42b62f189167`.
- Python venv works; API boots (`uvicorn relay.api.main:app`) → `/health/ready` `{database: ok}`.
- Node v24.19.0, npm 11.17.0 available for the Vite client.
- No `RELAY_GROQ_API_KEY` set → AI extraction uses the **deterministic fallback**
  (honest, one EXECUTE step + clarifications). Multi-stage lifecycle is authored
  by the user during capture/X-Ray and persisted as `user_explicit` steps — real,
  not faked AI.

## Backend truth map (verified live via curl, Phase 0/1)

| Capability | Route | Status |
| --- | --- | --- |
| Auth | `POST /v1/auth/register\|login\|logout`, `GET /v1/me` | REAL_AND_WORKING |
| Households | `POST /v1/households`, `GET /v1/households/{id}`, members, invites, accept | REAL_AND_WORKING |
| Draft (X-Ray suggest) | `POST /v1/responsibilities/drafts?household_id=` | REAL_AND_WORKING (deterministic w/o key) |
| Create responsibility | `POST /v1/responsibilities?household_id=` (multi-step) | REAL_AND_WORKING |
| List / get / patch | `GET/PATCH /v1/responsibilities...` | REAL_AND_WORKING |
| Step complete/reopen | `POST .../steps/{id}/complete\|reopen` | REAL_AND_WORKING |
| Propose handoff | `POST /v1/responsibilities/{id}/handoffs` | REAL_AND_WORKING |
| Contract get/accept/decline | `GET/POST /v1/handoffs/{id}...` | REAL_AND_WORKING |
| Ghost queue | `GET /v1/me/ghost-queue` | REAL_AND_WORKING |
| Proof of relief | `GET /v1/responsibilities/{id}/proof-of-relief` | REAL_AND_WORKING |
| Ownership history | `GET /v1/responsibilities/{id}/ownership-history` | REAL_AND_WORKING |
| Notifications | `GET /v1/me/notifications`, mark read | REAL_AND_WORKING (empty on handoff propose) |

### Verified No Boomerang (real data)

Alice creates a 7-step "Maya's dental checkup" → Alice ghost-queue has 2 reminders
(cycle_due, step_due). Alice proposes → Bob accepts (`reminders_rerouted: 2`,
`ownership_version 1→2`). After: **Alice ghost-queue = [] , Bob ghost-queue = 2 items.**
Proof: `lifecycle_obligations_transferred: 7`, `decision_points_transferred: 2`.
History: created → proposed → transferred.

## Backend additions made (small, read-only, tested — no ownership semantics touched)

1. `GET /v1/households/{id}/members` now includes `display_name` + `email`
   (join `User`). Needed so the UI shows people, never UUIDs.
2. `GET /v1/households` — lists households the caller is an active member of.
   Replaces the legacy client's localStorage-only household discovery.
3. `GET /v1/me/handoffs` — the recipient's pending-contract inbox, so a handoff
   is discoverable without an out-of-band link. Ownership unchanged until accept.

Tests: `tests/integration/test_frontend_support.py` (4 tests, green).
Full integration suite: green. ruff + mypy: clean.

## Frontend architecture

- Replaced buildless `web/index.html` (backed up to `web/legacy-verification.html.bak`).
- Stack: React + TypeScript + Vite + React Router + TanStack Query + Motion (framer-motion).
- Design system: **Thread & Paper** — warm paper, ink typography, single thread accent,
  editorial spacing, minimal containers. Fonts bundled offline via @fontsource
  (Fraunces display serif, Inter UI, mono via system stack).
- Server state is authoritative: no optimistic ownership transfer; transfer motion
  only fires after the accept call returns real `ownership_version`.

## Reference matrix (principles used, not cloned)

- Granola — calm at rest, energy only during state change; typographic identity.
- Daylight — warm low-stimulation paper; post-transfer emptiness as a positive state.
- Family — human-readable audit ("Bob accepted", "Ownership v1 → v2"), not JSON.
- Tana — one canonical responsibility across views (sentence → X-Ray → contract → proof).
- mymind — progressive disclosure; show only the next meaningful obligation.
- Snow Fall / Active Theory / Apple — Judge Mode as chaptered causal narrative, deterministic director.

## Progress

- [x] Phase 0 reconnaissance + live E2E
- [x] Phase 1 backend truth map
- [x] Backend honest additions + tests
- [x] Frontend foundation (Vite/React/TS/Router/Query/Motion, Thread & Paper tokens, offline fonts)
- [x] Core screens (Ghost Queue, Capture→X-Ray composer, Detail, Inbox, Household)
- [x] Handoff (Ownership Contract, two-user acceptance, server-confirmed transfer motion, No Boomerang proof receipt + audit)
- [x] Judge Mode (deterministic 8-scene director, ~41s, real transfer trace, transport + reduced-motion + honest failure states)
- [x] Browser QA / responsive / build

## Verified in a live browser (real backend, two real users)

Signed in as Alice → captured a fresh "car registration" responsibility (deterministic
draft + user-authored lifecycle) → proposed to Bob → **signed out, signed in as Bob** →
Incoming inbox (`/v1/me/handoffs`) → opened the Ownership Contract → **Accepted** →
transfer motion played only after the accept call returned → status "Ownership moved to
Bob. 2 future reminders rerouted." → Alice's column went quiet ("Nothing scheduled here")
→ settled receipt from real proof (ownership v1→v2). Bob's My Load then showed both
responsibilities he now owns plus their rerouted reminders; Alice's queue was empty.

Judge Mode replayed that real transfer across 8 scenes (burden → sentence → X-Ray →
scope/consent → transfer → No Boomerang → proof → relief). Proof scene showed real
values: 4 lifecycle obligations, 2 reminders rerouted, 1 decision point, ownership v1→v2.

## Validation results

- Backend: `python -m pytest` → **121 passed** (117 prior + 4 new frontend-support tests). No regression.
- Backend quality: `ruff check src/relay` clean; `mypy` clean.
- Frontend: `tsc --noEmit` clean; `eslint . --ext ts,tsx` clean; `vite build` succeeds (~376 KB JS / 119 KB gzip).
- Browser: no console-breaking errors (one benign 401 from a pre-auth probe the client handles).
- Responsive: verified 1280×800 desktop and 375×812 mobile (My Load + X-Ray recompose vertically).
- Accessibility: semantic ordered-list thread (valid `<ol>`→`<li>`), visible focus, provenance in text not color, `aria-live` ownership-change announcement, `prefers-reduced-motion` gates Judge Mode + global transitions.

## Docker

`docker-compose.yml` web service now runs the real Vite client (node:20-slim, `RELAY_API_TARGET=http://api:8000`) instead of the buildless placeholder. API/worker/db architecture unchanged.

## Honest limitations (real, unresolved)

- No `RELAY_GROQ_API_KEY` in this environment → drafts use the deterministic fallback (one EXECUTE step). Lifecycle richness is user-authored during capture and persisted as `user_explicit` — truthful, not simulated AI. With a Groq key the same UI would render a richer AI draft.
- The owner's pending-contract deep link is remembered as a client-side hint (`localStorage`); the recipient's inbox (`/v1/me/handoffs`) is the authoritative discovery path.
- In-app notifications are empty on propose (worker generates delivery evidence on reminder firing); the Ghost Queue reroute is the authoritative No-Boomerang signal and is what the UI shows.
