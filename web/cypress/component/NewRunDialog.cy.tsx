import { NewRunDialog } from "../../components/NewRunDialog";
import { api } from "../../lib/api";
import type { Run } from "../../lib/types";

const fakeRun: Run = {
  id: 1,
  vod_id: "123456",
  channel: "",
  status: "pending",
  stage: null,
  error: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  clip_count: 0,
};

describe("NewRunDialog", () => {
  it("dialog is closed by default", () => {
    cy.mount(<NewRunDialog onCreated={cy.spy()} />);
    cy.contains("VOD ID").should("not.exist");
  });

  it("opens on trigger click", () => {
    cy.mount(<NewRunDialog onCreated={cy.spy()} />);
    cy.contains("New Run").click();
    cy.contains("VOD ID").should("be.visible");
  });

  it("submit disabled when VOD ID is empty", () => {
    cy.mount(<NewRunDialog onCreated={cy.spy()} />);
    cy.contains("New Run").click();
    cy.get("button[type=submit]").should("be.disabled");
  });

  it("calls onCreated on successful submission", () => {
    cy.stub(api.runs, "create").as("create").resolves(fakeRun);
    const onCreated = cy.spy().as("onCreated");
    cy.mount(<NewRunDialog onCreated={onCreated} />);
    cy.contains("New Run").click();
    cy.get("input").first().type("123456");
    cy.get("button[type=submit]").click();
    cy.get("@onCreated").should("have.been.calledOnce");
  });

  it("shows API error inside the dialog", () => {
    cy.stub(api.runs, "create").as("create").rejects(new Error("401: Unauthorized"));
    cy.mount(<NewRunDialog onCreated={cy.spy()} />);
    cy.contains("New Run").click();
    cy.get("input").first().type("123456");
    cy.get("button[type=submit]").click();
    cy.contains("401: Unauthorized").should("be.visible");
  });

  it("cancel closes dialog without calling create", () => {
    cy.stub(api.runs, "create").as("create");
    cy.mount(<NewRunDialog onCreated={cy.spy()} />);
    cy.contains("New Run").click();
    cy.contains("Cancel").click();
    cy.contains("VOD ID").should("not.exist");
    cy.get("@create").should("not.have.been.called");
  });
});
