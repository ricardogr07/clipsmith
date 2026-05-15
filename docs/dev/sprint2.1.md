# Sprint 2.1 — Frontend Testing with Cypress

## Goal

Add a component-level and E2E test suite to the Next.js dashboard.
Every interactive component gets at least one happy-path and one error-path
test. E2E tests cover the two main user flows without requiring a live FastAPI
server (all network calls are intercepted).

---

## Tooling Decision

| Tool | Role |
|------|------|
| Cypress Component Testing | Unit-level: mount a single component, stub `api.*` calls, assert DOM output |
| Cypress E2E | Flow-level: load a real Next.js page in a browser, intercept `fetch`, assert the full user journey |
| `cy.intercept()` | Replaces `msw` / `jest-fetch-mock` — stubs the network at the browser level |

No Jest, no React Testing Library — Cypress handles both layers cleanly with
one tool and one config.

---

## Step 1 — Cypress Install & Config

```bash
cd web
pnpm add -D cypress
```

### `web/cypress.config.ts`

```ts
import { defineConfig } from "cypress";

export default defineConfig({
  component: {
    devServer: {
      framework: "next",
      bundler: "webpack",
    },
    specPattern: "cypress/component/**/*.cy.tsx",
  },
  e2e: {
    baseUrl: "http://localhost:3000",
    specPattern: "cypress/e2e/**/*.cy.ts",
    supportFile: "cypress/support/e2e.ts",
  },
});
```

### `web/package.json` — add scripts

```json
"cy:open":  "cypress open",
"cy:run":   "cypress run",
"cy:comp":  "cypress run --component",
"cy:e2e":   "cypress run --e2e"
```

### `web/cypress/support/component.ts` — global mount setup

```ts
import { mount } from "cypress/react18";
import "../../app/globals.css";

Cypress.Commands.add("mount", mount);
```

### `web/cypress/support/e2e.ts` — global E2E setup

```ts
// nothing required yet — extend as shared commands are added
```

### Acceptance

- [ ] `pnpm cy:open` opens the Cypress Launchpad with both "Component" and "E2E" options
- [ ] `pnpm cy:comp` exits 0 on an empty spec directory

---

## Step 2 — Component Tests

### `cypress/component/RunCard.cy.tsx`

**Fixtures:**

| Scenario | Input |
|----------|-------|
| Pending run | `{ status: "pending", clip_count: 0 }` |
| Running run | `{ status: "running", stage: "transcribe", clip_count: 0 }` |
| Done run | `{ status: "done", clip_count: 5 }` |
| Failed run | `{ status: "failed", error: "oom" }` |

**Assertions:**
- Correct badge text and colour for each status
- Clip count label ("5 clips", "1 clip", "0 clips")
- `stage` label visible when `status === "running"`
- Error text visible when `status === "failed"`
- `<a href="/runs/{id}">` rendered (link target)

---

### `cypress/component/NewRunDialog.cy.tsx`

**Stubs:** `cy.stub(api.runs, "create")`

**Scenarios:**

| Scenario | Setup | Assertion |
|----------|-------|-----------|
| Dialog closed by default | mount | trigger button visible, dialog not rendered |
| Opens on button click | click trigger | form fields visible |
| Submit disabled when VOD ID empty | open, leave blank | Submit button `disabled` |
| Happy path | fill vod_id, click Submit, stub resolves | `onCreated` spy called with returned run |
| API error | stub rejects with "401: ..." | Error message text rendered in dialog |
| Cancel closes without submit | open, click Cancel | dialog unmounts, stub not called |

---

### `cypress/component/ClipCard.cy.tsx`

**Stubs:** `cy.stub(api.clips, "patch")`

**Scenarios:**

| Scenario | Setup | Assertion |
|----------|-------|-----------|
| Renders title | clip with title | title text visible |
| Untitled clip | clip with `title: ""` | "untitled" italic placeholder shown |
| Approved badge | `approved: true` | "Approved" badge visible |
| Rejected badge | `approved: false` | "Rejected" badge visible |
| Approve button happy path | click Approve, stub resolves | `onUpdate` spy called; badge flips to "Approved" |
| Reject button happy path | click Reject, stub resolves | `onUpdate` spy called; badge flips to "Rejected" |
| "···" opens more options | click `···` | `ClipMoreOptions` panel visible |
| Play button opens modal | click play area | `ClipModal` overlay visible |

---

### `cypress/component/ClipMoreOptions.cy.tsx`

**Stubs:** `cy.stub(api.clips, "patch")`

**Scenarios:**

| Scenario | Setup | Assertion |
|----------|-------|-----------|
| Score bar width | `score: 0.75` | bar `width` style ≈ 75% |
| Zero score | `score: 0` | bar `width` style = 0% |
| Timestamps format | `start_s: 65, end_s: 125` | "1:05" and "2:05" visible |
| Duration | same as above | "60.0s" visible |
| Title click → input | click title text | `<input>` rendered with existing value |
| Blur saves title | type new value, blur | `api.clips.patch` called with `{ title: "..." }` |
| Enter saves title | type new value, press Enter | `api.clips.patch` called |
| Escape reverts | type new value, press Escape | original title restored, `patch` not called |
| Save error reverts | stub rejects | original title restored |

---

### `cypress/component/ClipModal.cy.tsx`

**Stubs:** `cy.stub(api.clips, "patch")`

**Scenarios:**

| Scenario | Setup | Assertion |
|----------|-------|-----------|
| Video src | `filename: "clip_01.mp4"` | `<video src>` contains `/clips/file/clip_01.mp4` |
| Title shown | clip with title | title text in modal |
| Duration label | `start_s: 10, end_s: 40` | "30.0s" visible |
| ESC closes | open modal, press Escape | `onClose` spy called |
| Backdrop click closes | click outside modal box | `onClose` spy called |
| ✕ button closes | click ✕ | `onClose` spy called |
| Approve button | click Approve | `patch` called with `{ approved: true }`; button variant flips |
| Reject button | click Reject | `patch` called with `{ approved: false }`; button variant flips |

---

### `cypress/component/ProgressStream.cy.tsx`

SSE can't be intercepted natively in Cypress Component Testing — use a
**custom hook wrapper** pattern: extract the SSE logic into `useProgressStream`
and test the hook via a thin wrapper component.

**Scenarios:**

| Scenario | SSE events | Assertion |
|----------|------------|-----------|
| Initial state | none | "starting" stage, 0% |
| Stage update | `{ stage: "transcribe", pct: 40 }` | label "transcribe", progress bar 40% |
| Multiple events | sequence of events | bar advances to last pct |
| Done event | `{ event: "end", status: "done" }` | "Pipeline complete" text shown, `onDone` spy called |
| Error event | `{ event: "end", status: "failed", error: "oom" }` | error text visible |
| Stream disconnect | `es.onerror` fires | "Stream disconnected" error text |

Implementation note: inject a `eventSourceFactory` prop (default: `EventSource`)
into the component for testing, replacing the global with a controllable fake.

---

## Step 3 — E2E Tests

All E2E tests use `cy.intercept()` to stub FastAPI — no live backend required.

### `cypress/e2e/dashboard.cy.ts`

```
GET /api/runs → []          (empty state)
GET /api/runs → [run1, run2]  (populated)
POST /api/runs → run3        (create)
```

**Scenarios:**

| Scenario | Setup | Steps | Assertion |
|----------|-------|-------|-----------|
| Empty state | intercept GET /runs → `[]` | load `/` | "No runs yet" message visible |
| Run list renders | intercept GET /runs → `[pendingRun, doneRun]` | load `/` | two RunCards visible |
| Status badges | same | — | "Pending" and "Done" badges visible |
| New Run dialog opens | load `/` | click "New Run" | dialog visible |
| Happy path create | intercept POST /runs → newRun | fill form + Submit | new card appears at top of list |
| Create error | intercept POST /runs → 401 | fill form + Submit | error message in dialog |
| Navigate to run | intercept GET /runs, load `/` | click card | URL → `/runs/{id}` |

---

### `cypress/e2e/run-detail.cy.ts`

```
GET /api/runs/{id}       → run
GET /api/runs/{id}/clips → clips
```

**Scenarios:**

| Scenario | Setup | Assertion |
|----------|-------|-----------|
| Run header | done run | VOD ID, "done" badge visible |
| Clip grid | run with 3 clips | 3 ClipCards rendered |
| Approve a clip | intercept PATCH /clips/1 → updated | click Approve; "Approved" badge |
| 404 run | intercept GET /runs/99 → 404 | error message + Back button |
| Active run shows progress bar | running run | `<progress>` element present |

---

## Step 4 — VS Code Integration

Add Cypress tasks to `.vscode/tasks.json`:

```json
{ "label": "Cypress: component tests", "command": "pnpm cy:comp", "cwd": "${workspaceFolder}/web" },
{ "label": "Cypress: e2e tests",       "command": "pnpm cy:e2e",  "cwd": "${workspaceFolder}/web" },
{ "label": "Cypress: open",            "command": "pnpm cy:open", "cwd": "${workspaceFolder}/web", "isBackground": true }
```

Add Cypress launch config to `.vscode/launch.json`:

```json
{
  "name": "Cypress: open (interactive)",
  "type": "node-terminal",
  "request": "launch",
  "command": "pnpm cy:open",
  "cwd": "${workspaceFolder}/web"
}
```

---

## Step 5 — Storybook Component Preview

> **Note on Figma MCP:** Figma API tooling is not currently wired into this
> environment. This step uses **Storybook** as the previsualization layer —
> it mounts every component in isolation with live prop controls, dark/light
> theme toggle, and a static-exportable site. When Figma MCP becomes available,
> Step 5b below adds the sync layer so Storybook stories can be linked to Figma
> frames and vice-versa.

### Why Storybook, not just Cypress

Cypress Component Testing is for *correctness* (assertions, pass/fail).
Storybook is for *visualization* — you interactively adjust props and see the
component render live, which is exactly the "previsualize what we built" goal.
The two tools share fixtures so there is no duplication.

### Install

```bash
cd web
pnpm dlx storybook@latest init --type nextjs --yes
pnpm add -D @storybook/addon-themes
```

`storybook init` auto-detects Next.js + Tailwind and wires the preview config.

### `web/.storybook/preview.ts`

```ts
import type { Preview } from "@storybook/react";
import "../app/globals.css";

const preview: Preview = {
  parameters: {
    backgrounds: { disable: true },   // use the themes addon instead
    nextjs: { appDirectory: true },
  },
};

export default preview;
```

### `web/package.json` — add scripts

```json
"storybook":       "storybook dev -p 6006",
"storybook:build": "storybook build"
```

### Stories to write

One story file per component, living alongside the component in
`components/*.stories.tsx`. Each file exports a `default` meta and one named
export per visual variant.

#### `RunCard.stories.tsx`

| Story | Props |
|-------|-------|
| `Pending` | `status: "pending"`, `clip_count: 0` |
| `Running` | `status: "running"`, `stage: "transcribe"` |
| `Done` | `status: "done"`, `clip_count: 5` |
| `Failed` | `status: "failed"`, `error: "OOM killed"` |
| `LongVodId` | 40-char vod_id — tests truncation |

#### `NewRunDialog.stories.tsx`

| Story | State |
|-------|-------|
| `Default` | dialog closed |
| `Open` | `play()` clicks the trigger to open |
| `Submitting` | stub `api.runs.create` to hang — shows loading state |
| `WithError` | stub rejects — shows error message in dialog |

#### `ClipCard.stories.tsx`

| Story | Props |
|-------|-------|
| `Untitled` | `title: ""`, `approved: null` |
| `Approved` | `approved: true` |
| `Rejected` | `approved: false` |
| `OptionsOpen` | `play()` clicks `···` — more-options panel visible |

#### `ClipMoreOptions.stories.tsx`

| Story | Props |
|-------|-------|
| `Default` | `score: 0.82`, `start_s: 65`, `end_s: 125` |
| `ZeroScore` | `score: 0` |
| `EditingTitle` | `play()` clicks title — shows input |

#### `ClipModal.stories.tsx`

| Story | Props |
|-------|-------|
| `Default` | standard clip, `open: true` |
| `Approved` | `approved: true` |
| `Rejected` | `approved: false` |

Because `ClipModal` is a full-viewport overlay, wrap it in a decorator that
constrains height so it renders inside the Storybook canvas without overflow.

#### `ProgressStream.stories.tsx`

Use the `eventSourceFactory` prop (from the Cypress testing refactor) to inject
a fake EventSource. Stories exercise each visual state directly:

| Story | EventSource events fired |
|-------|--------------------------|
| `Starting` | none |
| `Transcribing` | `{ stage: "transcribe", pct: 40 }` |
| `Complete` | `{ event: "end", status: "done" }` |
| `Failed` | `{ event: "end", status: "failed", error: "OOM" }` |

### Shared fixtures

Reuse the Cypress fixtures from Step 2 (`cypress/fixtures/*.json`) in stories
via a `web/lib/fixtures.ts` re-export. One source of truth for both tools.

```ts
// web/lib/fixtures.ts
export { default as sampleRun }  from "../cypress/fixtures/run.json";
export { default as sampleRuns } from "../cypress/fixtures/runs.json";
export { default as sampleClips } from "../cypress/fixtures/clips.json";
```

### VS Code integration

Add to `.vscode/tasks.json`:
```json
{ "label": "Storybook: dev",   "command": "pnpm storybook",       "cwd": "${workspaceFolder}/web", "isBackground": true },
{ "label": "Storybook: build", "command": "pnpm storybook:build",  "cwd": "${workspaceFolder}/web" }
```

Add to `.vscode/launch.json`:
```json
{
  "name": "Storybook: dev",
  "type": "node-terminal",
  "request": "launch",
  "command": "pnpm storybook",
  "cwd": "${workspaceFolder}/web",
  "serverReadyAction": {
    "action": "openExternally",
    "pattern": "Local:",
    "uriFormat": "http://localhost:6006"
  }
}
```

### Step 5b — Figma sync (when MCP is available)

Once a Figma MCP tool is connected, this step extends Step 5:

1. **Create a Figma file** `clipsmith-dashboard` with one page per component
   (RunCard, ClipCard, ClipModal, ProgressStream, NewRunDialog).
2. **Map Tailwind tokens → Figma variables**: background, foreground,
   primary, muted, destructive — matching `globals.css` CSS variables exactly.
3. **Use `@storybook/addon-design`** to link each story to its Figma frame URL,
   so the Storybook canvas shows the Figma design side-by-side with the live
   component.
4. **Verify visual parity**: compare rendered story with the Figma frame for
   each variant and document any intentional divergences.

This step is gated on Figma MCP availability and is not blocking for Sprint 2.1.

---

## File Layout (after Sprint 2.1)

```
web/
├── .storybook/
│   ├── main.ts
│   └── preview.ts
├── components/
│   ├── RunCard.tsx
│   ├── RunCard.stories.tsx          ← new
│   ├── ClipCard.tsx
│   ├── ClipCard.stories.tsx         ← new
│   ├── ClipMoreOptions.tsx
│   ├── ClipMoreOptions.stories.tsx  ← new
│   ├── ClipModal.tsx
│   ├── ClipModal.stories.tsx        ← new
│   ├── NewRunDialog.tsx
│   ├── NewRunDialog.stories.tsx     ← new
│   ├── ProgressStream.tsx
│   └── ProgressStream.stories.tsx  ← new
├── cypress/
│   ├── component/
│   │   ├── RunCard.cy.tsx
│   │   ├── NewRunDialog.cy.tsx
│   │   ├── ClipCard.cy.tsx
│   │   ├── ClipMoreOptions.cy.tsx
│   │   ├── ClipModal.cy.tsx
│   │   └── ProgressStream.cy.tsx
│   ├── e2e/
│   │   ├── dashboard.cy.ts
│   │   └── run-detail.cy.ts
│   ├── fixtures/
│   │   ├── run.json
│   │   ├── runs.json
│   │   └── clips.json
│   └── support/
│       ├── component.ts
│       └── e2e.ts
├── lib/
│   ├── api.ts
│   ├── fixtures.ts                  ← new (re-exports cypress fixtures)
│   └── types.ts
└── cypress.config.ts
```

---

## Verification Checklist

### Step 1 — Setup
- [ ] `pnpm cy:open` launches Cypress Launchpad
- [ ] Both "Component Testing" and "E2E Testing" modes available
- [ ] `pnpm cy:comp` exits 0 (no specs yet)

### Step 2 — Component tests
- [ ] `RunCard` — all 4 status variants pass
- [ ] `NewRunDialog` — 6 scenarios pass
- [ ] `ClipCard` — 8 scenarios pass
- [ ] `ClipMoreOptions` — 9 scenarios pass (including title editing with blur/Enter/Escape)
- [ ] `ClipModal` — 8 scenarios pass
- [ ] `ProgressStream` — 6 scenarios pass (uses `eventSourceFactory` prop injection)

### Step 3 — E2E tests
- [ ] `dashboard.cy.ts` — 7 scenarios pass without a live backend
- [ ] `run-detail.cy.ts` — 5 scenarios pass without a live backend

### Step 4 — VS Code
- [ ] "Cypress: component tests" task runs and reports pass/fail
- [ ] "Cypress: open" launch config opens the interactive runner

### Step 5 — Storybook
- [ ] `pnpm storybook` → opens at `http://localhost:6006`
- [ ] All 6 component story files present in the sidebar
- [ ] Each component shows all named variants selectable from the sidebar
- [ ] `ClipMoreOptions` — title edit interaction works in canvas
- [ ] `ProgressStream` — `Starting`, `Transcribing`, `Complete`, `Failed` variants all render
- [ ] `pnpm storybook:build` exits 0 (static export, no broken imports)
- [ ] "Storybook: dev" launch config opens browser automatically
