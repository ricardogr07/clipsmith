import { ClipCard } from "../../components/ClipCard";
import { api } from "../../lib/api";
import type { Clip } from "../../lib/types";

const base: Clip = {
  id: 1,
  run_id: 1,
  filename: "clip_01.mp4",
  title: "Epic play",
  start_s: 65,
  end_s: 125,
  score: 0.82,
  approved: null,
  created_at: "2026-01-01T00:00:00Z",
};

describe("ClipCard", () => {
  it("renders clip title", () => {
    cy.mount(<ClipCard clip={base} onUpdate={cy.spy()} />);
    cy.contains("Epic play").should("be.visible");
  });

  it("renders italic placeholder for untitled clip", () => {
    cy.mount(<ClipCard clip={{ ...base, title: "" }} onUpdate={cy.spy()} />);
    cy.get("em").contains("untitled").should("be.visible");
  });

  it("shows Approved badge when approved: true", () => {
    cy.mount(<ClipCard clip={{ ...base, approved: true }} onUpdate={cy.spy()} />);
    cy.contains("Approved").should("be.visible");
  });

  it("shows Rejected badge when approved: false", () => {
    cy.mount(<ClipCard clip={{ ...base, approved: false }} onUpdate={cy.spy()} />);
    cy.contains("Rejected").should("be.visible");
  });

  it("Approve button calls patch and fires onUpdate", () => {
    cy.stub(api.clips, "patch").as("patch").resolves({ ...base, approved: true });
    const onUpdate = cy.spy().as("onUpdate");
    cy.mount(<ClipCard clip={base} onUpdate={onUpdate} />);
    cy.contains("Approve").click();
    cy.get("@onUpdate").should("have.been.calledOnce");
  });

  it("Reject button calls patch and fires onUpdate", () => {
    cy.stub(api.clips, "patch").as("patch").resolves({ ...base, approved: false });
    const onUpdate = cy.spy().as("onUpdate");
    cy.mount(<ClipCard clip={base} onUpdate={onUpdate} />);
    cy.contains("Reject").click();
    cy.get("@onUpdate").should("have.been.calledOnce");
  });

  it("··· button toggles ClipMoreOptions panel", () => {
    cy.mount(<ClipCard clip={base} onUpdate={cy.spy()} />);
    cy.contains("···").click();
    cy.contains("Score").should("be.visible");
  });

  it("play button opens ClipModal with video", () => {
    cy.mount(<ClipCard clip={base} onUpdate={cy.spy()} />);
    cy.get("[aria-label^='Play']").click();
    cy.get("video").should("exist");
  });
});
