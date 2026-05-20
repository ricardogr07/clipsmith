# Sprint 8 — Run Detail UI + Video Player

## Goal

Complete the pending run-detail page. The page shell and polling logic already exist in
`web/app/runs/[id]/page.tsx` but the key components are missing: a real-time SSE progress
bar, an in-browser video player inside each clip card, approve/reject keyboard shortcuts,
and a signal breakdown mini-chart that uses the `signal_breakdown` data from Sprint 5.

This sprint is the full-stack showcase moment — it touches SSE streaming, React state
management, video APIs, keyboard event handling, and data visualization, all wired together
through the existing FastAPI backend.

---

## Step 0 — Doc Pre-flight

### `docs/dev/PLAN.md`

| Item | Change |
|------|--------|
| Sprint 8 status | `🔜 Planned` → `🚧 In Progress` |

---

## Step 1 — SSE Progress Bar Component

The FastAPI SSE endpoint (`GET /runs/{id}/progress`) already streams `PipelineEvent` rows.
The dashboard's `web/app/runs/[id]/page.tsx` already imports `ProgressStream` but the
component is not implemented. Build it now.

### New file: `web/components/ProgressStream.tsx`

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";

interface ProgressEvent {
  stage: string;
  pct: number;
  message: string;
}

const STAGE_LABELS: Record<string, string> = {
  starting:    "Starting",
  download:    "Downloading VOD",
  webcam:      "Detecting webcam",
  transcribe:  "Transcribing audio",
  chat:        "Downloading chat",
  candidates:  "Scoring candidates",
  select:      "LLM clip selection",
  clip:        "Rendering clips",
  done:        "Complete",
};

interface Props {
  runId: number;
  onDone?: () => void;
}

export function ProgressStream({ runId, onDone }: Props) {
  const [event, setEvent] = useState<ProgressEvent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const url = api.sseUrl(runId);
    const es = new EventSource(url);
    esRef.current = es;

    es.onmessage = (e) => {
      try {
        const data: ProgressEvent = JSON.parse(e.data);
        setEvent(data);
        if (data.stage === "done" || data.pct >= 100) {
          es.close();
          onDone?.();
        }
      } catch {
        // malformed event — ignore
      }
    };

    es.onerror = () => {
      setError("Lost connection to progress stream");
      es.close();
    };

    return () => es.close();
  }, [runId, onDone]);

  if (error) {
    return <p className="text-xs text-muted-foreground">{error}</p>;
  }

  if (!event) {
    return (
      <div className="space-y-1">
        <Progress value={0} className="h-2" />
        <p className="text-xs text-muted-foreground">Waiting for pipeline…</p>
      </div>
    );
  }

  const label = STAGE_LABELS[event.stage] ?? event.stage;

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between items-center">
        <span className="text-sm font-medium">{label}</span>
        <span className="text-xs text-muted-foreground">{Math.round(event.pct)}%</span>
      </div>
      <Progress value={event.pct} className="h-2" />
      {event.message && (
        <p className="text-xs text-muted-foreground truncate">{event.message}</p>
      )}
    </div>
  );
}
```

---

## Step 2 — Clip Card with Video Player

### New file: `web/components/ClipCard.tsx`

The card shows the clip metadata, a lazy-loaded `<video>` element that only loads when
the card scrolls into the viewport (via `IntersectionObserver`), approve/reject buttons,
and a signal breakdown bar.

```tsx
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Check, X, Play } from "lucide-react";
import { SignalBreakdownBar } from "@/components/SignalBreakdownBar";
import { api } from "@/lib/api";
import type { Clip } from "@/lib/types";

interface Props {
  clip: Clip;
  focused: boolean;          // true when this card is keyboard-selected
  onUpdate: (clip: Clip) => void;
  onFocus: () => void;
}

export function ClipCard({ clip, focused, onUpdate, onFocus }: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const cardRef = useRef<HTMLDivElement | null>(null);
  const [videoVisible, setVideoVisible] = useState(false);
  const [patching, setPatching] = useState(false);

  // Lazy-load video when card enters viewport
  useEffect(() => {
    const el = cardRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setVideoVisible(true); },
      { threshold: 0.1 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // Auto-play when keyboard-focused
  useEffect(() => {
    if (focused && videoRef.current) {
      videoRef.current.play().catch(() => {});
    } else if (!focused && videoRef.current) {
      videoRef.current.pause();
    }
  }, [focused]);

  const patch = useCallback(
    async (approved: boolean) => {
      if (patching) return;
      setPatching(true);
      try {
        const updated = await api.clips.patch(clip.id, { approved });
        onUpdate(updated);
      } finally {
        setPatching(false);
      }
    },
    [clip.id, patching, onUpdate]
  );

  const approvedClass =
    clip.approved === true
      ? "ring-2 ring-green-500"
      : clip.approved === false
        ? "ring-2 ring-red-500"
        : "";

  const focusClass = focused ? "ring-2 ring-blue-500" : "";

  return (
    <Card
      ref={cardRef}
      className={`cursor-pointer transition-all ${approvedClass} ${focusClass}`}
      onClick={onFocus}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-medium leading-tight line-clamp-2 flex-1">
            {clip.title || clip.filename}
          </p>
          <Badge variant="outline" className="shrink-0 text-xs">
            {clip.score.toFixed(0)}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          {clip.start_s.toFixed(1)}s – {clip.end_s.toFixed(1)}s
          ({(clip.end_s - clip.start_s).toFixed(1)}s)
        </p>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* Video player — lazy loaded */}
        <div className="rounded-md overflow-hidden bg-black aspect-[9/16] max-h-64 flex items-center justify-center">
          {videoVisible ? (
            <video
              ref={videoRef}
              src={api.fileUrl(clip.run_id, clip.filename)}
              className="w-full h-full object-contain"
              controls
              preload="metadata"
              playsInline
              muted
            />
          ) : (
            <div className="flex flex-col items-center gap-1 text-white/40">
              <Play className="h-6 w-6" />
              <span className="text-xs">Scroll to load</span>
            </div>
          )}
        </div>

        {/* Signal breakdown */}
        {clip.signal_breakdown && (
          <SignalBreakdownBar breakdown={clip.signal_breakdown} />
        )}

        {/* Approve / reject */}
        <div className="flex gap-2">
          <Button
            size="sm"
            variant={clip.approved === true ? "default" : "outline"}
            className="flex-1"
            disabled={patching}
            onClick={(e) => { e.stopPropagation(); patch(true); }}
          >
            <Check className="h-3.5 w-3.5 mr-1" />
            Approve
          </Button>
          <Button
            size="sm"
            variant={clip.approved === false ? "destructive" : "outline"}
            className="flex-1"
            disabled={patching}
            onClick={(e) => { e.stopPropagation(); patch(false); }}
          >
            <X className="h-3.5 w-3.5 mr-1" />
            Reject
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
```

---

## Step 3 — Signal Breakdown Bar

### New file: `web/components/SignalBreakdownBar.tsx`

```tsx
"use client";

const SIGNAL_COLORS: Record<string, string> = {
  existing_clip:   "bg-purple-500",
  clip_command:    "bg-blue-500",
  chat_density:    "bg-cyan-500",
  transcript_hype: "bg-green-500",
  audio_energy:    "bg-orange-500",
};

const SIGNAL_LABELS: Record<string, string> = {
  existing_clip:   "Clip",
  clip_command:    "!clip",
  chat_density:    "Chat",
  transcript_hype: "Hype",
  audio_energy:    "Audio",
};

interface Props {
  breakdown: Record<string, number>;
}

export function SignalBreakdownBar({ breakdown }: Props) {
  const signals = Object.entries(SIGNAL_COLORS)
    .map(([key]) => ({ key, value: breakdown[key] ?? 0 }))
    .filter((s) => s.value > 0);

  if (!signals.length) return null;

  const total = signals.reduce((sum, s) => sum + s.value, 0);

  return (
    <div className="space-y-1">
      <div className="flex h-2 rounded-full overflow-hidden gap-px">
        {signals.map(({ key, value }) => (
          <div
            key={key}
            className={`${SIGNAL_COLORS[key]} transition-all`}
            style={{ width: `${(value / total) * 100}%` }}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5">
        {signals.map(({ key, value }) => (
          <span key={key} className="text-xs text-muted-foreground flex items-center gap-1">
            <span className={`inline-block h-2 w-2 rounded-full ${SIGNAL_COLORS[key]}`} />
            {SIGNAL_LABELS[key]} {value.toFixed(0)}
          </span>
        ))}
      </div>
    </div>
  );
}
```

---

## Step 4 — Keyboard Shortcuts

Keyboard navigation is wired into the run detail page, not inside individual cards.

### `web/app/runs/[id]/page.tsx` — keyboard handler

Add a `focusedIndex` state and a `useEffect` for `keydown`:

```tsx
const [focusedIndex, setFocusedIndex] = useState(0);

useEffect(() => {
  function onKey(e: KeyboardEvent) {
    // Don't hijack events inside <input>, <textarea>, <video> controls
    const tag = (e.target as HTMLElement).tagName;
    if (["INPUT", "TEXTAREA", "VIDEO", "BUTTON"].includes(tag)) return;

    switch (e.key) {
      case "ArrowRight":
      case "ArrowDown":
        e.preventDefault();
        setFocusedIndex((i) => Math.min(i + 1, clips.length - 1));
        break;
      case "ArrowLeft":
      case "ArrowUp":
        e.preventDefault();
        setFocusedIndex((i) => Math.max(i - 1, 0));
        break;
      case "j":
      case "J":
        // Approve focused clip
        if (clips[focusedIndex]) approveFocused(true);
        break;
      case "k":
      case "K":
        // Reject focused clip
        if (clips[focusedIndex]) approveFocused(false);
        break;
    }
  }
  window.addEventListener("keydown", onKey);
  return () => window.removeEventListener("keydown", onKey);
}, [clips, focusedIndex]);

async function approveFocused(approved: boolean) {
  const clip = clips[focusedIndex];
  if (!clip) return;
  const updated = await api.clips.patch(clip.id, { approved });
  handleClipUpdate(updated);
  // Advance focus to next clip automatically
  setFocusedIndex((i) => Math.min(i + 1, clips.length - 1));
}
```

Pass `focused={i === focusedIndex}` and `onFocus={() => setFocusedIndex(i)}` to each
`ClipCard`.

### Keyboard shortcut help tooltip

Add a floating `?` button in the bottom-right corner that shows a popover:

```
Arrow keys  Navigate clips
J           Approve focused clip
K           Reject focused clip
Space       Play / pause video
```

---

## Step 5 — `lib/types.ts` Update

Add `signal_breakdown` and `prompt_version` fields from Sprint 5:

```ts
export interface Clip {
  id: number;
  run_id: number;
  filename: string;
  title: string;
  start_s: number;
  end_s: number;
  score: number;
  approved: boolean | null;
  published_url: string | null;
  signal_breakdown: Record<string, number> | null;   // NEW
  created_at: string;
}

export interface Run {
  id: number;
  vod_id: string;
  channel: string;
  status: RunStatus;
  stage: string | null;
  error: string | null;
  prompt_version: string;   // NEW — "v1" | "v2"
  created_at: string;
  updated_at: string;
  clip_count: number;
}
```

---

## Step 6 — `api.ts` — `fileUrl` Fix

The existing `api.fileUrl` constructs a URL to serve the clip via FastAPI. Ensure it
routes through the correct path including `run_id`:

```ts
// lib/api.ts
fileUrl: (runId: number, filename: string): string =>
  `${DIRECT}/runs/${runId}/clips/file/${filename}`,
```

---

## File Layout (final state after Sprint 8)

```
web/
├── app/
│   └── runs/[id]/
│       └── page.tsx           MODIFIED — keyboard handler, focusedIndex, full layout
├── components/
│   ├── ClipCard.tsx           NEW — lazy video, approve/reject, signal breakdown
│   ├── ProgressStream.tsx     NEW — SSE hook → Progress bar
│   └── SignalBreakdownBar.tsx NEW — stacked colour bar + legend
└── lib/
    ├── types.ts               MODIFIED — signal_breakdown, prompt_version fields
    └── api.ts                 MODIFIED — fileUrl includes run_id
```

---

## Verification Checklist

### Progress bar
- [ ] Navigate to `/runs/{id}` while a run is active → SSE progress bar appears and updates live
- [ ] Bar reaches 100% and `onDone` fires when stage = "done"
- [ ] If SSE disconnects, error message shown (not blank)
- [ ] Bar disappears when run status is `done` or `failed` (static)

### Clip grid
- [ ] Each clip card renders with title, duration, score badge
- [ ] Video player is not loaded until card scrolls into view (IntersectionObserver)
- [ ] Video plays when loaded; approve/reject buttons work
- [ ] Green ring on approved, red ring on rejected, no ring on null

### Keyboard shortcuts
- [ ] Arrow keys move focus between cards (highlighted with blue ring)
- [ ] Focused video auto-plays; unfocused pauses
- [ ] J key approves focused clip and advances focus
- [ ] K key rejects focused clip and advances focus
- [ ] Keyboard events do not fire while inside `<input>` or `<video controls>`

### Signal breakdown
- [ ] Bar renders when `clip.signal_breakdown` is not null
- [ ] Segments are proportional to signal contribution values
- [ ] Only signals with value > 0 are shown

### TypeScript
- [ ] `pnpm build` with no type errors
- [ ] `tsc --noEmit` passes
