// P-09-T09 (SHL-13 run pane; SPEC-648 Story 1.1; handoff frames 3, 4, 6 and 7): the projection by
// level, the six tool-card states, the decision card, the failed step and the completed run, from
// the E0 fixtures, and nothing here decides for a person.
import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import type { JSX } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { ClockProvider } from "@abacus/ui";
import {
  PERSON_RUN_ACTIONS,
  RUN_4127_ASK_ID,
  RUN_4127_DONE_ID,
  RUN_4127_FAILED_ID,
  RUN_4127_IDLE_ID,
  RUN_4127_PLAN_ID,
  RUN_CLOSE_COPPERLEAF_ID,
  SHL13_RUNS,
} from "../../fixtures/seed/agent-dock";
import { DEMO_MS } from "../../fixtures/seed/clock";
import { E0_RUNS, LEVELS_4127_941, RUN_4127_ID } from "../../fixtures/seed/agent-runs";
import { json, mockApi, renderRoutes } from "../../testing/support";
import { dockAgents } from "./AgentDock";
import { levelTail, projectionTitle, RunPane, sourceOf } from "./RunPane";

afterEach(cleanup);

/** P-09-T14: `agent_runtime.v2` on (or off) for the firm, through `/v1/me/capabilities`. */
function capabilities(v2: boolean): object {
  return {
    capabilities: [],
    clock_mode: "offset",
    engagement_id: null,
    entitlements: [],
    flags: { "agent_runtime.v2": v2 },
    mfa_recent_until: null,
    office_id: null,
    portal: null,
    roles: [],
    server_now: "2026-09-14T14:41:00Z",
    tz: "America/Chicago",
  };
}

/** The E0 and SHL-13 fixture runs as exact routes (the fixture handlers' shape, per run). Run
 * #4127 at 9:41 is read as Marcus Delaney, who holds every human action (P-09-T14). */
function routes(v2 = true): Parameters<typeof mockApi>[0] {
  const out: Parameters<typeof mockApi>[0] = {
    "GET /v1/me/capabilities": () => json(capabilities(v2)),
  };
  for (const [id, run] of Object.entries({ ...E0_RUNS, ...SHL13_RUNS })) {
    const last = run.items.reduce((n, i) => Math.max(n, i.seq), 0);
    const view =
      id === RUN_4127_ID ? { ...run.view, allowed_actions: PERSON_RUN_ACTIONS } : run.view;
    out[`GET /v1/agent-runs/${id}`] = () => json(view);
    out[`GET /v1/agent-runs/${id}/items`] = () =>
      json({ run: run.view.run, items: run.items, last_seq: last, next_seq: last, resync: false });
  }
  return out;
}

function renderPane(
  runId: string,
  extra: Partial<Parameters<typeof RunPane>[0]> = {},
  v2 = true,
): void {
  mockApi(routes(v2));
  const Page = (): JSX.Element => (
    <ClockProvider now={() => DEMO_MS}>
      <RunPane runId={runId} onTrace={() => undefined} {...extra} />
    </ClockProvider>
  );
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
    expect(
      (await screen.findByRole("button", { name: "Sign off run" })).hasAttribute("disabled"),
    ).toBe(true);
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

  it("frame 1: idle, the engagement agent is ready and only a person starts it", async () => {
    renderPane(RUN_4127_IDLE_ID, { engagementId: "00000000-0000-4000-8000-000000000001" });
    expect(await screen.findByText("Ready to run 14 workpapers across 5 levels")).toBeTruthy();
    expect(
      screen.getByText("Auto mode is off — I'll propose the plan and wait for your go-ahead."),
    ).toBeTruthy();
    // P-09-T14: the server lists agent_run.start for Marcus, so Run is his to press.
    const run = await screen.findByRole("button", { name: "Run" });
    expect(run.hasAttribute("disabled")).toBe(false);
    expect(screen.queryByRole("button", { name: "Sign off run" })).toBeNull();
    expect(screen.getAllByText(/^0 of /)).toHaveLength(5);
  });

  it("frame 2: the plan is proposed and waits; the go-ahead chips are the person's", async () => {
    renderPane(RUN_4127_PLAN_ID);
    expect(await screen.findByText("Run planning for Northwind.")).toBeTruthy();
    expect(await screen.findByText("Plan ready — approve?")).toBeTruthy();
    expect(
      (await screen.findByRole("button", { name: "yes, run it" })).hasAttribute("disabled"),
    ).toBe(false);
    expect(screen.getByRole("button", { name: "Change order…" })).toBeTruthy();
  });

  it("frame 5: the Sampling question with its recommended option, answered by a person", async () => {
    renderPane(RUN_4127_ASK_ID);
    const card = (
      await screen.findByText("Which population should eligibility testing start from?")
    ).closest("li") as HTMLElement;
    expect(within(card).getByText(/PayGrid payroll census/)).toBeTruthy();
    expect(within(card).getByText(/Recommended/)).toBeTruthy();
    expect(within(card).getByText(/Keystone participant file/)).toBeTruthy();
    expect(within(card).getByText("1 of 1")).toBeTruthy();
    // P-09-T14: Skip is live; Next waits for an answer.
    expect(
      (await within(card).findByRole("button", { name: "Skip" })).hasAttribute("disabled"),
    ).toBe(false);
    expect(within(card).getByRole("button", { name: "Next" }).hasAttribute("disabled")).toBe(true);
  });

  it("frame 8: Copperleaf's close run counts 6 of 9 with 3 running", async () => {
    renderPane(RUN_CLOSE_COPPERLEAF_ID);
    expect(await screen.findByText("Closing agent is running")).toBeTruthy();
    expect(screen.getByText("3 tasks running at once")).toBeTruthy();
    expect(screen.getByText("6 of 9 complete")).toBeTruthy();
    expect(screen.getByText("Started 18 minutes ago")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Run 2/ })).toBeTruthy();
    expect(await screen.findAllByText(/./, { selector: "[data-task-row] span" })).toHaveLength(9);
    expect(document.querySelectorAll("[data-task-row='succeeded']")).toHaveLength(6);
    expect(
      screen.getByText("Tie Square payouts (gross $73,166.90 − fees $1,684.54 = net $71,482.36)"),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Sign off run" })).toBeNull();
  });

  it("revision 1: the agents strip lists each agent once, with the open run's source", async () => {
    const agents = dockAgents(
      [SHL13_RUNS[RUN_4127_DONE_ID]?.view.run, SHL13_RUNS[RUN_4127_FAILED_ID]?.view.run].filter(
        (r) => r !== undefined,
      ),
    );
    expect(agents).toHaveLength(1);
    expect(sourceOf("agent_column")).toBe("Agent column");
    expect(sourceOf("event_policy")).toBe("Trigger");
    expect(sourceOf(null)).toBe("Manual");
    renderPane(RUN_4127_ID, { agents });
    const strip = await screen.findByRole("button", { name: "Agents on this engagement · 1" });
    expect(strip.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(strip);
    expect(screen.getByText("Manual")).toBeTruthy();
  });

  it("revision 4: thumbs-down needs a reason before Submit", async () => {
    renderPane(RUN_4127_ID);
    const card = (await screen.findByText("Run trial balance workpaper")).closest(
      "li",
    ) as HTMLElement;
    fireEvent.click(within(card).getByRole("button", { expanded: false }));
    fireEvent.click(await within(card).findByRole("button", { name: "Not helpful" }));
    const picker = within(card).getByRole("dialog", { name: "What was wrong" });
    const submit = within(picker).getByRole("button", { name: "Submit" });
    expect(submit.hasAttribute("disabled")).toBe(true);
    fireEvent.click(within(picker).getByLabelText("Wrong document"));
    expect(submit.hasAttribute("disabled")).toBe(false);
  });

  it("P-09-T14: with agent_runtime.v2 off no human action is offered", async () => {
    renderPane(RUN_4127_ID, {}, false);
    await screen.findByRole("region", { name: "Run projection" });
    for (const name of ["Sign off run", "yes, run it", "Retry", "Not helpful"]) {
      expect(screen.queryByRole("button", { name })).toBeNull();
    }
    expect(screen.getByLabelText<HTMLInputElement>("Message").disabled).toBe(true);
  });

  it("P-09-T14: a run the server lists no action on offers none", async () => {
    renderPane(RUN_CLOSE_COPPERLEAF_ID);
    await screen.findByText("Closing agent is running");
    expect(screen.queryByRole("button", { name: "Sign off run" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Skip" })).toBeNull();
  });

  it("P-09-T14: Sign off run lists the open issues and decisions before it is sent", async () => {
    renderPane(RUN_4127_DONE_ID);
    fireEvent.click(await screen.findByRole("button", { name: "Sign off run" }));
    expect(await screen.findByRole("alertdialog")).toBeTruthy();
  });
});
