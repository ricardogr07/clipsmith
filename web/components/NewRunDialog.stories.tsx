import type { Meta, StoryObj } from "@storybook/react";
import { userEvent, within } from "storybook/test";
import { NewRunDialog } from "./NewRunDialog";
import { api } from "@/lib/api";
import { sampleRun } from "@/lib/fixtures";

const meta: Meta<typeof NewRunDialog> = {
  title: "Components/NewRunDialog",
  component: NewRunDialog,
  parameters: { nextjs: { appDirectory: true } },
  args: { onCreated: () => {} },
};

export default meta;
type Story = StoryObj<typeof NewRunDialog>;

export const Default: Story = {};

export const Open: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(canvas.getByText("New Run"));
  },
};

export const Submitting: Story = {
  beforeEach: () => {
    const original = api.runs.create;
    api.runs.create = () => new Promise(() => {}); // never resolves
    return () => {
      api.runs.create = original;
    };
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(canvas.getByText("New Run"));
    await userEvent.type(
      canvas.getByPlaceholderText("e.g. 2345678901"),
      sampleRun.vod_id
    );
    await userEvent.click(canvas.getByRole("button", { name: /start/i }));
  },
};

export const WithError: Story = {
  beforeEach: () => {
    const original = api.runs.create;
    api.runs.create = async () => {
      throw new Error("401: Unauthorized");
    };
    return () => {
      api.runs.create = original;
    };
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(canvas.getByText("New Run"));
    await userEvent.type(
      canvas.getByPlaceholderText("e.g. 2345678901"),
      sampleRun.vod_id
    );
    await userEvent.click(canvas.getByRole("button", { name: /start/i }));
  },
};
