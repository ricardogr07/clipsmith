export type RunStatus = "pending" | "running" | "done" | "failed";

export interface Run {
  id: number;
  vod_id: string;
  channel: string;
  status: RunStatus;
  stage: string | null;
  error: string | null;
  prompt_version: string;
  created_at: string;
  updated_at: string;
  clip_count: number;
}

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
  signal_breakdown: Record<string, number> | null;
  created_at: string;
}

export interface PipelineEvent {
  id: number;
  run_id: number;
  stage: string;
  pct: number;
  message: string;
  created_at: string;
}

export interface RunCreate {
  vod_id: string;
  channel?: string;
  provider?: string;
  start_s?: number;
  end_s?: number;
  cloud?: boolean;
}
