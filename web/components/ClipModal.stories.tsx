import type { Meta, StoryObj } from "@storybook/react";
import { ClipModal } from "./ClipModal";
import { sampleClips } from "@/lib/fixtures";
import type { Clip } from "@/lib/types";

const [epicClip] = sampleClips as Clip[];

const meta: Meta<typeof ClipModal> = {
  title: "Components/ClipModal",
  component: ClipModal,
  // Constrain the canvas so the full-viewport overlay fits without overflow
  decorators: [
    (Story) => (
      <div style={{ position: "relative", height: "600px", overflow: "hidden" }}>
        <Story />
      </div>
    ),
  ],
  parameters: { nextjs: { appDirectory: true } },
  args: {
    onClose: () => {},
    onUpdate: () => {},
  },
};

export default meta;
type Story = StoryObj<typeof ClipModal>;

export const Default: Story = {
  args: { clip: epicClip },
};

export const Approved: Story = {
  args: { clip: { ...epicClip, approved: true } },
};

export const Rejected: Story = {
  args: { clip: { ...epicClip, approved: false } },
};

export const Untitled: Story = {
  args: { clip: { ...epicClip, title: "" } },
};
