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
