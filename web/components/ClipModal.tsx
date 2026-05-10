"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Clip } from "@/lib/types";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

interface Props {
  clip: Clip;
  onClose: () => void;
  onUpdate: (updated: Clip) => void;
}

export function ClipModal({ clip, onClose, onUpdate }: Props) {
  const duration = clip.end_s - clip.start_s;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function handleApprove(approved: boolean) {
    try {
      const updated = await api.clips.patch(clip.id, { approved });
      onUpdate(updated);
    } catch {
      // swallow — user can retry
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="relative bg-background rounded-lg shadow-2xl max-w-3xl w-full mx-4 overflow-hidden">
        <button
          onClick={onClose}
          className="absolute top-3 right-3 z-10 text-muted-foreground hover:text-foreground text-xl leading-none"
          aria-label="Close"
        >
          ✕
        </button>

        {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
        <video
          src={api.fileUrl(clip.run_id, clip.filename)}
          controls
          autoPlay
          className="w-full max-h-[60vh] bg-black"
        />

        <div className="p-4 space-y-3">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="font-medium text-sm leading-snug">
                {clip.title || <em className="text-muted-foreground">untitled</em>}
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {formatTime(clip.start_s)} → {formatTime(clip.end_s)}{" "}
                <span className="ml-1">({duration.toFixed(1)}s)</span>
              </p>
            </div>
            <span className="text-xs font-mono text-muted-foreground shrink-0">
              score {clip.score.toFixed(2)}
            </span>
          </div>

          <div className="flex gap-2">
            <Button
              size="sm"
              variant={clip.approved === true ? "default" : "outline"}
              onClick={() => handleApprove(true)}
              className="flex-1"
            >
              Approve
            </Button>
            <Button
              size="sm"
              variant={clip.approved === false ? "destructive" : "outline"}
              onClick={() => handleApprove(false)}
              className="flex-1"
            >
              Reject
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
