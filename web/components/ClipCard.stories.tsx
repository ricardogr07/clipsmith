import type { Meta, StoryObj } from "@storybook/react";
import { userEvent, within } from "storybook/test";
import { ClipCard } from "./ClipCard";
import { sampleClips } from "@/lib/fixtures";
import type { Clip } from "@/lib/types";

const [epicClip, untitledClip] = sampleClips as Clip[];

const meta: Meta<typeof ClipCard> = {
  title: "Components/ClipCard",
  component: ClipCard,
  parameters: { nextjs: { appDirectory: true } },
  args: { onUpdate: () => {} },
};

export default meta;
type Story = StoryObj<typeof ClipCard>;

export const Untitled: Story = {
  args: { clip: untitledClip },
};

export const Approved: Story = {
  args: { clip: { ...epicClip, approved: true } },
};

export const Rejected: Story = {
  args: { clip: { ...epicClip, approved: false } },
};

export const Default: Story = {
  args: { clip: epicClip },
};

export const OptionsOpen: Story = {
  args: { clip: epicClip },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(canvas.getByTitle("More options"));
  },
};
