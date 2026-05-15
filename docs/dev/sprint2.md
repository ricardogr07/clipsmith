# Sprint 2 — Next.js Dashboard + API Auth

## Goal

Ship the web dashboard that was always the target for Sprint 1's REST layer.
Three features land together because they are architecturally coupled:
**API key gate** (the backend must be secured before the frontend hits it in any
shared environment), **modal player** (how clips are previewed), and **more
options** panel (the richer clip metadata already in the DB just needs exposing).

---

## Step 0 — Doc Update (Pre-flight)

Sprint 1 is done. The docs written before it shipped are now stale.
Fix them before starting implementation so the plan docs stay honest.

### `docs/dev/contributing.md`

| Section | What to update |
|---------|----------------|
| Install | Add `pip install -e ".[server]"` (new optional extra) |
| Run commands | Add `clipsmith serve` → `http://localhost:8000/docs` |
| Module layout | Add `api/` and `db/` subtrees (they do not appear today) |
| CI table | Note that `ci.yml` now also checks the `[server]` import paths |

### `docs/dev/PLAN.md`

| Item | Change |
|------|--------|
| Sprint 1 status | Already `✅ Done` — confirm checklist items pass |
| Sprint 2 status | `🔜 Next` → `🚧 In Progress` |
| Sprint 2 detail block | Expand to match the final scope: auth gate, modal player, more-options panel |

### Acceptance

- Both files reviewed, no stale instructions remain
- `mkdocs build --strict` passes with zero warnings

---

## Step 1 — API Key Gate (Backend)

Protect mutating endpoints with a static API key before the frontend is wired
to any shared server. Read-only endpoints remain open so the dashboard can load
data without storing a second credential client-side.

### Config changes

`src/clipsmith/config/models.py` — add to `AppConfig`:

```python
api_key: str | None = None   # read from config.yaml or CLIPSMITH_API_KEY env var
```

`config.yaml` (project default / `.gitignore`d):

```yaml
api_key: "change-me"
```

### `src/clipsmith/api/deps.py` — new dependency

```python
from fastapi import Header, HTTPException, Security
from fastapi.security import APIKeyHeader

_api_key_header = APIKeyHeader(name="X-Api-Key", auto_error=False)

async def verify_api_key(
    x_api_key: str | None = Security(_api_key_header),
) -> None:
    cfg = _get_cfg()           # module-level cached config
    if cfg.api_key and x_api_key != cfg.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
```

### Routes that require auth

| Endpoint | Auth |
|----------|------|
| `POST /runs` | `verify_api_key` dependency |
| `PATCH /clips/{id}` | `verify_api_key` dependency |
| `GET /runs`, `GET /runs/{id}` | open |
| `GET /runs/{id}/clips` | open |
| `GET /runs/{id}/progress` | open |
| `GET /clips/file/{filename}` | open |
| `GET /health`, `GET /metrics` | open |

### CORS update

`app.py` — restrict `allow_origins` to `["http://localhost:3000"]` in dev;
add `"X-Api-Key"` to `allow_headers`.

### `PATCH /clips/{id}` — extend schema

`ClipPatch` currently only accepts `approved`. Extend to also accept `title`:

```python
class ClipPatch(BaseModel):
    approved: bool | None = None
    title: str | None = None
```

Apply whichever fields are non-`None`.

### API contract additions

```
POST   /runs            X-Api-Key required → 401 if wrong/missing
PATCH  /clips/{id}      X-Api-Key required; body now accepts title too
```

---

## Step 2 — Next.js Scaffold

### Directory layout

```
web/
├── app/
│   ├── layout.tsx          Root layout, Tailwind, font
│   ├── page.tsx            Dashboard: run list + "New Run" dialog
│   └── runs/
│       └── [id]/
│           └── page.tsx    Run detail: progress bar + clip grid
├── components/
│   ├── RunCard.tsx          Status chip, VOD ID, clip count, elapsed time
│   ├── ClipCard.tsx         Thumbnail row + approve/reject + "more" toggle
│   ├── ClipMoreOptions.tsx  Expanded panel: title edit, timestamps, score bar
│   ├── ClipModal.tsx        Fullscreen video modal with metadata
│   ├── NewRunDialog.tsx     Form: vod_id + channel + provider select
│   └── ProgressStream.tsx   SSE hook → live stage label + percentage bar
├── lib/
│   ├── api.ts               Typed fetch wrappers; injects X-Api-Key header
│   └── types.ts             Run, Clip, PipelineEvent TypeScript interfaces
└── package.json
```

### Dependencies

```bash
pnpm dlx create-next-app@latest web --typescript --tailwind --app --no-src-dir
cd web
pnpm dlx shadcn@latest init
pnpm dlx shadcn@latest add card badge button progress dialog
```

### Environment variables (`web/.env.local`)

```
NEXT_PUBLIC_API_BASE=http://localhost:8000
NEXT_PUBLIC_API_KEY=change-me
```

Both are `NEXT_PUBLIC_*` so the browser can read them.
`web/.env.local` is `.gitignore`d — add a `web/.env.example` with placeholder values.

### Dev proxy (`web/next.config.ts`)

```ts
rewrites: async () => [
  { source: "/api/:path*", destination: "http://localhost:8000/:path*" },
],
```

This lets `lib/api.ts` call `/api/runs` instead of `http://localhost:8000/runs`
and avoids browser CORS preflight for the SSE stream.

---

## Step 3 — Dashboard Page (`app/page.tsx`)

**Behaviour:**

1. On mount: `GET /runs` → render `<RunCard>` list, sorted newest-first.
2. Poll every 5 s while any run has `status: running | pending`.
3. "New Run" button → `<NewRunDialog>` modal.
4. `NewRunDialog` submits `POST /runs` (with `X-Api-Key`) → on 201 append the
   new run and navigate to `/runs/{id}`.

**`RunCard` fields:**

| Field | Source |
|-------|--------|
| VOD ID | `run.vod_id` |
| Channel | `run.channel` |
| Status badge | `run.status` (colour: pending=gray, running=blue, done=green, failed=red) |
| Clip count | `run.clip_count` |
| Created | `run.created_at` relative time |

---

## Step 4 — Run Detail Page + SSE Progress (`app/runs/[id]/page.tsx`)

**Behaviour:**

1. `GET /runs/{id}` → page title, status.
2. If status is `running | pending`: open SSE connection to
   `GET /runs/{id}/progress`, render `<ProgressStream>`.
3. `GET /runs/{id}/clips` → render `<ClipCard>` grid (2-col on desktop).
4. Auto-refresh clip list every 3 s while run is not done/failed.

**`ProgressStream` component:**

- Consumes SSE events `{ stage, pct, message }`.
- Renders a labelled `<Progress>` bar (shadcn/ui) and a stage caption.
- On `EventSource` close (run finished), show "Pipeline complete ✓" and stop polling.

---

## Step 5 — Modal Player (`ClipModal.tsx`)

Triggered when the user clicks the preview area of a `<ClipCard>`.

**Layout (full-viewport overlay):**

```
┌─────────────────────────────────────────────────────┐
│  [✕ close]                                          │
│                                                     │
│        ┌──────────────────────────────┐             │
│        │   <video controls autoplay>  │             │
│        │   src: /clips/file/{fname}   │             │
│        └──────────────────────────────┘             │
│                                                     │
│  Title: {title}                Score: {score:.2f}   │
│  {start_s}s → {end_s}s   ({duration}s)             │
│                                                     │
│          [Approve]   [Reject]                       │
└─────────────────────────────────────────────────────┘
```

**Behaviour:**

- ESC or backdrop click → close without side effects.
- Approve / Reject → `PATCH /clips/{id}` → optimistic UI update on the parent
  `ClipCard` (no full page reload).
- Video `src` points to the FastAPI `GET /clips/file/{filename}` endpoint via
  the dev proxy.

---

## Step 6 — Clip More Options (`ClipMoreOptions.tsx`)

Toggled by a "···" / "Details" button on each `ClipCard`.

**Panel contents:**

| Field | Editable? | Source |
|-------|-----------|--------|
| Title | Yes — inline input, blur → `PATCH /clips/{id}` with `{ title }` | `clip.title` |
| Score | No — read-only, rendered as a filled bar (0–1 range) | `clip.score` |
| Start time | No | `clip.start_s` formatted as `mm:ss` |
| End time | No | `clip.end_s` formatted as `mm:ss` |
| Duration | No — computed | `(clip.end_s - clip.start_s).toFixed(1)s` |
| Approved | No — mirrored from approve/reject buttons | `clip.approved` |

**Title edit flow:**

1. Click title text → becomes `<input>` with current value.
2. `onBlur` or `Enter` → `PATCH /clips/{id} { title: newValue }` (with `X-Api-Key`).
3. On 200 → update local state; on error → revert and show toast.

---

## Step 7 — Auth Wire-up (Frontend)

`lib/api.ts` — central fetch wrapper:

```ts
const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";
const KEY  = process.env.NEXT_PUBLIC_API_KEY  ?? "";

async function apiFetch(path: string, init: RequestInit = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Api-Key": KEY,
      ...init.headers,
    },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}
```

All `POST` and `PATCH` calls go through `apiFetch`.
`GET` calls for public read endpoints also go through it (harmless, and keeps
the interface uniform).

---

## File Layout (final state after Sprint 2)

```
clipsmith/
├── src/clipsmith/
│   ├── api/
│   │   ├── app.py              CORS locked to localhost:3000 in dev
│   │   ├── deps.py             get_db() + verify_api_key()
│   │   └── routes/
│   │       ├── runs.py         POST /runs now requires verify_api_key
│   │       └── clips.py        PATCH /clips/{id} extended + requires auth
│   └── config/
│       └── models.py           AppConfig gains api_key field
├── web/                        Next.js 14 App Router
│   ├── app/
│   │   ├── page.tsx
│   │   └── runs/[id]/page.tsx
│   ├── components/
│   │   ├── RunCard.tsx
│   │   ├── ClipCard.tsx
│   │   ├── ClipMoreOptions.tsx
│   │   ├── ClipModal.tsx
│   │   ├── NewRunDialog.tsx
│   │   └── ProgressStream.tsx
│   ├── lib/
│   │   ├── api.ts
│   │   └── types.ts
│   ├── .env.example
│   └── next.config.ts
└── docs/dev/
    ├── contributing.md         Updated (Step 0)
    ├── PLAN.md                 Sprint 2 marked active (Step 0)
    ├── sprint1.md              Unchanged
    └── sprint2.md              This file
```

---

## API Contract (full — Sprint 2 state)

```
POST   /runs                X-Api-Key required   201 Run
GET    /runs                open                 200 Run[]
GET    /runs/{id}           open                 200 Run
GET    /runs/{id}/progress  open                 200 text/event-stream
GET    /runs/{id}/clips     open                 200 Clip[]
PATCH  /clips/{id}          X-Api-Key required   200 Clip  (approved?, title?)
GET    /clips/file/{fname}  open                 200 video/mp4
GET    /health              open                 200 { status, db, version }
GET    /metrics             open                 200 { runs_by_status }
GET    /docs                open                 OpenAPI UI
GET    /                    open                 302 → /docs
```

---

## Verification Checklist

### Step 0 — Docs
- [ ] `contributing.md` lists `api/` and `db/` in the module layout
- [ ] `contributing.md` documents `clipsmith serve` and `pip install -e ".[server]"`
- [ ] `PLAN.md` Sprint 2 shows `🚧 In Progress`
- [ ] `mkdocs build --strict` exits 0

### Step 1 — Auth
- [ ] `POST /runs` without `X-Api-Key` → 401
- [ ] `POST /runs` with correct key → 201
- [ ] `PATCH /clips/{id}` without key → 401
- [ ] `GET /runs` without key → 200 (open read)
- [ ] `PATCH /clips/{id}` `{ "title": "New Title" }` → 200, title persisted
- [ ] `PATCH /clips/{id}` `{ "approved": true }` → 200, approved persisted
- [ ] If `api_key` is null in config → all requests pass (auth disabled)

### Step 2 — Scaffold
- [ ] `cd web && pnpm dev` → Next.js on `:3000` with no TypeScript errors
- [ ] `pnpm build` exits 0

### Step 3 — Dashboard
- [ ] `http://localhost:3000` shows run list
- [ ] "New Run" dialog opens, submits, new run card appears
- [ ] Running run card shows blue badge; done shows green

### Step 4 — Run Detail + SSE
- [ ] `/runs/{id}` page loads with correct title and status
- [ ] While running: progress bar advances via SSE events
- [ ] After run done: clip grid appears with all clips

### Step 5 — Modal Player
- [ ] Click clip thumbnail → modal opens with `<video>` playing
- [ ] ESC closes modal
- [ ] Backdrop click closes modal
- [ ] Approve / Reject inside modal updates card without page reload

### Step 6 — More Options
- [ ] "Details" button expands more-options panel
- [ ] Title field is editable; blur saves via PATCH
- [ ] Score bar renders proportionally
- [ ] Start/end/duration display correctly in `mm:ss` format

### Step 7 — Auth (Frontend)
- [ ] All POST/PATCH calls include `X-Api-Key` header
- [ ] Wrong key in `.env.local` → UI shows error toast, no 5xx unhandled crash
