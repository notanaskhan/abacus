// TXP-12 · K-1 package (T-02-T25). One test per artboard (A, A2–A5, B, B2, C–F) on its fixture
// scenario; every read in the OpenAPI schema; Release stays disabled with every failing check
// named until the check passes; no row shows a TIN (the detail carries it masked, ADR-031); and
// the release, Undo, share and resend are a person's clicks on their routes: nothing is sent first.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
} from "../../app-core/fixture-mode";
import { validateResponse } from "../../fixtures/schema-check";
import {
  BLUESTEM_RETURN,
  RIDGELINE_RETURN,
  k1Check,
  k1Counts,
  k1Rows,
} from "../../fixtures/seed/k1-packages";
import { newQueryClient } from "../../testing/support";
import { K1PackagePage } from ".";
import { COPY } from "./copy";
import { OPENING, OPENS, STATES, type Txp12State, scenarios } from "./scenarios";

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

function show(state: Txp12State, override: Record<string, FixtureHandler> = {}): Seen {
  const seen: Seen = { calls: [] };
  const scenario: Scenario = scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries({ ...scenario.handlers, ...override }).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  const opening = OPENING[state];
  render(
    <QueryClientProvider client={newQueryClient()}>
      <K1PackagePage returnId={OPENS[state]} {...(opening === undefined ? {} : { opening })} />
    </QueryClientProvider>,
  );
  return seen;
}

const writes = (seen: Seen) => seen.calls.filter((c) => c.method !== "GET");

describe("TXP-12 artboards", () => {
  it("covers A, A2–A5, B, B2 and C–F", () => {
    expect(STATES).toEqual(["a", "a2", "a3", "a4", "a5", "b", "b2", "c", "d", "e", "f"]);
  });

  it("every artboard's rows and check are in the schema", () => {
    for (const v of ["drafts", "approved", "released", "amended"] as const) {
      for (const ret of [RIDGELINE_RETURN, BLUESTEM_RETURN]) {
        const rows = k1Rows(ret, v);
        expect(
          validateResponse("GET", "/v1/tax-returns/{return_id}/k1-packages", {
            items: rows,
            next_cursor: null,
            total: rows.length,
            counts: k1Counts(rows),
          }),
        ).toEqual([]);
        expect(
          validateResponse(
            "GET",
            "/v1/tax-returns/{return_id}/k1-packages/release-check",
            k1Check(ret, v),
          ),
        ).toEqual([]);
      }
    }
  });

  it("A: five drafts, the shared-drafts banner, and Release locked with its reason", async () => {
    const seen = show("a");
    await screen.findByText("Pell Street II LLC");
    expect(screen.getByText("Jul 1 – Dec 31, 2025")).toBeTruthy();
    expect(screen.getAllByText("Draft K-1 · pre-release").length).toBeGreaterThanOrEqual(5);
    expect(
      await screen.findByText(
        "Drafts only. Two drafts are shared internally with the Shah and Feld 1040s, where they block final approval until release.",
      ),
    ).toBeTruthy();
    await screen.findByText(/^Release blocked: final approval \(/);
    expect(screen.getAllByText(/final K-1s not imported/).length).toBeGreaterThan(0);
    const release = screen.getByRole("button", { name: COPY.releaseK1s });
    expect(release).toHaveProperty("disabled", true);
    expect(release.getAttribute("aria-describedby")).toBeTruthy();
    expect(screen.getByText("Shah 1040 · shared Sep 10")).toBeTruthy();
    // No TIN on a list row (ADR-031).
    expect(document.body.textContent).not.toMatch(/4417|2290|3318/);
    expect(writes(seen)).toEqual([]);
  });

  it("A2: Jonah Feld's row expands with boxes, state lines, documents and the masked TIN", async () => {
    show("a2");
    expect(await screen.findByText(/Box 2 307,900 · Box 5 4,600 · Box 18A 1,550/)).toBeTruthy();
    expect(screen.getByText(/Item K 2,762,075 · Item L ending 1,912,500/)).toBeTruthy();
    expect(
      screen.getByText(/PTET credit 7,011 · CO 4,268 · NY \(IT-653 PTET credit\) 4,746/),
    ).toBeTruthy();
    expect(screen.getByText("•••-••-4417")).toBeTruthy();
    expect(screen.getByText("State K-1s (3)")).toBeTruthy();
    const toggle = screen.getByRole("button", { name: COPY.collapseRow("Jonah Feld") });
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(document.getElementById(toggle.getAttribute("aria-controls") ?? "")).toBeTruthy();
  });

  it("A3: the K-3 note names the import, not an agent (DV-9)", async () => {
    show("a3");
    await screen.findByText("Pell Street II LLC");
    expect(screen.getAllByText(COPY.k3Tip).length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toMatch(/agent/i);
  });

  it("A4: Share draft internally lists the related returns and shares only on the click", async () => {
    const seen = show("a4");
    expect(await screen.findByText(COPY.share.warning)).toBeTruthy();
    const dialog = screen.getByRole("dialog");
    expect(await within(dialog).findByText("Jonah & Claire Feld · 2025 Form 1040")).toBeTruthy();
    expect(within(dialog).getAllByText("Draft shared Sep 10").length).toBe(2);
    expect(writes(seen)).toEqual([]);
  });

  it("A5: after final approval the confirm releases, and Undo calls the undo route", async () => {
    const seen = show("a5");
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText(COPY.release.recipients(5))).toBeTruthy();
    expect(writes(seen)).toEqual([]);
    fireEvent.click(within(dialog).getByRole("button", { name: COPY.release.confirm }));
    await waitFor(() => {
      expect(writes(seen).map((c) => c.path)).toEqual([
        `/v1/tax-returns/${RIDGELINE_RETURN}/k1-packages:release`,
      ]);
    });
    const body = writes(seen)[0]?.body as { package_ids: string[]; seen_version: number };
    expect(body.package_ids).toHaveLength(5);
    expect(body.seen_version).toBe(1);
    // The ten-second Undo toast; its action calls the undo route.
    let held: ReturnType<typeof toastStore.list>[number] | undefined;
    await waitFor(() => {
      held = toastStore.list().find((t) => t.text === COPY.release.releasing(5));
      expect(held?.action).toBe("Undo");
    });
    if (held !== undefined) toastStore.act(held.id);
    await waitFor(() => {
      expect(writes(seen).at(-1)?.path).toMatch(/^\/v1\/k1-releases\/.+:undo$/);
    });
  });

  it("B: released, viewed, downloaded and bounced, with finals replacing the drafts", async () => {
    show("b");
    expect(await screen.findByText(COPY.bounced)).toBeTruthy();
    expect(screen.getAllByText("Released Sep 15").length).toBe(2); // the subbar and the GP row
    expect(screen.getByText("Feld 1040 · final replaced draft")).toBeTruthy();
    expect(screen.queryByText(/^Drafts only\./)).toBeNull();
    expect(screen.getByText(/to the portal \(POR-13\) · 1 invite bounced/)).toBeTruthy();
  });

  it("B2: Resend… on the bounced row sends the chosen contact", async () => {
    const seen = show("b2");
    expect(await screen.findByText(COPY.resendDialog.body("Pell Street II LLC"))).toBeTruthy();
    expect(writes(seen)).toEqual([]);
  });

  it("C: 1120-S mode shows shareholders with K-3 not required and NY", async () => {
    show("c");
    expect((await screen.findAllByText("Arjun Mehta")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Sunita Rao").length).toBeGreaterThan(0);
    expect(screen.getAllByText(COPY.k3NotRequired)).toHaveLength(2);
    expect(screen.getAllByText("NY")).toHaveLength(2);
  });

  it("D: 1041 mode shows the beneficiaries as drafts", async () => {
    show("d");
    expect((await screen.findAllByText("Nora Calloway")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Theo Calloway").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Draft K-1 · pre-release").length).toBeGreaterThanOrEqual(2);
  });

  it("E: the amended Feld K-1 supersedes the Sep 15 package, which stays struck", async () => {
    show("e");
    expect(await screen.findByText("Superseded (amended K-1)")).toBeTruthy();
    const struck = screen
      .getAllByText("Jonah Feld")
      .filter((el) => el.className.includes("line-through"));
    expect(struck).toHaveLength(1);
  });

  it("F: a return with no K-1 set reads the import empty state", async () => {
    show("f");
    expect(await screen.findByText(COPY.emptyTitle)).toBeTruthy();
    expect(screen.getByText(COPY.emptyBody)).toBeTruthy();
  });

  it("Release stays disabled until every check passes, then opens the confirm", async () => {
    show("a", {
      "GET /v1/tax-returns/{return_id}/k1-packages/release-check": () =>
        Response.json({ ...k1Check(RIDGELINE_RETURN, "drafts"), failing: ["no_release_policy"] }),
    });
    await screen.findByText(/Release blocked: no release signer in BH-TAX-02/);
    expect(screen.getByRole("button", { name: COPY.releaseK1s })).toHaveProperty("disabled", true);
  });
});
