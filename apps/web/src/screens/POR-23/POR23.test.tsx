// POR-23 · Component auditor room (A-09-T36). One test per artboard on its fixture scenario
// (a–f) and the 390 layout: "POR-23 a-f match their scenarios at Tier C, Accrued appears nowhere,
// and T7-M holds Tier D at 390 px." The live routes are A-09-T33's; parity runs in the end pass.
import { client } from "@abacus/api-client/client";
import { Toaster } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { POR23 } from ".";
import { COPY } from "./copy";
import { type Por23State, STATES, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Por23State, mobile = false): void {
  restore = installFixtureMode(scenarios[state]);
  renderRoutes([
    {
      path: "/",
      component: () => (
        <>
          <POR23 mobile={mobile} />
          <Toaster />
        </>
      ),
    },
  ]);
}

function avoid(): void {
  const text = document.body.textContent;
  expect(text).not.toMatch(/Accrued/);
  // Firm status words never reach the component auditor.
  for (const word of [/\bExpected\b/, /\bReceived\b/, /\bReviewed\b/, /\bLate\b/]) {
    expect(text).not.toMatch(word);
  }
}

describe("POR-23 artboards", () => {
  it("defines a to f, all Renee Pruett's", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f"]);
    for (const s of STATES) expect(scenarios[s].persona).toBe("renee-pruett");
  });

  it("a: invited, 0 of 4, the four deliverables and Acknowledge instructions", async () => {
    show("a");
    expect(await screen.findByText(COPY.progress(0, 4))).toBeTruthy();
    expect(screen.getByText("Planning confirmation")).toBeTruthy();
    expect(
      screen.getByText("Subsequent events update through the group report date"),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: COPY.acknowledge })).toBeTruthy();
    avoid();
  });

  it("b: acknowledged, the thread with times", async () => {
    show("b");
    expect(await screen.findByText(/You acknowledged/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: COPY.acknowledge })).toBeNull();
    expect(await screen.findByText(/Allocated from group PM 180,000/)).toBeTruthy();
    avoid();
  });

  it("c: the interim memo overdue, 1 of 4", async () => {
    show("c");
    expect(await screen.findByText(COPY.progress(1, 4))).toBeTruthy();
    const pill = document.querySelector('[data-pill="overdue"]');
    expect(pill?.textContent).toBe(COPY.pill.overdue);
    expect(await screen.findByText(/was due November 30/)).toBeTruthy();
    avoid();
  });

  it("d: uploaded, 2 of 4", async () => {
    show("d");
    expect(await screen.findByText(COPY.progress(2, 4))).toBeTruthy();
    avoid();
  });

  it("e: returned, not signed, with the note", async () => {
    show("e");
    const pill = await waitFor(() => {
      const found = document.querySelector('[data-pill="returned"]');
      expect(found).not.toBeNull();
      return found;
    });
    expect(pill?.textContent).toBe("Returned · not signed");
    expect(screen.getByText("Please upload the signed memo. — Omar Haddad")).toBeTruthy();
    avoid();
  });

  it("f: the invitation expired", async () => {
    show("f");
    expect(await screen.findByText(COPY.expired)).toBeTruthy();
    avoid();
  });

  it("opens the full letter with Download PDF", async () => {
    show("a");
    fireEvent.click(await screen.findByRole("button", { name: COPY.openLetter }));
    expect(await screen.findByText(COPY.downloadPdf)).toBeTruthy();
    expect(screen.getByText(/§4 Materiality\./)).toBeTruthy();
  });

  it("asks which deliverable when a drop is ambiguous", async () => {
    show("a");
    const input = await screen.findByLabelText(COPY.drop);
    fireEvent.change(input, { target: { files: [new File(["x"], "memo.pdf")] } });
    expect((await screen.findAllByText(COPY.whichDeliverable)).length).toBeGreaterThan(0);
  });

  it("390: the same room in the mobile layout", async () => {
    show("a", true);
    expect(await screen.findByText(COPY.progress(0, 4))).toBeTruthy();
    avoid();
  });
});
