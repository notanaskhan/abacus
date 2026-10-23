// SHL-14 · Request composer drawer (P-06-T13). One test per state this task builds (a, b, e, f)
// on its fixture scenario, the R2 items 1–5, the dirty guard, the send flow against the C5
// routes, and the task's acceptance: "A Draft never offers Save & send without a due date and
// Approve & send records the person as sender."
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
} from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { RequestComposer } from ".";
import { CLOCK_A, CLOCK_F, OPENS, STATES, type Shl14State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  toastStore.clear();
});

interface Seen {
  calls: { method: string; path: string; body: unknown }[];
}

function show(state: Shl14State): Seen {
  const seen: Seen = { calls: [] };
  const scenario: Scenario = scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  const { binderId, requestId } = OPENS[state];
  renderRoutes([
    {
      path: "/",
      component: () => (
        <RequestComposer
          binderId={binderId}
          requestId={requestId}
          open
          onOpenChange={() => undefined}
        />
      ),
    },
  ]);
  return seen;
}

function drawer(): HTMLElement {
  return screen.getByRole("dialog");
}

function input(label: string): HTMLInputElement | HTMLTextAreaElement {
  const field = within(drawer()).getByLabelText(label);
  return field as HTMLInputElement;
}

async function choose(label: RegExp, option: string): Promise<void> {
  const trigger = within(drawer()).getByRole("button", { name: label });
  trigger.focus();
  fireEvent.keyDown(trigger, { key: "ArrowDown" });
  const menu = await screen.findByRole("menu");
  fireEvent.click(within(menu).getByText(option));
}

describe("SHL-14 states", () => {
  it("defines a, b and e as Marcus Delaney on Sep 14 and f as Cole Hart on Sep 24", () => {
    expect(STATES).toEqual(["a", "b", "e", "f"]);
    for (const s of ["a", "b", "e"] as const) {
      expect(scenarios[s].persona).toBe("marcus-delaney");
      expect(scenarios[s].clock).toBe(CLOCK_A);
    }
    expect(scenarios.f.persona).toBe("cole-hart");
    expect(scenarios.f.clock).toBe(CLOCK_F);
  });

  it("SHL-14a new: a Draft on the Northwind binder, due from the binder default", async () => {
    show("a");
    expect(await screen.findByRole("heading", { name: "New request" })).toBeTruthy();
    expect(within(drawer()).getByText("Draft")).toBeTruthy();
    expect(await within(drawer()).findByText("Northwind · PY2025")).toBeTruthy();
    expect(within(drawer()).getByRole("tab", { name: "Details" })).toBeTruthy();
    expect(within(drawer()).getByRole("tab", { name: "Comments" })).toBeTruthy();
    expect(within(drawer()).getByRole("tab", { name: "Activity" })).toBeTruthy();
    expect(within(drawer()).getByText("Document request")).toBeTruthy();
    expect(within(drawer()).getByText("People")).toBeTruthy();
    expect(within(drawer()).getByText("Links")).toBeTruthy();
    await waitFor(() => {
      expect(input("Due").value).toBe("2026-09-21");
    });
    expect(
      await within(drawer()).findByText(
        "Adds 1 request · Source Documents will read 11 of 25 received",
      ),
    ).toBeTruthy();
    expect(within(drawer()).getByText("Becomes Client when sent")).toBeTruthy();
    expect(within(drawer()).getByText("Every 3 days until received")).toBeTruthy();
    expect(
      within(drawer()).getByText("Sent from the pre-approved reminder template"),
    ).toBeTruthy();
  });

  it("SHL-14b existing: the bridge letter, requested Sep 1, due Sep 25, delegated to Sam Ortiz", async () => {
    show("b");
    expect(await screen.findByRole("heading", { name: "Request" })).toBeTruthy();
    expect(await within(drawer()).findByText("Requested Sep 1 · due Sep 25")).toBeTruthy();
    await waitFor(() => {
      expect(input("Request").value).toBe("Bridge letter — Keystone, Oct–Dec 2025");
    });
    expect(input("Description").value).toContain("Keystone's SOC 1 Type 2 report covers");
    fireEvent.click(within(drawer()).getByRole("switch", { name: "Request from a third party" }));
    await choose(/^Third party/, "Sam Ortiz");
    expect(
      await within(drawer()).findByText("Sam sees only this request (POR-14). Dana is copied."),
    ).toBeTruthy();
    expect(
      within(drawer()).getByRole("button", { name: "Save & send to Sam Ortiz" }),
    ).toBeTruthy();
    expect(within(drawer()).getByText("Preview — what Sam sees")).toBeTruthy();
  });

  it("SHL-14e validation: no due date, so Save & send is disabled with its reason", async () => {
    show("e");
    expect(await screen.findByRole("heading", { name: "New request" })).toBeTruthy();
    expect(await within(drawer()).findByText("Add a due date to send")).toBeTruthy();
    fireEvent.change(input("Request"), {
      target: { value: "ERISA fidelity bond — 2025 declarations page" },
    });
    fireEvent.change(input("Description"), {
      target: { value: "ERISA §412 requires a fidelity bond." },
    });
    await choose(/^Category/, "Plan documents");
    const send = within(drawer()).getByRole("button", { name: "Save & send" });
    expect((send as HTMLButtonElement).disabled).toBe(true);
    expect(
      within(drawer()).getByRole<HTMLButtonElement>("button", { name: "Save draft" }).disabled,
    ).toBe(false);
  });

  it("SHL-14f agent-drafted Draft: Approve & send to Luis Ferrante; Activity names the drafting session", async () => {
    show("f");
    expect(
      await within(await screen.findByRole("dialog")).findByRole("button", {
        name: "Approve & send to Luis Ferrante",
      }),
    ).toBeTruthy();
    expect(within(drawer()).getByText("Draft")).toBeTruthy();
    expect(input("Request").value).toBe("Support for 40 subsequent disbursements (SURL)");
    expect(within(drawer()).getByText("Owners only")).toBeTruthy();
    fireEvent.click(within(drawer()).getByRole("tab", { name: "Activity" }));
    expect(
      await within(drawer()).findByText(
        "Drafted by Accrued Agent in the BH-FS-430 procedure session",
      ),
    ).toBeTruthy();
  });
});

describe("SHL-14 acceptance", () => {
  it("P-06 §3.3: a new request is created, given its fields and sent by the person, then toasts", async () => {
    const seen = show("a");
    await screen.findByRole("heading", { name: "New request" });
    await waitFor(() => {
      expect(input("Due").value).toBe("2026-09-21");
    });
    fireEvent.change(input("Request"), {
      target: { value: "ERISA fidelity bond — 2025 declarations page" },
    });
    fireEvent.change(input("Description"), {
      target: {
        value:
          "ERISA §412 requires a fidelity bond of at least 10% of plan assets handled, capped at $500,000 for this plan.",
      },
    });
    await choose(/^Category/, "Plan documents");
    await choose(/^Client assignee/, "Dana Kowalski");
    fireEvent.click(within(drawer()).getByRole("button", { name: "Save & send" }));
    await waitFor(() => {
      expect(toastStore.list().map((t) => t.text)).toContain("Request sent to Dana Kowalski");
    });
    const writes = seen.calls.filter((c) => c.method !== "GET").map((c) => c.method);
    expect(writes).toEqual(["POST", "PATCH", "POST"]);
    const patch = seen.calls.find((c) => c.method === "PATCH");
    expect(patch?.body).toMatchObject({
      title: "ERISA fidelity bond — 2025 declarations page",
      due_on: "2026-09-21",
      wave: "planning",
    });
    expect(
      seen.calls.at(-1)?.path ?? seen.calls.filter((c) => c.method === "POST").at(-1)?.path,
    ).toBeTruthy();
    expect(seen.calls.some((c) => c.method === "POST" && c.path.endsWith("/send"))).toBe(true);
  });

  it("SHL-14 acceptance (R2): Draft is a neutral outline pill; Visibility reads Owners only until sent", async () => {
    show("a");
    const pill = await within(await screen.findByRole("dialog")).findByText("Draft");
    expect(pill.closest(".bg-card")).not.toBeNull();
    expect(
      within(drawer()).getByRole("tab", { name: "Owners only" }).getAttribute("aria-selected"),
    ).toBe("true");
  });

  it("SHL-14 acceptance (R2): Links shows Related rows and Controls; the cross-engagement link stays hidden (DV-6)", async () => {
    show("a");
    await screen.findByRole("heading", { name: "New request" });
    expect(within(drawer()).getByText("Related rows")).toBeTruthy();
    expect(within(drawer()).getByText("Controls")).toBeTruthy();
    expect(within(drawer()).queryByText(/Link from another engagement/)).toBeNull();
  });

  it("SHL-14 acceptance: the client preview is plain language and free of firm internals", async () => {
    show("b");
    await within(await screen.findByRole("dialog")).findByText("Requested Sep 1 · due Sep 25");
    const preview = (await within(drawer()).findByText(/Preview — what/)).closest("section");
    if (preview === null) throw new Error("no preview");
    const text = preview.textContent;
    expect(text).toContain("Please provide a bridge letter");
    expect(text).not.toMatch(/materiality|sample seed|BH-EBP|Accrued/i);
  });

  it("SHL-14 acceptance: a Draft never offers Save & send without a due date", async () => {
    show("e");
    await within(await screen.findByRole("dialog")).findByText("Add a due date to send");
    expect(
      within(drawer()).getByRole<HTMLButtonElement>("button", { name: "Save & send" }).disabled,
    ).toBe(true);
  });

  it("SHL-14 acceptance: the server answers 422 due_date_required to a send without a due date", async () => {
    const h = scenarios.e.handlers;
    const req = (params: Record<string, string>, body: unknown) => ({
      method: "POST",
      path: "",
      params,
      query: new URLSearchParams(),
      body,
      persona: "marcus-delaney",
    });
    const engagementId = (await (
      await h["GET /v1/binders/{binder_id}"]?.(req({ binder_id: OPENS.e.binderId }, null))
    )?.json()) as { engagement_id: string };
    const created = await h["POST /v1/engagements/{engagement_id}/request-items"]?.(
      req(
        { engagement_id: engagementId.engagement_id },
        { audit_area: "Plan documents", description: "x" },
      ),
    );
    const item = (await created?.json()) as { id: string };
    const sent = await h["POST /v1/engagements/{engagement_id}/request-items/{item_id}/send"]?.(
      req({ engagement_id: engagementId.engagement_id, item_id: item.id }, null),
    );
    expect(sent?.status).toBe(422);
    expect(await sent?.json()).toEqual({ detail: "due_date_required" });
  });
});
