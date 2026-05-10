import type { Meta, StoryObj } from "@storybook/react";
import { ProgressStream } from "./ProgressStream";

type FakeES = {
  onmessage: ((e: { data: string }) => void) | null;
  onerror: ((e: Event) => void) | null;
  close: () => void;
};

function makeFactory(events: object[], triggerError = false) {
  return (url: string): EventSource => {
    const es: FakeES = {
      onmessage: null,
      onerror: null,
      close() {},
    };

    // Fire events asynchronously after component mounts
    setTimeout(() => {
      if (triggerError) {
        es.onerror?.(new Event("error"));
        return;
      }
      for (const data of events) {
        es.onmessage?.({ data: JSON.stringify(data) });
      }
    }, 100);

    return es as unknown as EventSource;
  };
}

const meta: Meta<typeof ProgressStream> = {
  title: "Components/ProgressStream",
  component: ProgressStream,
  parameters: { nextjs: { appDirectory: true } },
  args: { runId: 1, onDone: () => {} },
};

export default meta;
type Story = StoryObj<typeof ProgressStream>;

export const Starting: Story = {
  args: { eventSourceFactory: makeFactory([]) },
};

export const Transcribing: Story = {
  args: {
    eventSourceFactory: makeFactory([{ stage: "transcribe", pct: 40, message: "Processing audio…" }]),
  },
};

export const Complete: Story = {
  args: {
    eventSourceFactory: makeFactory([
      { stage: "export", pct: 95 },
      { event: "end", status: "done" },
    ]),
  },
};

export const Failed: Story = {
  args: {
    eventSourceFactory: makeFactory([
      { stage: "clip", pct: 50 },
      { event: "end", status: "failed", error: "OOM: process killed" },
    ]),
  },
};

export const Disconnected: Story = {
  args: { eventSourceFactory: makeFactory([], true) },
};
