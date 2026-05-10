import type { Meta, StoryObj } from "@storybook/react";
import { RunCard } from "./RunCard";
import { sampleRuns } from "@/lib/fixtures";
import type { Run } from "@/lib/types";

const [doneRun, pendingRun] = sampleRuns as Run[];

const meta: Meta<typeof RunCard> = {
  title: "Components/RunCard",
  component: RunCard,
  parameters: { nextjs: { appDirectory: true } },
};

export default meta;
type Story = StoryObj<typeof RunCard>;

export const Pending: Story = {
  args: { run: { ...doneRun, status: "pending", clip_count: 0 } },
};

export const Running: Story = {
  args: { run: { ...doneRun, status: "running", stage: "transcribe", clip_count: 0 } },
};

export const Done: Story = {
  args: { run: { ...doneRun, status: "done", clip_count: 5 } },
};

export const Failed: Story = {
  args: { run: { ...doneRun, status: "failed", error: "OOM killed" } },
};

export const LongVodId: Story = {
  args: { run: { ...doneRun, vod_id: "a".repeat(40), status: "done", clip_count: 2 } },
};

export const WithChannel: Story = {
  args: { run: pendingRun },
};
