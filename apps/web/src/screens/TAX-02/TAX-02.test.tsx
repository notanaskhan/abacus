// TAX-02 · Return › Overview (T-02-T14). One test per artboard (a–f) on its fixture scenario, the
// statement footing, the live Assign…, the engine deep link and the entity variant.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
} from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { ReturnOverviewPage } from ".";
import { COPY } from "./copy";
import { ENTITY_RETURN, OPENS, STATES, type Tax02State, scenarios } from "./scenarios";

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

function show(
  state: Tax02State,
  extra: Record<string, FixtureHandler> = {},
  returnId: string = OPENS[state],
): Seen {
  const seen: Seen = { calls: [] };
  const scenario: Scenario = scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries({ ...scenario.handlers, ...extra }).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <ReturnOverviewPage returnId={returnId} />
    </QueryClientProvider>,
  );
  return seen;
}

async function ready(): Promise<void> {
  await screen.findByRole("heading", { name: COPY.canvas, level: 2 }).catch(() => undefined);
  await screen.findByText(/^2025 Form /);
}

describe("TAX-02 artboards", () => {
  it("covers a to f", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f"]);
  });

  it("a: In review · Manager, the blocked final approval and the dependency banner", async () => {
    show("a");
    await ready();
    expect((await screen.findAllByText("In review · Manager")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Blocked by Draft K-1 · pre-release")).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain(
      "Ridgeline 1065 K-1 is a draft — final approval is blocked until Ridgeline Property Partners, LP is approved",
    );
    expect(screen.getByText("Jonah & Claire Feld · Married filing jointly")).toBeTruthy();
    expect(screen.getByText("2025 Binder · 5 of 7 requests satisfied")).toBeTruthy();
  });

  it("a: the estimate foots and shows 2a blank with its ⚑ note", async () => {
    show("a");
    await ready();
    const card = await screen.findByRole("region", { name: COPY.estimate });
    expect(within(card).getByText("Federal estimate · from CCH Axcess sync Sep 10")).toBeTruthy();
    const text = card.textContent;
    for (const figure of ["598,030", "41,331", "61,580", "495,119", "123,223", "123,476", "253"]) {
      expect(text).toContain(figure);
    }
    expect(within(card).getByText("K-1 box 18A 1,550 not yet carried (Issue)")).toBeTruthy();
    expect(text).toContain("SALT 10,591 after phase-down");
  });

  it("a: four open issues, 2 Missing information + 1 Action required + 1 Review point", async () => {
    show("a");
    await ready();
    const card = await screen.findByRole("region", { name: COPY.issues(4) });
    expect(within(card).getAllByText(COPY.issueKind.missing_information)).toHaveLength(2);
    expect(within(card).getAllByText(COPY.issueKind.action_required)).toHaveLength(1);
    expect(within(card).getAllByText(COPY.issueKind.review_point)).toHaveLength(1);
  });

  it("a: the two-year snapshot and the tax plan", async () => {
    show("a");
    await ready();
    const two = await screen.findByRole("region", { name: COPY.twoYear });
    expect(two.textContent).toContain("551,940 → 598,030");
    expect(two.textContent).toContain("(−78.4%)");
    const plan = screen.getByRole("region", { name: COPY.plan });
    expect(within(plan).getByText("Draft K-1 · pre-release")).toBeTruthy();
    expect(within(plan).getByText("residency review point open")).toBeTruthy();
  });

  it("b: not started — pipeline all rings and the no-draft empty state", async () => {
    show("b");
    await ready();
    expect(await screen.findByText(COPY.noDraftTitle)).toBeTruthy();
    expect(screen.getByText(COPY.noDraftBody)).toBeTruthy();
    expect(screen.getByText("Binder not published")).toBeTruthy();
    expect(screen.getAllByText(COPY.notAssigned)).toHaveLength(2);
  });

  it("c: gathering — the pro forma replaces the estimate", async () => {
    show("c");
    await ready();
    expect(await screen.findByText("Pro forma 2025I:FeldJ:V1 imported Feb 3")).toBeTruthy();
    expect(screen.getByText("CCH Axcess · TY2024 return rolled forward")).toBeTruthy();
    expect(screen.getByText("Waiting on K-1")).toBeTruthy();
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("d: prepared — no estimate yet and detail review not started", async () => {
    show("d");
    await ready();
    expect(await screen.findByText(COPY.noEstimate)).toBeTruthy();
    expect(screen.getByText("YK · not started")).toBeTruthy();
    expect(screen.getAllByText("Prepared").length).toBeGreaterThan(0);
  });

  it("e: accepted — banner gone, every rung done, released K-1", async () => {
    show("e");
    await ready();
    expect((await screen.findAllByText("Accepted")).length).toBeGreaterThan(0);
    expect(screen.getByText("Daniel Reyes · Sep 16")).toBeTruthy();
    expect(screen.getByText("Released Sep 15")).toBeTruthy();
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("f: loading — the record never answers", async () => {
    show("f");
    await waitFor(() => {
      expect(document.querySelector("[data-screen='TAX-02']")).not.toBeNull();
    });
    expect(screen.queryByText(/^2025 Form /)).toBeNull();
  });
});

describe("TAX-02 behaviour", () => {
  it("Assign… posts the chosen role and member to …/assignments", async () => {
    const seen = show("a");
    await ready();
    fireEvent.click(await screen.findByRole("button", { name: COPY.actions.assign }));
    fireEvent.click(await screen.findByRole("menuitem", { name: COPY.assignRoles.reviewer }));
    const members = await screen.findAllByRole("menuitem");
    fireEvent.click(members[0] as HTMLElement);
    await waitFor(() => {
      expect(seen.calls.some((c) => c.method === "POST" && c.path.endsWith("/assignments"))).toBe(true);
    });
    const post = seen.calls.find((c) => c.path.endsWith("/assignments"));
    expect((post?.body as { role: string }).role).toBe("reviewer");
  });

  /** The scenario's record with another `engine_url` (T-02-T13 builds it from ADM-08's template). */
  const withEngineUrl =
    (url: string): FixtureHandler =>
    async (request) => {
      const base = scenarios.a.handlers["GET /v1/tax-returns/{return_id}"];
      if (base === undefined) throw new Error("no record handler");
      const body = (await (await base(request)).json()) as Record<string, unknown>;
      return json({ ...body, engine_url: url });
    };

  it("Open in CCH Axcess is an https deep link in a new tab, never automation", async () => {
    show("a", {
      "GET /v1/tax-returns/{return_id}": withEngineUrl("https://axcess.example.test/r/FeldJ"),
    });
    await ready();
    const link = await screen.findByRole("link", { name: COPY.actions.openEngine });
    expect(link.getAttribute("href")).toBe("https://axcess.example.test/r/FeldJ");
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toContain("noopener");
  });

  it("a non-https engine link is never drawn as a link", async () => {
    show("a", { "GET /v1/tax-returns/{return_id}": withEngineUrl("javascript:alert(1)") });
    await ready();
    expect(await screen.findByRole("button", { name: COPY.actions.openEngine })).toBeTruthy();
    expect(screen.queryByRole("link", { name: COPY.actions.openEngine })).toBeNull();
  });

  it("an entity return (Ridgeline 1065) opens here with its own row and no invented bands", async () => {
    show("a", {}, ENTITY_RETURN);
    expect(await screen.findByText("2025 Form 1065")).toBeTruthy();
    expect(screen.getAllByText(/Ridgeline Property Partners, LP/).length).toBeGreaterThan(0);
    expect(screen.queryByText(COPY.bands.team)).toBeNull();
  });
});
