"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { NewRunDialog } from "@/components/NewRunDialog";
import { RunCard } from "@/components/RunCard";
import { api } from "@/lib/api";
import type { Run } from "@/lib/types";

const POLL_INTERVAL_MS = 5000;

function hasActiveRun(runs: Run[]): boolean {
  return runs.some((r) => r.status === "pending" || r.status === "running");
}

export default function DashboardPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchRuns = useCallback(async () => {
    try {
      const data = await api.runs.list();
      setRuns(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load runs");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (!hasActiveRun(runs)) return;
    timerRef.current = setTimeout(fetchRuns, POLL_INTERVAL_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [runs, fetchRuns]);

  function handleCreated(run: Run) {
    setRuns((prev) => [run, ...prev]);
  }

  function handleDeleted(id: number) {
    setRuns((prev) => prev.filter((r) => r.id !== id));
  }

  return (
    <main className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">clipsmith</h1>
          <p className="text-sm text-muted-foreground">AI clip pipeline dashboard</p>
        </div>
        <NewRunDialog onCreated={handleCreated} />
      </div>

      {loading && (
        <p className="text-muted-foreground text-sm">Loading runs…</p>
      )}

      {error && (
        <p className="text-destructive text-sm">{error}</p>
      )}

      {!loading && runs.length === 0 && !error && (
        <div className="text-center py-16 text-muted-foreground">
          <p className="text-lg">No runs yet.</p>
          <p className="text-sm mt-1">Click &ldquo;New Run&rdquo; to start the pipeline.</p>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {runs.map((run) => (
          <RunCard key={run.id} run={run} onDelete={handleDeleted} />
        ))}
      </div>
    </main>
  );
}
