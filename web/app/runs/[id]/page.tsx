"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ClipCard } from "@/components/ClipCard";
import { ProgressStream } from "@/components/ProgressStream";
import { api } from "@/lib/api";
import type { Clip, Run } from "@/lib/types";

const POLL_INTERVAL_MS = 3000;

export default function RunDetailPage() {
  const params = useParams();
  const router = useRouter();
  const runId = Number(params.id);

  const [run, setRun] = useState<Run | null>(null);
  const [clips, setClips] = useState<Clip[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isActive = run?.status === "pending" || run?.status === "running";

  const fetchClips = useCallback(async () => {
    try {
      const data = await api.clips.list(runId);
      setClips(data);
    } catch {
      // don't clobber the main error
    }
  }, [runId]);

  const fetchRun = useCallback(async () => {
    try {
      const data = await api.runs.get(runId);
      setRun(data);
      setError(null);
      if (data.status === "done" || data.status === "failed") {
        await fetchClips();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load run");
    } finally {
      setLoading(false);
    }
  }, [runId, fetchClips]);

  useEffect(() => {
    fetchRun();
    fetchClips();
  }, [fetchRun, fetchClips]);

  // Poll while active
  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (!isActive) return;
    timerRef.current = setTimeout(async () => {
      await Promise.all([fetchRun(), fetchClips()]);
    }, POLL_INTERVAL_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [isActive, fetchRun, fetchClips]);

  function handleSseDone() {
    setTimeout(() => {
      fetchRun();
      fetchClips();
    }, 500);
  }

  function handleClipUpdate(updated: Clip) {
    setClips((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
  }

  if (loading) {
    return (
      <main className="max-w-4xl mx-auto px-4 py-8">
        <p className="text-muted-foreground text-sm">Loading…</p>
      </main>
    );
  }

  if (error || !run) {
    return (
      <main className="max-w-4xl mx-auto px-4 py-8 space-y-4">
        <p className="text-destructive">{error ?? "Run not found"}</p>
        <Button variant="outline" onClick={() => router.push("/")}>
          ← Back
        </Button>
      </main>
    );
  }

  const statusVariant =
    run.status === "done"
      ? "secondary"
      : run.status === "failed"
        ? "destructive"
        : run.status === "running"
          ? "default"
          : "outline";

  return (
    <main className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      <div className="flex items-start gap-3">
        <Button variant="ghost" size="sm" onClick={() => router.push("/")}>
          ←
        </Button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-xl font-bold font-mono truncate">{run.vod_id}</h1>
            <Badge variant={statusVariant}>{run.status}</Badge>
          </div>
          {run.channel && (
            <p className="text-sm text-muted-foreground">@{run.channel}</p>
          )}
        </div>
      </div>

      {isActive && (
        <div className="rounded-lg border p-4">
          <p className="text-sm font-medium mb-3">Pipeline progress</p>
          <ProgressStream runId={runId} onDone={handleSseDone} />
        </div>
      )}

      {run.status === "failed" && run.error && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4">
          <p className="text-sm font-medium text-destructive mb-1">Pipeline failed</p>
          <p className="text-xs text-muted-foreground font-mono">{run.error}</p>
        </div>
      )}

      {clips.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">
            Clips{" "}
            <span className="text-muted-foreground font-normal text-base">
              ({clips.length})
            </span>
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {clips.map((clip) => (
              <ClipCard key={clip.id} clip={clip} onUpdate={handleClipUpdate} />
            ))}
          </div>
        </div>
      )}

      {run.status === "done" && clips.length === 0 && (
        <p className="text-muted-foreground text-sm">
          Pipeline completed but no clips were generated.
        </p>
      )}
    </main>
  );
}
