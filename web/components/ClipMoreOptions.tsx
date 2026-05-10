"use client";

import { useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { Clip } from "@/lib/types";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

interface Props {
  clip: Clip;
  onUpdate: (updated: Clip) => void;
}

export function ClipMoreOptions({ clip, onUpdate }: Props) {
  const [editing, setEditing] = useState(false);
  const [titleDraft, setTitleDraft] = useState(clip.title);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const duration = clip.end_s - clip.start_s;

  async function saveTitle() {
    if (titleDraft === clip.title) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      const updated = await api.clips.patch(clip.id, { title: titleDraft });
      onUpdate(updated);
      setEditing(false);
    } catch {
      setTitleDraft(clip.title);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="pt-3 mt-3 border-t space-y-3 text-sm">
      <div className="space-y-1">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Title
        </span>
        {editing ? (
          <Input
            ref={inputRef}
            value={titleDraft}
            onChange={(e) => setTitleDraft(e.target.value)}
            onBlur={saveTitle}
            onKeyDown={(e) => {
              if (e.key === "Enter") inputRef.current?.blur();
              if (e.key === "Escape") {
                setTitleDraft(clip.title);
                setEditing(false);
              }
            }}
            disabled={saving}
            className="h-7 text-sm"
            autoFocus
          />
        ) : (
          <p
            className="cursor-pointer hover:text-foreground text-muted-foreground truncate"
            onClick={() => setEditing(true)}
            title="Click to edit"
          >
            {clip.title || <em>untitled — click to edit</em>}
          </p>
        )}
      </div>

      <div className="space-y-1">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Score
        </span>
        <div className="flex items-center gap-2">
          <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-primary rounded-full"
              style={{ width: `${Math.min(clip.score * 100, 100)}%` }}
            />
          </div>
          <span className="text-xs tabular-nums">{clip.score.toFixed(2)}</span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 text-xs">
        <div>
          <span className="text-muted-foreground block">Start</span>
          <span className="font-mono">{formatTime(clip.start_s)}</span>
        </div>
        <div>
          <span className="text-muted-foreground block">End</span>
          <span className="font-mono">{formatTime(clip.end_s)}</span>
        </div>
        <div>
          <span className="text-muted-foreground block">Duration</span>
          <span className="font-mono">{duration.toFixed(1)}s</span>
        </div>
      </div>
    </div>
  );
}
