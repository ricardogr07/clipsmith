import type { Meta, StoryObj } from "@storybook/react";
import { userEvent, within } from "storybook/test";
import { ClipMoreOptions } from "./ClipMoreOptions";
import { sampleClips } from "@/lib/fixtures";
import type { Clip } from "@/lib/types";

const [epicClip] = sampleClips as Clip[];

const meta: Meta<typeof ClipMoreOptions> = {
  title: "Components/ClipMoreOptions",
  component: ClipMoreOptions,
  parameters: { nextjs: { appDirectory: true } },
  args: { onUpdate: () => {} },
};

export default meta;
type Story = StoryObj<typeof ClipMoreOptions>;

export const Default: Story = {
  args: { clip: epicClip },
};

export const ZeroScore: Story = {
  args: { clip: { ...epicClip, score: 0 } },
};

export const HighScore: Story = {
  args: { clip: { ...epicClip, score: 0.99 } },
};

export const EditingTitle: Story = {
  args: { clip: epicClip },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // Click the title text to enter edit mode
    await userEvent.click(canvas.getByTitle("Click to edit"));
  },
};
