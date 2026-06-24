"use client";

import Link from "next/link";
import { Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { Run, RunStatus } from "@/lib/types";

const STATUS_VARIANT: Record<RunStatus, "default" | "secondary" | "destructive" | "outline"> = {
  pending: "outline",
  running: "default",
  done: "secondary",
  failed: "destructive",
};

const STATUS_LABEL: Record<RunStatus, string> = {
  pending: "Pending",
  running: "Running",
  done: "Done",
  failed: "Failed",
};

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

interface RunCardProps {
  run: Run;
  onDelete?: (id: number) => void;
}

export function RunCard({ run, onDelete }: RunCardProps) {
  async function handleDelete(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    try {
      await api.runs.delete(run.id);
      onDelete?.(run.id);
    } catch (err) {
      console.error("Failed to delete run:", err);
    }
  }

  return (
    <Link href={`/runs/${run.id}`} className="block hover:no-underline">
      <Card className="hover:shadow-md transition-shadow cursor-pointer">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-base font-mono truncate">{run.vod_id}</CardTitle>
            <div className="flex items-center gap-1 shrink-0">
              <Badge variant={STATUS_VARIANT[run.status]}>{STATUS_LABEL[run.status]}</Badge>
              {run.status === "failed" && onDelete && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 text-muted-foreground hover:text-destructive"
                  onClick={handleDelete}
                  aria-label="Delete run"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              )}
            </div>
          </div>
          {run.channel && (
            <p className="text-sm text-muted-foreground">@{run.channel}</p>
          )}
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>{run.clip_count} clip{run.clip_count !== 1 ? "s" : ""}</span>
            <span>{relativeTime(run.created_at)}</span>
          </div>
          {run.stage && run.status === "running" && (
            <p className="mt-1 text-xs text-blue-500">{run.stage}…</p>
          )}
          {run.error && run.status === "failed" && (
            <p className="mt-1 text-xs text-destructive truncate">{run.error}</p>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}
