import { ClipModal } from "../../components/ClipModal";
import { api } from "../../lib/api";
import type { Clip } from "../../lib/types";

const base: Clip = {
  id: 1,
  run_id: 1,
  filename: "clip_01.mp4",
  title: "Epic play",
  start_s: 10,
  end_s: 40,
  score: 0.82,
  approved: null,
  created_at: "2026-01-01T00:00:00Z",
};

describe("ClipModal", () => {
  it("video src contains the clip filename", () => {
    cy.mount(<ClipModal clip={base} onClose={cy.spy()} onUpdate={cy.spy()} />);
    cy.get("video").should("have.attr", "src").and("include", "clip_01.mp4");
  });

  it("shows clip title", () => {
    cy.mount(<ClipModal clip={base} onClose={cy.spy()} onUpdate={cy.spy()} />);
    cy.contains("Epic play").should("be.visible");
  });

  it("shows duration label", () => {
    cy.mount(<ClipModal clip={base} onClose={cy.spy()} onUpdate={cy.spy()} />);
    cy.contains("30.0s").should("be.visible");
  });

  it("✕ button calls onClose", () => {
    const onClose = cy.spy().as("onClose");
    cy.mount(<ClipModal clip={base} onClose={onClose} onUpdate={cy.spy()} />);
    cy.get("button[aria-label='Close']").click();
    cy.get("@onClose").should("have.been.calledOnce");
  });

  it("Escape key calls onClose", () => {
    const onClose = cy.spy().as("onClose");
    cy.mount(<ClipModal clip={base} onClose={onClose} onUpdate={cy.spy()} />);
    cy.get("body").type("{esc}");
    cy.get("@onClose").should("have.been.calledOnce");
  });

  it("clicking backdrop (outside modal box) calls onClose", () => {
    const onClose = cy.spy().as("onClose");
    cy.mount(<ClipModal clip={base} onClose={onClose} onUpdate={cy.spy()} />);
    cy.get(".fixed.inset-0").click(5, 5);
    cy.get("@onClose").should("have.been.calledOnce");
  });

  it("Approve button calls patch with approved: true", () => {
    cy.stub(api.clips, "patch").as("patch").resolves({ ...base, approved: true });
    cy.mount(<ClipModal clip={base} onClose={cy.spy()} onUpdate={cy.spy()} />);
    cy.contains("Approve").click();
    cy.get("@patch").should("have.been.calledWith", 1, { approved: true });
  });

  it("Reject button calls patch with approved: false", () => {
    cy.stub(api.clips, "patch").as("patch").resolves({ ...base, approved: false });
    cy.mount(<ClipModal clip={base} onClose={cy.spy()} onUpdate={cy.spy()} />);
    cy.contains("Reject").click();
    cy.get("@patch").should("have.been.calledWith", 1, { approved: false });
  });
});
