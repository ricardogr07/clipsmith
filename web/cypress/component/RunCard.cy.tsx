import { RunCard } from "../../components/RunCard";
import type { Run } from "../../lib/types";

const base: Run = {
  id: 1,
  vod_id: "2763505810",
  channel: "chuyelwuero",
  status: "done",
  stage: null,
  error: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  clip_count: 0,
};

describe("RunCard", () => {
  it("shows Pending badge and 0 clips", () => {
    cy.mount(<RunCard run={{ ...base, status: "pending" }} />);
    cy.contains("Pending").should("be.visible");
    cy.contains("0 clips").should("be.visible");
  });

  it("shows Running badge and stage label", () => {
    cy.mount(<RunCard run={{ ...base, status: "running", stage: "transcribe" }} />);
    cy.contains("Running").should("be.visible");
    cy.contains("transcribe…").should("be.visible");
  });

  it("shows Done badge with clip count", () => {
    cy.mount(<RunCard run={{ ...base, status: "done", clip_count: 5 }} />);
    cy.contains("Done").should("be.visible");
    cy.contains("5 clips").should("be.visible");
  });

  it("uses singular 'clip' for count of 1", () => {
    cy.mount(<RunCard run={{ ...base, status: "done", clip_count: 1 }} />);
    cy.contains("1 clip").should("be.visible");
    cy.contains("1 clips").should("not.exist");
  });

  it("shows Failed badge with error text", () => {
    cy.mount(<RunCard run={{ ...base, status: "failed", error: "oom" }} />);
    cy.contains("Failed").should("be.visible");
    cy.contains("oom").should("be.visible");
  });

  it("renders anchor linking to the run detail page", () => {
    cy.mount(<RunCard run={{ ...base, status: "done" }} />);
    cy.get("a").should("have.attr", "href", "/runs/1");
  });
});
