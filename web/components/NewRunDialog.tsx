"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { Run } from "@/lib/types";

interface Props {
  onCreated: (run: Run) => void;
}

export function NewRunDialog({ onCreated }: Props) {
  const [open, setOpen] = useState(false);
  const [vodId, setVodId] = useState("");
  const [channel, setChannel] = useState("");
  const [startS, setStartS] = useState("");
  const [endS, setEndS] = useState("");
  const [cloud, setCloud] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleOpenChange(next: boolean) {
    setOpen(next);
    if (!next) {
      setVodId("");
      setChannel("");
      setStartS("");
      setEndS("");
      setCloud(true);
      setError(null);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!vodId.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const run = await api.runs.create({
        vod_id: vodId.trim(),
        channel: channel.trim() || undefined,
        start_s: startS ? parseFloat(startS) : undefined,
        end_s: endS ? parseFloat(endS) : undefined,
        cloud,
      });
      onCreated(run);
      handleOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create run");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger render={<Button />}>New Run</DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Start a new pipeline run</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 mt-2">
          <div className="space-y-1">
            <label className="text-sm font-medium">VOD ID *</label>
            <Input
              placeholder="e.g. 2345678901"
              value={vodId}
              onChange={(e) => setVodId(e.target.value)}
              required
              autoFocus
            />
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium">Channel (optional)</label>
            <Input
              placeholder="e.g. streamer_name"
              value={channel}
              onChange={(e) => setChannel(e.target.value)}
            />
          </div>
          <div className="flex gap-2">
            <div className="space-y-1 flex-1">
              <label className="text-sm font-medium">Start (s)</label>
              <Input
                type="number"
                min="0"
                placeholder="0"
                value={startS}
                onChange={(e) => setStartS(e.target.value)}
              />
            </div>
            <div className="space-y-1 flex-1">
              <label className="text-sm font-medium">End (s)</label>
              <Input
                type="number"
                min="0"
                placeholder="0 = full VOD"
                value={endS}
                onChange={(e) => setEndS(e.target.value)}
              />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={cloud}
              onChange={(e) => setCloud(e.target.checked)}
              className="h-4 w-4"
            />
            Cloud offload (ACI)
          </label>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading || !vodId.trim()}>
              {loading ? "Starting…" : "Start"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
