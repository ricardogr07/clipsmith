import { ProgressStream } from "../../components/ProgressStream";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;

  constructor(public url: string) {
    FakeEventSource.instances.push(this);
  }

  close() {}

  push(data: object) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }

  error() {
    this.onerror?.(new Event("error"));
  }
}

function factory(url: string): EventSource {
  return new FakeEventSource(url) as unknown as EventSource;
}

describe("ProgressStream", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
  });

  it("shows initial state: 'starting' stage at 0%", () => {
    cy.mount(<ProgressStream runId={1} eventSourceFactory={factory} />);
    cy.contains("starting").should("be.visible");
    cy.contains("0%").should("be.visible");
  });

  it("updates stage and pct on an SSE event", () => {
    cy.mount(<ProgressStream runId={1} eventSourceFactory={factory} />);
    cy.contains("starting").should("be.visible");
    cy.then(() => {
      FakeEventSource.instances[0].push({ stage: "transcribe", pct: 40 });
    });
    cy.contains("transcribe").should("be.visible");
    cy.contains("40%").should("be.visible");
  });

  it("advances through multiple events to the last value", () => {
    cy.mount(<ProgressStream runId={1} eventSourceFactory={factory} />);
    cy.contains("starting").should("be.visible");
    cy.then(() => {
      FakeEventSource.instances[0].push({ stage: "transcribe", pct: 20 });
      FakeEventSource.instances[0].push({ stage: "clip", pct: 60 });
      FakeEventSource.instances[0].push({ stage: "export", pct: 90 });
    });
    cy.contains("export").should("be.visible");
    cy.contains("90%").should("be.visible");
  });

  it("shows 'Pipeline complete' on end event with status done", () => {
    const onDone = cy.spy().as("onDone");
    cy.mount(<ProgressStream runId={1} onDone={onDone} eventSourceFactory={factory} />);
    cy.contains("starting").should("be.visible");
    cy.then(() => {
      FakeEventSource.instances[0].push({ event: "end", status: "done" });
    });
    cy.contains("Pipeline complete").should("be.visible");
    cy.get("@onDone").should("have.been.calledOnce");
  });

  it("shows error text on end event with status failed", () => {
    cy.mount(<ProgressStream runId={1} eventSourceFactory={factory} />);
    cy.contains("starting").should("be.visible");
    cy.then(() => {
      FakeEventSource.instances[0].push({ event: "end", status: "failed", error: "oom" });
    });
    cy.contains("oom").should("be.visible");
  });

  it("shows 'Stream disconnected' when onerror fires", () => {
    cy.mount(<ProgressStream runId={1} eventSourceFactory={factory} />);
    cy.contains("starting").should("be.visible");
    cy.then(() => {
      FakeEventSource.instances[0].error();
    });
    cy.contains("Stream disconnected").should("be.visible");
  });
});
