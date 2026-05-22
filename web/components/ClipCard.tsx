"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ClipModal } from "@/components/ClipModal";
import { ClipMoreOptions } from "@/components/ClipMoreOptions";
import { SignalBreakdownBar } from "@/components/SignalBreakdownBar";
import { api } from "@/lib/api";
import type { Clip } from "@/lib/types";

interface Props {
  clip: Clip;
  focused?: boolean;
  onUpdate: (updated: Clip) => void;
  onFocus?: () => void;
}

export function ClipCard({ clip: initialClip, focused = false, onUpdate, onFocus }: Props) {
  const [clip, setClip] = useState(initialClip);
  const [showModal, setShowModal] = useState(false);
  const [showOptions, setShowOptions] = useState(false);

  // Sync local state when parent updates the clip (e.g. via keyboard shortcuts)
  useEffect(() => {
    setClip(initialClip);
  }, [initialClip]);

  function handleUpdate(updated: Clip) {
    setClip(updated);
    onUpdate(updated);
  }

  async function handleApprove(approved: boolean) {
    try {
      const updated = await api.clips.patch(clip.id, { approved });
      handleUpdate(updated);
    } catch {
      // swallow — user can retry
    }
  }

  const focusRing = focused ? "ring-2 ring-blue-500" : "";
  const approvalRing =
    clip.approved === true
      ? "ring-2 ring-green-500"
      : clip.approved === false
        ? "ring-2 ring-red-500"
        : "";

  return (
    <>
      <Card
        className={`overflow-hidden cursor-pointer transition-all ${focusRing || approvalRing}`}
        onClick={onFocus}
      >
        {/* Thumbnail / preview area */}
        <button
          onClick={(e) => { e.stopPropagation(); setShowModal(true); }}
          className="w-full aspect-video bg-muted flex items-center justify-center group hover:bg-muted/80 transition-colors"
          aria-label={`Play ${clip.title || clip.filename}`}
        >
          <span className="text-4xl opacity-40 group-hover:opacity-70 transition-opacity">▶</span>
        </button>

        <CardContent className="p-3 space-y-3">
          <div className="flex items-start gap-2">
            <p className="text-sm font-medium flex-1 leading-tight truncate">
              {clip.title || (
                <em className="text-muted-foreground">untitled</em>
              )}
            </p>
            {clip.approved === true && <Badge variant="secondary">Approved</Badge>}
            {clip.approved === false && <Badge variant="destructive">Rejected</Badge>}
          </div>

          {clip.signal_breakdown && (
            <SignalBreakdownBar breakdown={clip.signal_breakdown} />
          )}

          <div className="flex gap-2">
            <Button
              size="sm"
              variant={clip.approved === true ? "default" : "outline"}
              onClick={(e) => { e.stopPropagation(); handleApprove(true); }}
              className="flex-1 text-xs"
            >
              Approve
            </Button>
            <Button
              size="sm"
              variant={clip.approved === false ? "destructive" : "outline"}
              onClick={(e) => { e.stopPropagation(); handleApprove(false); }}
              className="flex-1 text-xs"
            >
              Reject
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={(e) => { e.stopPropagation(); setShowOptions((v) => !v); }}
              className="px-2 text-xs"
              title="More options"
            >
              {showOptions ? "▲" : "···"}
            </Button>
          </div>

          {showOptions && (
            <ClipMoreOptions clip={clip} onUpdate={handleUpdate} />
          )}
        </CardContent>
      </Card>

      {showModal && (
        <ClipModal
          clip={clip}
          onClose={() => setShowModal(false)}
          onUpdate={handleUpdate}
        />
      )}
    </>
  );
}
