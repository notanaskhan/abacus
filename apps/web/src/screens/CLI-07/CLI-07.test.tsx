// CLI-07 · Acceptance & continuance (P-07-T46). One test per artboard a–g on its fixture scenario,
// the revision's acceptance bullets, the writes (a manual check completed and sent, a decision with
// conditions, the MFA step-up, a condition completed, the risk-partner review), loading, error, the
// walled 404, and the task's acceptance: "Scenarios a to g pass with axe and only the engagement
// partner sees an enabled Decide control" (axe: e2e/screens/CLI-07.spec.ts, Playwright).
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
  never,
} from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { CLI07, type Cli07Target } from ".";
import {
  type Cli07Options,
  type Cli07State,
  NOTES,
  OPENS,
  STATES,
  freshScenario,
  scenarios,
} from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  // `clear` keeps a toast 180 ms while it leaves; `reset` drops it, so none reaches the next test.
  toastStore.reset();
});

interface Call {
  method: string;
  path: string;
  body: unknown;
}

function install(scenario: Scenario, over: Record<string, FixtureHandler>): Call[] {
  const calls: Call[] = [];
  const handlers = Object.fromEntries(
    Object.entries({ ...scenario.handlers, ...over }).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  return calls;
}

function show(
  state: Cli07State,
  options: Cli07Options & {
    over?: Record<string, FixtureHandler>;
    onNavigate?: (t: Cli07Target) => void;
  } = {},
): Call[] {
  const { over = {}, onNavigate, ...scenario } = options;
  const calls = install(freshScenario(state, scenario), over);
  const opens = OPENS[state];
  renderRoutes([
    {
      path: "/",
      component: () => (
        <CLI07
          clientId={opens.clientId}
          engagementId={opens.engagementId}
          note={NOTES[state]}
          {...(onNavigate === undefined ? {} : { onNavigate })}
        />
      ),
    },
  ]);
  return calls;
}

function dock(): HTMLElement {
  const el = document.querySelector<HTMLElement>("[data-cockpit='dock']");
  if (el === null) throw new Error("no dock");
  return el;
}

function canvas(): HTMLElement {
  const el = document.querySelector<HTMLElement>("[data-cockpit='canvas']");
  if (el === null) throw new Error("no canvas");
  return el;
}

function riskSummary(): string {
  return document.querySelector("[data-risk-summary]")?.textContent ?? "";
}

function railLines(): string[] {
  return [...document.querySelectorAll("[data-rail-row='phase']")].map((r) =>
    r.textContent.replace("···", "").trim(),
  );
}

function primary(): HTMLButtonElement {
  const el = document.querySelector<HTMLButtonElement>("[data-dock-footer] button");
  if (el === null) throw new Error("no dock action");
  return el;
}

async function ready(text: string): Promise<void> {
  expect((await screen.findAllByText(text, {}, { timeout: 3000 })).length).toBeGreaterThan(0);
}

describe("CLI-07 artboards", () => {
  it("defines a–g with the contract's viewers and clocks", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f", "g"]);
    const viewer = (s: Cli07State) => scenarios[s].persona;
    expect(["a", "c", "d", "e"].map((s) => viewer(s as Cli07State))).toEqual([
      "daniel-reyes",
      "daniel-reyes",
      "daniel-reyes",
      "daniel-reyes",
    ]);
    expect(viewer("b")).toBe("samuel-ito");
    expect(viewer("f")).toBe("margaret-okonkwo");
    expect(viewer("g")).toBe("margaret-okonkwo");
    expect(scenarios.a.clock).toBe("2026-09-14T09:40:00-05:00");
    expect(scenarios.b.clock).toBe("2026-09-11T16:10:00-05:00");
    expect(scenarios.c.clock).toBe("2026-09-11T16:01:00-05:00");
    expect(scenarios.d.clock).toBe("2026-09-14T09:46:00-05:00");
    expect(scenarios.g.clock).toBe("2026-10-01T10:40:00-05:00");
  });

  it("CLI-07a default: Thornbury awaiting Daniel Reyes, three human flags, Moderate", async () => {
    show("a");
    await ready("Form 706 is required");
    expect(screen.getByText("Executor authority is not yet evidenced")).toBeTruthy();
    expect(
      screen.getByText("Client identification — the estate, not the beneficiaries"),
    ).toBeTruthy();
    expect(screen.getByText("Acceptance — Form 706 & estate Form 1041")).toBeTruthy();
    expect(document.querySelector("[data-meta='prepared']")?.textContent).toBe(
      "Prepared by Samuel Ito · Sep 11",
    );
    expect(screen.getByText("Questionnaire · Tax engagements v2")).toBeTruthy();
    expect(riskSummary()).toBe(
      "5 sections clear (1 by manual check) · 3 flags · conclusion awaiting partner · risk-partner review not required at Moderate",
    );
    expect(railLines()).toContain("Authority & documents1 flag · letters of office missing");
    expect(railLines()).toContain("ConclusionAwaiting partner");
    expect(screen.getByText("Blocked on a partner decision")).toBeTruthy();
    expect(
      within(dock()).getByText("Accept the Estate of Walter Thornbury engagement?"),
    ).toBeTruthy();
    expect(primary().textContent).toContain("Decide");
    expect(primary().disabled).toBe(false);
    expect(
      within(dock()).getByText(
        "Reserved to Daniel Reyes · Engagement partner. The decision date must precede the engagement letter (G1).",
      ),
    ).toBeTruthy();
    // Production flags are human-prepared: no agent recommendation or pre-screen meta (DEC-64).
    expect(screen.queryByText("Agent recommendation")).toBeNull();
    expect(screen.queryByText(/Pre-screened by Accrued Agent/)).toBeNull();
    expect(screen.getAllByRole("button", { name: /Make this a condition/ })).toHaveLength(3);
  });

  it("CLI-07b draft: Grace Holloway's fee check is open and Send to partner waits for it", async () => {
    show("b");
    await ready("Manual check open · Fees & collectability");
    expect(within(dock()).getByText("Not ready for decision — 1 manual check open")).toBeTruthy();
    expect(primary().textContent).toBe("Send to partner");
    expect(primary().disabled).toBe(true);
    expect(screen.getByText("Asked of Grace Holloway · Sep 11")).toBeTruthy();
    expect(screen.getAllByText("Daniel Reyes can make this a condition")).toHaveLength(3);
    expect(riskSummary()).toContain("4 sections clear · 3 flags · 1 manual check open");
    expect(railLines()).toContain(
      "Fees & collectabilityManual check · estate not yet in CCH Axcess Practice",
    );
    expect(screen.getByText("Draft")).toBeTruthy();
  });

  it("CLI-07b manual check: Grace completes it, then Samuel sends to the partner", async () => {
    const calls = show("b", { persona: "grace-holloway" });
    fireEvent.click(await screen.findByRole("button", { name: "Complete check…" }));
    fireEvent.click(await screen.findByRole("button", { name: "Mark check done" }));
    await waitFor(() => {
      expect(screen.queryByText("Manual check open · Fees & collectability")).toBeNull();
    });
    expect(
      calls.some((c) => c.method === "POST" && c.path.endsWith("/manual-checks/fees/complete")),
    ).toBe(true);
    await waitFor(() => {
      expect(primary().disabled).toBe(false);
    });
    fireEvent.click(primary());
    await ready("Blocked on a partner decision");
    const send = calls.find((c) => c.path.endsWith("/send-to-partner"));
    expect(send?.body).toEqual({ seen_version: 13 });
  });

  it("CLI-07c pre-screen running (fixture only): 4 of 9 sections", async () => {
    show("c");
    await ready("Accrued Agent is screening · 4 of 9 sections");
    expect(screen.queryByText("Form 706 is required")).toBeNull();
    expect(
      [...document.querySelectorAll("[data-rail-row='phase']")].filter(
        (r) => r.getAttribute("data-disc") === "run",
      ),
    ).toHaveLength(5);
    expect(
      within(dock()).getByText("Not ready for decision — questionnaire in progress"),
    ).toBeTruthy();
  });

  it("CLI-07d decided and locked: accepted with conditions, three open conditions for Samuel Ito", async () => {
    const calls = show("d");
    await ready("Accepted with conditions");
    const decided = document.querySelector("[data-dock-decided]");
    expect(decided?.textContent).toContain("Accepted with conditions");
    expect(decided?.textContent).toContain("Daniel Reyes · Sep 14, 9:46 AM");
    expect(screen.getByRole("img", { name: "Locked" })).toBeTruthy();
    expect(screen.queryByRole("radiogroup")).toBeNull();
    expect(
      document.querySelector("[data-option='accept_with_conditions'][data-chosen]"),
    ).not.toBeNull();
    expect(screen.getByText("0 of 3 done")).toBeTruthy();
    expect(screen.getAllByText("Owner Samuel Ito · Open")).toHaveLength(3);
    expect(screen.getAllByText("Accepted").length).toBeGreaterThan(0);
    expect(primary().textContent).toBe("Draft engagement letter →");
    expect(primary().disabled).toBe(true);
    expect(
      screen.getByText(
        "Decision recorded Sep 14, 9:46 AM · it can't be edited. The engagement letter follows it (G1).",
      ),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Make this a condition/ })).toBeNull();
    expect(railLines()).toContain("ConclusionAccepted with conditions · DR");
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: "Mark done: Letters of office on file before the letter is signed.",
      }),
    );
    await ready("1 of 3 done");
    expect(
      calls.some((c) => c.path.includes("/conditions/") && c.path.endsWith("/complete")),
    ).toBe(true);
  });

  it("CLI-07e declined: the reasons, no letter, and Open Estate of Walter Thornbury", async () => {
    const onNavigate = vi.fn();
    show("e", { onNavigate });
    await ready("Open Estate of Walter Thornbury");
    expect(document.querySelector("[data-dock-decided]")?.textContent).toContain("Declined");
    expect(screen.getByText("Reasons")).toBeTruthy();
    expect(
      screen.getByText(
        "We can't confirm the executor's authority until the letters of office issue.",
      ),
    ).toBeTruthy();
    expect(
      screen.getByText(
        "Decision recorded Sep 14, 9:40 AM · it can't be edited. No engagement letter will be drafted.",
      ),
    ).toBeTruthy();
    expect(screen.queryByText("Draft engagement letter →")).toBeNull();
    fireEvent.click(primary());
    expect(onNavigate).toHaveBeenCalledWith({ screen: "CLI-02", clientId: OPENS.e.clientId });
  });

  it("CLI-07f continuance: Meridian Tool & Die FY2026, Low, the prior-year flag and CLI-08", async () => {
    show("f");
    await ready("Prior-year history — one open item");
    expect(screen.getByText("Continuance — FY2026 FS audit")).toBeTruthy();
    expect(
      within(dock()).getByText("Continue the Meridian Tool & Die, Inc. engagement for FY2026?"),
    ).toBeTruthy();
    for (const label of ["Continue", "Continue with conditions", "Discontinue"]) {
      expect(within(dock()).getByRole("radio", { name: label })).toBeTruthy();
    }
    expect(riskSummary()).toBe(
      "7 sections clear · 1 flag · conclusion awaiting partner · risk-partner review not required at Low",
    );
    expect(screen.getByText(/IL DOR notice of tax due IL-1120 \$5,880/)).toBeTruthy();
    const nas = screen.getByRole("button", { name: "see Independence (CLI-08) →" });
    expect(nas.getAttribute("title")).toBe(
      "Opens CLI-08 · Independence · Meridian Tool & Die, Inc.",
    );
    expect(primary().textContent).toContain("Decide");
    expect(primary().disabled).toBe(false);
  });

  it("CLI-07g continuance draft (fixture until I-03): the responsiveness flag, not ready", async () => {
    show("g");
    await ready("Client responsiveness is below the firm rate");
    expect(screen.getByText("Continuance — FY2027 FS audit")).toBeTruthy();
    expect(railLines()).toContain("Client responsiveness1 flag · on-time rate 48% (firm 63%)");
  });
});

describe("CLI-07 acceptance (R2)", () => {
  it("frame g shows the flag 'On-time rate 48% (firm 63%)' with two cited sources", async () => {
    show("g");
    await ready("Client responsiveness is below the firm rate");
    expect(screen.getByText(/completed 48% of requests .* against 63% for the firm/)).toBeTruthy();
    const card = screen.getByRole("region", {
      name: "Client responsiveness is below the firm rate",
    });
    expect(card.querySelectorAll("[data-source]")).toHaveLength(2);
  });

  it("the decision stays with the engagement partner; the dock is not ready for decision on Oct 1", async () => {
    show("g");
    await ready("Not ready for decision — questionnaire in progress");
    expect(screen.queryByRole("button", { name: /Decide/ })).toBeNull();
    expect(primary().textContent).toBe("Send to partner");
    expect(primary().disabled).toBe(true);
    expect(
      within(dock()).getByText(/Reserved to Margaret Okonkwo · Engagement partner/),
    ).toBeTruthy();
  });

  it("the note names Luis Ferrante (Granite Peak's CFO) and no new people", async () => {
    show("g");
    const note = await screen.findByRole("textbox", { name: "Continuance note" });
    expect((note as HTMLTextAreaElement).value).toBe(
      "Agree PBC dates and a named contact with Luis Ferrante before the FY2027 letter.",
    );
  });

  it("frames a–f keep the Thornbury decision and the Meridian continuance", async () => {
    show("d");
    await ready("Accepted with conditions");
    expect(
      screen.getByText("Letters of office on file before the letter is signed."),
    ).toBeTruthy();
  });

  it("the decision date is before any letter date (G1 < letter): the letter waits on the decision", async () => {
    show("a");
    await ready("Form 706 is required");
    expect(screen.queryByText("Draft engagement letter →")).toBeNull();
  });
});

describe("CLI-07 decision", () => {
  it("only the engagement partner sees an enabled Decide; everyone else sees Partner decision", async () => {
    show("a");
    await ready("Form 706 is required");
    expect(primary().textContent).toContain("Decide");
    expect(primary().disabled).toBe(false);
    expect(
      within(dock())
        .getAllByRole("radio")
        .every((r) => !(r as HTMLButtonElement).disabled),
    ).toBe(true);
    cleanup();
    restore?.();
    for (const persona of ["samuel-ito", "grace-holloway"]) {
      show("a", { persona });
      await ready("Form 706 is required");
      expect(primary().textContent).toBe("Partner decision");
      expect(primary().disabled).toBe(true);
      expect(screen.queryByRole("button", { name: "Decide" })).toBeNull();
      expect(
        within(dock())
          .getAllByRole("radio")
          .every((r) => (r as HTMLButtonElement).disabled),
      ).toBe(true);
      cleanup();
      restore?.();
    }
  });

  it("asks for an option and a rationale, turns a flag into a condition, then records it", async () => {
    const calls = show("a");
    await ready("Form 706 is required");
    fireEvent.click(primary());
    expect(await screen.findByText("Choose an option.")).toBeTruthy();
    const make = screen.getAllByRole("button", { name: /Make this a condition/ })[0];
    if (make === undefined) throw new Error("no make-condition link");
    fireEvent.click(make);
    expect(screen.getByRole<HTMLInputElement>("textbox", { name: "Condition 1" }).value).toBe(
      "Form 706 is required",
    );
    fireEvent.click(primary());
    expect(await screen.findByText("A rationale is required.")).toBeTruthy();
    fireEvent.change(screen.getByRole("textbox", { name: "Rationale" }), {
      target: { value: "Every flag can be resolved by a condition." },
    });
    fireEvent.click(primary());
    await waitFor(() => {
      expect(toastStore.list()[0]?.text).toBe("Decision recorded");
    });
    const decide = calls.find((c) => c.path.endsWith("/acceptance/decision"));
    expect(decide?.body).toMatchObject({
      option: "accept_with_conditions",
      rationale: "Every flag can be resolved by a condition.",
      seen_version: 14,
      conditions: [{ text: "Form 706 is required" }],
    });
    await waitFor(() => {
      expect(document.querySelector("[data-dock-decided]")?.textContent).toContain(
        "Accepted with conditions",
      );
    });
  });

  it("a stale MFA opens the step-up instead of recording", async () => {
    show("a", { staleMfa: true });
    await ready("Form 706 is required");
    fireEvent.click(within(dock()).getByRole("radio", { name: "Accept" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Rationale" }), {
      target: { value: "Low risk once letters issue." },
    });
    fireEvent.click(primary());
    expect(await screen.findByText("Confirm it's you")).toBeTruthy();
    expect(toastStore.list().map((t) => t.text)).not.toContain("Decision recorded");
    expect(document.querySelector("[data-dock-decided]")).toBeNull();
  });

  it("requests a risk-partner review from the partners the picker offers", async () => {
    const calls = show("a");
    fireEvent.click(await screen.findByRole("button", { name: "Request risk-partner review…" }));
    const dialog = await screen.findByRole("dialog");
    const picker = await within(dialog).findByRole("button", { name: "Partner: Partner" });
    picker.focus();
    fireEvent.keyDown(picker, { key: "ArrowDown" });
    fireEvent.click(await screen.findByRole("menuitemradio", { name: /Margaret Okonkwo/ }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Request review" }));
    await waitFor(() => {
      expect(riskSummary()).toContain("risk-partner review requested of Margaret Okonkwo");
    });
    expect(calls.some((c) => c.path.endsWith("/risk-partner-review"))).toBe(true);
  });
});

describe("CLI-07 states", () => {
  it("loading: nothing from the record shows", async () => {
    show("a", { over: { "GET /v1/engagements/{engagement_id}/acceptance": () => never() } });
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText("Form 706 is required")).toBeNull();
    expect(document.querySelector("[data-cockpit='dock']")).toBeNull();
  });

  it("error: a 5xx offers Retry", async () => {
    show("a", {
      over: {
        "GET /v1/engagements/{engagement_id}/acceptance": () => json({ detail: "boom" }, 500),
      },
    });
    expect(await screen.findByRole("button", { name: "Retry" })).toBeTruthy();
  });

  it("walled or not on the team: 404, nothing of the record, no Decide", async () => {
    show("a", { persona: "lena-park" });
    await waitFor(() => {
      expect(canvas().textContent).not.toBe("");
    });
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText("Form 706 is required")).toBeNull();
    expect(screen.queryByRole("button", { name: "Decide" })).toBeNull();
  });
});
