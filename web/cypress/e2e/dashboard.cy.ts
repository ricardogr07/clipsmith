import runs from "../fixtures/runs.json";
import type { Run } from "../../lib/types";

const [doneRun, pendingRun] = runs as Run[];
const newRun: Run = {
  ...doneRun,
  id: 3,
  vod_id: "9999999999",
  status: "pending",
  clip_count: 0,
};

describe("Dashboard page", () => {
  it("shows empty state when no runs exist", () => {
    cy.intercept("GET", "/api/runs", { body: [] }).as("getRuns");
    cy.visit("/");
    cy.wait("@getRuns");
    cy.contains("No runs yet.").should("be.visible");
  });

  it("renders a RunCard for each run returned", () => {
    cy.intercept("GET", "/api/runs", { body: runs }).as("getRuns");
    cy.visit("/");
    cy.wait("@getRuns");
    cy.contains(doneRun.vod_id).should("be.visible");
    cy.contains(pendingRun.vod_id).should("be.visible");
  });

  it("shows correct status badges for pending and done runs", () => {
    cy.intercept("GET", "/api/runs", { body: runs }).as("getRuns");
    cy.visit("/");
    cy.wait("@getRuns");
    cy.contains("Done").should("be.visible");
    cy.contains("Pending").should("be.visible");
  });

  it("opens New Run dialog on button click", () => {
    cy.intercept("GET", "/api/runs", { body: [] }).as("getRuns");
    cy.visit("/");
    cy.wait("@getRuns");
    cy.contains("New Run").click();
    cy.contains("VOD ID").should("be.visible");
  });

  it("creates a run and shows new card at top of list", () => {
    cy.intercept("GET", "/api/runs", { body: [] }).as("getRuns");
    cy.intercept("POST", "/api/runs", { statusCode: 201, body: newRun }).as("postRun");
    cy.visit("/");
    cy.wait("@getRuns");
    cy.contains("New Run").click();
    cy.get("input").first().type("9999999999");
    cy.get("button[type=submit]").click();
    cy.wait("@postRun");
    cy.contains("9999999999").should("be.visible");
  });

  it("shows error message in dialog on 401 response", () => {
    cy.intercept("GET", "/api/runs", { body: [] }).as("getRuns");
    cy.intercept("POST", "/api/runs", {
      statusCode: 401,
      body: { detail: "Unauthorized" },
    }).as("postRun");
    cy.visit("/");
    cy.wait("@getRuns");
    cy.contains("New Run").click();
    cy.get("input").first().type("9999999999");
    cy.get("button[type=submit]").click();
    cy.wait("@postRun");
    cy.contains("401").should("be.visible");
  });

  it("navigates to run detail page when a run card is clicked", () => {
    cy.intercept("GET", "/api/runs", { body: runs }).as("getRuns");
    cy.visit("/");
    cy.wait("@getRuns");
    cy.contains(doneRun.vod_id).closest("a").click();
    cy.url().should("include", `/runs/${doneRun.id}`);
  });
});
