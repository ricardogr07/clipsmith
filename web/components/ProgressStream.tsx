"use client";

import { useEffect, useRef, useState } from "react";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import type { PipelineEvent } from "@/lib/types";

type EventSourceFactory = (url: string) => EventSource;

interface StreamState {
  stage: string;
  pct: number;
  message: string;
  done: boolean;
  error: string | null;
}

interface Props {
  runId: number;
  onDone?: () => void;
  eventSourceFactory?: EventSourceFactory;
}

const MAX_RETRIES = 5;

export function ProgressStream({ runId, onDone, eventSourceFactory }: Props) {
  const [state, setState] = useState<StreamState>({
    stage: "starting",
    pct: 0,
    message: "",
    done: false,
    error: null,
  });
  const esRef = useRef<EventSource | null>(null);
  const retriesRef = useRef(0);

  useEffect(() => {
    const factory = eventSourceFactory ?? ((url: string) => new EventSource(url));

    function connect() {
      esRef.current?.close();
      const es = factory(api.sseUrl(runId));
      esRef.current = es;

      es.onmessage = (e) => {
        retriesRef.current = 0; // reset on any successful message
        try {
          const data = JSON.parse(e.data) as Partial<PipelineEvent> & {
            event?: string;
            status?: string;
            error?: string;
          };

          if (data.event === "end") {
            setState((s) => ({
              ...s,
              done: true,
              pct: data.status === "done" ? 100 : s.pct,
              error: data.error ?? null,
            }));
            es.close();
            onDone?.();
            return;
          }

          if (data.stage !== undefined) {
            setState((s) => ({
              ...s,
              stage: data.stage!,
              pct: data.pct ?? s.pct,
              message: data.message ?? "",
            }));
          }
        } catch {
          // malformed SSE frame — skip
        }
      };

      es.onerror = () => {
        es.close();
        if (retriesRef.current < MAX_RETRIES) {
          retriesRef.current += 1;
          // exponential back-off: 2s, 4s, 8s, 16s, 32s
          setTimeout(connect, Math.min(2 ** retriesRef.current * 1000, 32_000));
        } else {
          setState((s) => ({ ...s, done: true, error: "Stream disconnected" }));
        }
      };
    }

    connect();

    return () => {
      esRef.current?.close();
    };
  }, [runId, onDone, eventSourceFactory]);

  if (state.done && !state.error) {
    return (
      <div className="space-y-2">
        <Progress value={100} className="h-2" />
        <p className="text-sm text-green-600 font-medium">Pipeline complete</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium capitalize">{state.stage}</span>
        <span className="text-muted-foreground">{Math.round(state.pct)}%</span>
      </div>
      <Progress value={state.pct} className="h-2" />
      {state.message && <p className="text-xs text-muted-foreground">{state.message}</p>}
      {state.error && <p className="text-xs text-destructive">{state.error}</p>}
    </div>
  );
}
