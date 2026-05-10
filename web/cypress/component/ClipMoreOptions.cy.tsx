import { ClipMoreOptions } from "../../components/ClipMoreOptions";
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

describe("ClipMoreOptions", () => {
  it("renders score bar at correct proportional width", () => {
    cy.mount(<ClipMoreOptions clip={{ ...base, score: 0.75 }} onUpdate={cy.spy()} />);
    cy.get("[style*='width']").should(($el) => {
      const style = $el.attr("style") ?? "";
      expect(style).to.match(/75%/);
    });
  });

  it("renders score bar at 0% for zero score", () => {
    cy.mount(<ClipMoreOptions clip={{ ...base, score: 0 }} onUpdate={cy.spy()} />);
    cy.get("[style*='width: 0%']").should("exist");
  });

  it("formats start and end timestamps correctly", () => {
    cy.mount(<ClipMoreOptions clip={base} onUpdate={cy.spy()} />);
    cy.contains("1:05").should("be.visible");
    cy.contains("2:05").should("be.visible");
  });

  it("shows clip duration in seconds", () => {
    cy.mount(<ClipMoreOptions clip={base} onUpdate={cy.spy()} />);
    cy.contains("60.0s").should("be.visible");
  });

  it("clicking title text shows an input with existing value", () => {
    cy.mount(<ClipMoreOptions clip={base} onUpdate={cy.spy()} />);
    cy.contains("Epic play").click();
    cy.get("input").should("have.value", "Epic play");
  });

  it("blurring input saves new title via patch", () => {
    cy.stub(api.clips, "patch").as("patch").resolves({ ...base, title: "New title" });
    cy.mount(<ClipMoreOptions clip={base} onUpdate={cy.spy()} />);
    cy.contains("Epic play").click();
    cy.get("input").clear().type("New title").blur();
    cy.get("@patch").should("have.been.calledWith", 1, { title: "New title" });
  });

  it("pressing Enter saves new title via patch", () => {
    cy.stub(api.clips, "patch").as("patch").resolves({ ...base, title: "New title" });
    cy.mount(<ClipMoreOptions clip={base} onUpdate={cy.spy()} />);
    cy.contains("Epic play").click();
    cy.get("input").clear().type("New title{enter}");
    cy.get("@patch").should("have.been.called");
  });

  it("pressing Escape reverts title without calling patch", () => {
    cy.stub(api.clips, "patch").as("patch");
    cy.mount(<ClipMoreOptions clip={base} onUpdate={cy.spy()} />);
    cy.contains("Epic play").click();
    cy.get("input").clear().type("Discarded{esc}");
    cy.contains("Epic play").should("be.visible");
    cy.get("@patch").should("not.have.been.called");
  });

  it("patch error reverts title to original", () => {
    cy.stub(api.clips, "patch").as("patch").rejects(new Error("500"));
    cy.mount(<ClipMoreOptions clip={base} onUpdate={cy.spy()} />);
    cy.contains("Epic play").click();
    cy.get("input").clear().type("Discarded").blur();
    cy.contains("Epic play").should("be.visible");
  });
});
