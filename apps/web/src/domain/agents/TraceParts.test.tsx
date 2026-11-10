// P-09-T10 (WB-09 run trace drawer; SPEC-648 Stories 4.1 to 4.3; handoff WB-09 a to e): the summary
// card, the timeline marks and the a2 expansion, the records table with its total, the waiting
// write, the metadata-only note, the not-allowed state and the 200 ms skeleton.
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import type { JSX } from "react";
import { afterEach, describe, expect, it } from "vitest";
import {
  E0_RUNS,
  LIST_RETURNS_SAMPLES,
  LIST_RETURNS_STEP_ID,
  RUN_4118_ID,
  RUN_4127_ID,
} from "../../fixtures/seed/agent-runs";
import { json, mockApi, renderRoutes } from "../../testing/support";
import { TraceDrawer } from "./TraceDrawer";
import { traceDuration } from "./TraceParts";

afterEach(cleanup);

function routes(): Parameters<typeof mockApi>[0] {
  const out: Parameters<typeof mockApi>[0] = {};
  for (const [id, run] of Object.entries(E0_RUNS)) {
    const last = run.items.reduce((n, i) => Math.max(n, i.seq), 0);
    out[`GET /v1/agent-runs/${id}/trace`] = () => json(run.trace);
    out[`GET /v1/agent-runs/${id}/trace/writes`] = () => json(run.writes);
    out[`GET /v1/agent-runs/${id}/items`] = () =>
      json({ run: run.view.run, items: run.items, last_seq: last, next_seq: last, resync: false });
  }
  out[`GET /v1/agent-runs/${RUN_4118_ID}/trace/steps/${LIST_RETURNS_STEP_ID}`] = () =>
    json({
      step_id: LIST_RETURNS_STEP_ID,
      title: "Execute › list returns",
      args_summary: "tax year 2025",
      records_read: 224,
      samples: LIST_RETURNS_SAMPLES,
    });
  out["GET /v1/agent-runs/walled/trace"] = () => json({ detail: "not_found" }, 404);
  out["GET /v1/agent-runs/walled/items"] = () => json({ detail: "not_found" }, 404);
  return out;
}

function open(runId: string): void {
  mockApi(routes());
  const Page = (): JSX.Element => <TraceDrawer runId={runId} onClose={() => undefined} />;
  renderRoutes([{ path: "/", component: Page }]);
}

describe("WB-09 run trace drawer", () => {
  it("words durations as the handoff does", () => {
    expect(traceDuration(161_000, false)).toBe("2 m 41 s");
    expect(traceDuration(17 * 60_000, true)).toBe("17 m so far");
    expect(traceDuration(1_900, false)).toBe("1.9 s");
  });

  it("a: #4118's summary card, timeline and its waiting write", async () => {
    open(RUN_4118_ID);
    const summary = await screen.findByText("Run #4118");
    const card = summary.closest("[data-trace-summary]") as HTMLElement;
    expect(within(card).getByText("2,625")).toBeTruthy();
    expect(within(card).getByText("79")).toBeTruthy();
    expect(within(card).getByText("0 done · 1 waiting")).toBeTruthy();
    expect(within(card).getByText("Accrued Agent runtime")).toBeTruthy();
    expect(document.querySelectorAll("[data-trace-row]").length).toBeGreaterThan(5);
    fireEvent.click(screen.getByRole("tab", { name: "Writes & approvals" }));
    expect(await screen.findByText("Waiting on Hannah Leclerc")).toBeTruthy();
    // P-09-T10 remainder (DEC-3143): the waiting proposal opens SHL-10 for a person.
    const approve = screen.getByRole("button", { name: "Approve…" });
    expect(approve.hasAttribute("disabled")).toBe(false);
    expect(approve.closest("li")?.textContent).toContain("save_file");
  });

  it("a2: a tool row expands to its arguments through the step route", async () => {
    open(RUN_4118_ID);
    const row = await screen.findByRole("button", { name: "Execute › list returns" });
    fireEvent.click(row);
    expect(row.getAttribute("aria-expanded")).toBe("true");
    expect(await screen.findByText("tax year 2025")).toBeTruthy();
    // P-09-T10 remainder: the first five returns read, each linking to its return.
    const read = screen.getByRole("list", { name: "First records read" });
    const links = within(read).getAllByRole("link");
    expect(links).toHaveLength(5);
    expect(links[0]?.getAttribute("href")).toBe(
      `/tax-returns/${LIST_RETURNS_SAMPLES[0]?.id ?? ""}`,
    );
    expect(links[0]?.textContent).toBe("Amber & Birchwood Ceramics, LP · 1065");
  });

  it("a3: records read by source, through, with the total", async () => {
    open(RUN_4118_ID);
    await screen.findByText("Run #4118");
    fireEvent.click(screen.getByRole("tab", { name: "Records read" }));
    const table = screen.getByRole("table", { name: "Records read" });
    expect(within(table).getByText("Total")).toBeTruthy();
    expect(within(table).getAllByText("2,625").length).toBe(1);
  });

  it("b: #4127 is running, 17 m so far", async () => {
    open(RUN_4127_ID);
    expect(await screen.findByText("Run #4127")).toBeTruthy();
    expect(screen.getByText(/17 m so far/)).toBeTruthy();
  });

  it("the not-allowed state for a run the viewer can't see (INV-3)", async () => {
    open("walled");
    expect(await screen.findByText("You can't open this trace")).toBeTruthy();
  });

  it("e: skeleton rows while loading", async () => {
    open(RUN_4118_ID);
    // The router paints after it resolves the route; the skeleton then holds for 200 ms.
    await waitFor(() => {
      expect(document.querySelector("[data-trace-loading]")).not.toBeNull();
    });
  });
});
