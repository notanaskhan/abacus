// P-09-T09 (SHL-13 run pane; SPEC-648 Story 1.1; handoff frames 3, 4, 6 and 7): the projection by
// level, the six tool-card states, the decision card, the failed step and the completed run, from
// the E0 fixtures, and nothing here decides for a person.
import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import type { JSX } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { RUN_4127_DONE_ID, RUN_4127_FAILED_ID, SHL13_RUNS } from "../../fixtures/seed/agent-dock";
import { E0_RUNS, LEVELS_4127_941, RUN_4127_ID } from "../../fixtures/seed/agent-runs";
import { json, mockApi, renderRoutes } from "../../testing/support";
import { levelTail, projectionTitle, RunPane } from "./RunPane";

afterEach(cleanup);

/** The E0 and SHL-13 fixture runs as exact routes (the fixture handlers' shape, per run). */
function routes(): Parameters<typeof mockApi>[0] {
  const out: Parameters<typeof mockApi>[0] = {};
  for (const [id, run] of Object.entries({ ...E0_RUNS, ...SHL13_RUNS })) {
    const last = run.items.reduce((n, i) => Math.max(n, i.seq), 0);
    out[`GET /v1/agent-runs/${id}`] = () => json(run.view);
    out[`GET /v1/agent-runs/${id}/items`] = () =>
      json({ run: run.view.run, items: run.items, last_seq: last, next_seq: last, resync: false });
  }
  return out;
}

function renderPane(runId: string, extra: Partial<Parameters<typeof RunPane>[0]> = {}): void {
  mockApi(routes());
  const Page = (): JSX.Element => <RunPane runId={runId} onTrace={() => undefined} {...extra} />;
  renderRoutes([{ path: "/", component: Page }]);
}

describe("SHL-13 run pane", () => {
  it("words the projection: 14 workpapers across 5 levels, Planning 1 blocked · 1 running", () => {
    expect(projectionTitle(LEVELS_4127_941)).toBe("Run projection · 14 workpapers · 5 levels");
    expect(LEVELS_4127_941.map((lv) => lv.total)).toEqual([1, 5, 1, 4, 3]);
    const [, planning, sampling] = LEVELS_4127_941;
    expect(planning && levelTail(planning)).toBe("1 blocked · 1 running");
    expect(sampling && levelTail(sampling)).toBeNull();
  });

  it("frame 3: the live run at 9:41 with its projection and thread", async () => {
    renderPane(RUN_4127_ID);
    const strip = await screen.findByRole("region", { name: "Run projection" });
    expect(within(strip).getByText("1 of 1 ✓")).toBeTruthy();
    expect(within(strip).getByText("0 of 5")).toBeTruthy();
    expect(within(strip).getByText("1 blocked · 1 running")).toBeTruthy();
    expect(document.querySelector("[data-live-dot]")).not.toBeNull();
    // Sign off run is a person's, and only once the run ends.
    expect(screen.getByRole("button", { name: "Sign off run" }).hasAttribute("disabled")).toBe(
      true,
    );
    expect(await screen.findByText("yes, run it")).toBeTruthy();
    const states = [...document.querySelectorAll("[data-tool-card]")].map((n) =>
      n.getAttribute("data-tool-card"),
    );
    expect(states).toEqual([
      "succeeded",
      "succeeded",
      "blocked",
      "running",
      "waiting_on_inputs",
      "waiting_on_inputs",
    ]);
    // Service Organizations & SOC 1 is queued: in the projection, no tool card.
    expect(screen.queryByText(/Service Organizations/)).toBeNull();
    expect(screen.getByText("Holding…")).toBeTruthy();
    expect(screen.getByText("Opt-out elections — 4 auto-enrolled participants")).toBeTruthy();
  });

  it("expands a finished tool card to what it read and wrote, with Open trace", async () => {
    renderPane(RUN_4127_ID);
    const card = (await screen.findByText("Run trial balance workpaper")).closest(
      "li",
    ) as HTMLElement;
    const toggle = within(card).getByRole("button", { expanded: false });
    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(within(card).getByText("14 cells · 3 citations")).toBeTruthy();
    expect(within(card).getByRole("button", { name: "Open trace" })).toBeTruthy();
  });

  it("frame 4: the blocked card opens the partner's decision, it never decides", async () => {
    const opened: string[] = [];
    renderPane(RUN_4127_ID, { onOpenDecision: (ref) => opened.push(ref) });
    fireEvent.click(await screen.findByRole("button", { name: "Open decision" }));
    expect(opened).toHaveLength(1);
    // The run thread is the agent's output; the composer's Send below it is the person's own.
    const thread = screen.getByRole("list", { name: "Run thread" });
    for (const word of ["Approve", "Decide", "Release", "Post", "Send"]) {
      expect(within(thread).queryByRole("button", { name: new RegExp(`^${word}`) })).toBeNull();
    }
  });

  it("frame 6: the failed step shows the pack-configuration error and a person's Retry", async () => {
    renderPane(RUN_4127_FAILED_ID);
    expect(
      await screen.findByText(/BH-EBP-140 step 8 points to a SOC 1 bridge-letter/),
    ).toBeTruthy();
    const failed = document.querySelector("[data-tool-card='failed']") as HTMLElement;
    expect(within(failed).getByRole("button", { name: "Retry" })).toBeTruthy();
  });

  it("frame 7: a completed run enables Sign off run for a person who holds it", async () => {
    renderPane(RUN_4127_DONE_ID);
    expect(await screen.findByText(/14 of 14 workpapers drafted/)).toBeTruthy();
    const sign = await screen.findByRole("button", { name: "Sign off run" });
    await screen.findAllByText("1 of 1 ✓");
    expect(sign.hasAttribute("disabled")).toBe(false);
    expect(document.querySelector("[data-live-dot]")).toBeNull();
  });

  it("a run the viewer may not read shows the not-allowed state", async () => {
    renderPane("not-a-run");
    expect(await screen.findByText("You can't open this run.")).toBeTruthy();
  });
});
