// SPEC-020, SPEC-031 and SPEC-042 tests of the retired legacy client page (ClientEngagement.tsx and
// ClientGuidance.tsx), moved here by R-01-T18 with their AC names. The page is now POR-03
// (Documents) and POR-04 (the request sheet) in the portal entry, so each screen test drives the
// POR screen on its fixture scenario; the wording tests run unchanged against the moved logic in
// `clientHub.ts`. Assertions the portal's design no longer carries are listed, with their reason,
// in DEC-443 (docs/product/decision-log.md) rather than dropped silently.
import { client } from "@abacus/api-client/client";
import type { PortalRequestOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
} from "../../app-core/fixture-mode";
import { ARTBOARD as POR03_ARTBOARD, scenarios as por03 } from "../../fixtures/scenarios/POR-03";
import { freshScenario, type Por04State } from "../../fixtures/scenarios/POR-04";
import { FELD_DROP, sheet1095c } from "../../fixtures/seed/portal-documents";
import { PortalDocuments } from "../../screens/POR-03";
import { PortalRequest } from "../../screens/POR-04";
import { ARTBOARD as POR04_ARTBOARD } from "../../screens/POR-04/scenarios";
import { renderRoutes } from "../../testing/support";
import { estimate, gapMessage, outcomeLabel, yourPartMessage } from "./clientHub";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

type Call = { method: string; path: string; body: unknown };

function install(scenario: Scenario, over: Record<string, FixtureHandler> = {}): Call[] {
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

/** POR-03 on one of its artboards (the client's Documents page). */
function documents(state: keyof typeof por03, over: Record<string, FixtureHandler> = {}): Call[] {
  const calls = install(por03[state], over);
  const board = POR03_ARTBOARD[state];
  renderRoutes([
    {
      path: "/",
      component: () => (
        <PortalDocuments
          binderId={board.binderId}
          hold={{
            ...(board.ignoreOpenOn === undefined ? {} : { ignoreOpenOn: board.ignoreOpenOn }),
            still: true,
          }}
        />
      ),
    },
  ]);
  return calls;
}

/** POR-04 on one of its artboards (one request), optionally with another request body. */
function request(state: Por04State, sheet?: PortalRequestOut): Call[] {
  const calls = install(
    freshScenario(state),
    sheet === undefined ? {} : { "GET /v1/portal/request-items/{item_id}": () => json(sheet) },
  );
  const board = POR04_ARTBOARD[state];
  renderRoutes([
    {
      path: "/",
      component: () => (
        <PortalRequest
          requestId={board.requestId}
          hold={board.ignoreOpen === true ? { ignoreOpen: true } : {}}
        />
      ),
    },
  ]);
  return calls;
}

async function row(title: string): Promise<HTMLElement> {
  const text = await screen.findByText(title);
  const el = text.closest<HTMLElement>("[data-request]");
  if (el === null) throw new Error(`no row ${title}`);
  return el;
}

describe("SPEC-020 (moved from legacy/spec020.test.tsx)", () => {
  describe("ac1 client engagement page", () => {
    it("shows the engagement and its requests grouped by area", async () => {
      documents("a");
      expect(await screen.findByText("Form 1095-C From Mercer Hill Health")).toBeTruthy();
      expect(screen.getByRole("button", { name: /2025 Binder/ })).toBeTruthy();
      const rail = screen.getByRole("listbox", { name: /categor/i });
      expect(within(rail).getAllByRole("option").length).toBeGreaterThan(1);
      expect(within(rail).getByRole("option", { name: /Income Sources/ })).toBeTruthy();
      // A contributor gets no assignee picker.
      expect(screen.queryByLabelText("Assigned to")).toBeNull();
    });

    it("tells a contributor with nothing assigned what happens next", async () => {
      documents("h");
      expect(await screen.findByText("You’re all caught up.")).toBeTruthy();
      expect(screen.getByText("Brightwater Hale hasn’t requested anything new.")).toBeTruthy();
    });
  });

  describe("ac8 ac9 uploads", () => {
    it("uploads each chosen file, shows its result, and explains a refusal in plain words", async () => {
      let posts = 0;
      const calls = documents("a", {
        "POST /v1/portal/binders/{binder_id}/drops": () => {
          posts += 1;
          return posts === 1
            ? json({ batch_id: FELD_DROP.batch_id, file_id: FELD_DROP.files[0]?.file_id }, 202)
            : json({ detail: "type_not_allowed" }, 415);
        },
        "GET /v1/portal/drops/{batch_id}": () => json(FELD_DROP),
      });
      await screen.findByText("Form 1095-C From Mercer Hill Health");
      const well = document.querySelector<HTMLElement>("[data-part='well']");
      const files = [
        new File(["%PDF-1.7"], "Feld_2025_Estimated_Payments.pdf", { type: "application/pdf" }),
        new File(["MZ"], "tool.exe", { type: "application/octet-stream" }),
      ];
      fireEvent.drop(well as HTMLElement, { dataTransfer: { files, types: ["Files"] } });
      const refused = await screen.findByRole("list", { name: "Files not uploaded" });
      expect(
        within(refused).getByText(
          "tool.exe can't be uploaded here. Send a PDF, a photo, a spreadsheet, a Word document or a CSV.",
        ),
      ).toBeTruthy();
      await waitFor(() => {
        expect(document.querySelector("[data-part='sort-live']")?.textContent).not.toBe("");
      });
      expect(calls.filter((c) => c.method === "POST" && c.path.endsWith("/drops"))).toHaveLength(
        2,
      );
    });

    it("offers no upload on a request that no longer takes files", async () => {
      request("c");
      const box = await screen.findByRole("dialog");
      await within(box).findByText("✓ Received by email Sep 14");
      expect(within(box).queryByText("Drop the file here")).toBeNull();
      expect(within(box).queryByRole("button", { name: "Upload…" })).toBeNull();
    });
  });

  describe("ac7 states", () => {
    it("shows an error when the requests can't load", async () => {
      documents("a", {
        "GET /v1/portal/binders/{binder_id}": () => json({ detail: "unavailable" }, 503),
      });
      expect(await screen.findByText("Couldn’t load your documents.")).toBeTruthy();
      expect(screen.getByRole("button", { name: "Retry" })).toBeTruthy();
    });
  });
});

describe("SPEC-031 (moved from legacy/spec031clienthub.test.tsx)", () => {
  describe("ac1 the client's request", () => {
    it("shows why, what good looks like, still needed and the due date", async () => {
      request("a");
      const box = await screen.findByRole("dialog");
      expect(await within(box).findByText("Why we need it")).toBeTruthy();
      expect(within(box).getByText(/we use it to confirm your coverage/)).toBeTruthy();
      expect(within(box).getByText("To do · requested Feb 3")).toBeTruthy();
    });

    it("shows no guidance headings when there's none", async () => {
      request("a", sheet1095c({ guidance: null }));
      const box = await screen.findByRole("dialog");
      await within(box).findByRole("heading", { name: "Form 1095-C From Mercer Hill Health" });
      expect(within(box).queryByText("Why we need it")).toBeNull();
    });
  });

  describe("ac4 provided", () => {
    it("says where it came from and asks for no upload", async () => {
      request("c");
      const box = await screen.findByRole("dialog");
      expect(await within(box).findByText("✓ Received by email Sep 14")).toBeTruthy();
      expect(
        within(box).getByText(
          "Brightwater Hale will check it and let you know if anything is missing.",
        ),
      ).toBeTruthy();
      expect(within(box).queryByRole("button", { name: "Upload…" })).toBeNull();
    });
  });

  describe("ac5 the gap", () => {
    it.each([
      [
        { covered: ["2290", "8812"], needed: ["4471"] },
        "We have statements for accounts ending 2290 and 8812; we still need account ending 4471.",
      ],
      [
        { covered: [], needed: ["4471", "Payroll"] },
        "We still need statements for account ending 4471 and the Payroll account.",
      ],
      [{ covered: ["2290"], needed: [] }, null],
    ])("words the gap", (gap, expected) => {
      expect(gapMessage(gap)).toBe(expected);
    });
  });

  describe("ac7 history", () => {
    const entry = {
      evidence_version_id: "v1",
      added_by: "client" as const,
      added_by_name: "Cara",
      added_at: "2026-10-09T10:00:00Z",
    };

    it("labels each outcome; a send-back shows its reason", () => {
      expect(outcomeLabel({ ...entry, outcome: "sent_back", reason_label: "Wrong period" })).toBe(
        "Sent back: Wrong period",
      );
      expect(outcomeLabel({ ...entry, outcome: "not_accepted" })).toBe("Not accepted");
      expect(outcomeLabel({ ...entry, outcome: "replaced" })).toBe("Replaced");
    });

    it("shows the send-back note with the upload and the provided rows", async () => {
      request("d");
      const box = await screen.findByRole("dialog");
      expect(await within(box).findByText("Returned · wrong year")).toBeTruthy();
      expect(
        within(box).getByText(/This is the 2024 form\. We need the 2025 Form 1095-C\./),
      ).toBeTruthy();
      expect(within(box).getByText("Feld_1095C_2024.pdf")).toBeTruthy();
    });
  });

  describe("ac6 your part", () => {
    it.each([
      [0, "about 15 minutes"],
      [45, "about 45 minutes"],
      [60, "about 1 hour"],
      [90, "about 1½ hours"],
      [180, "about 3 hours"],
    ])("estimates %i minutes", (minutes, expected) => {
      expect(estimate(minutes)).toBe(expected);
    });

    it("words the part", () => {
      expect(yourPartMessage({ items_left: 6, blocks_fieldwork: 2, minutes: 90 })).toBe(
        "6 left · 2 block fieldwork · about 1½ hours",
      );
      expect(yourPartMessage({ items_left: 3, blocks_fieldwork: 1, minutes: 60 })).toBe(
        "3 left · 1 blocks fieldwork · about 1 hour",
      );
      expect(yourPartMessage({ items_left: 0, blocks_fieldwork: 0, minutes: 0 })).toBe(
        "Nothing left for you",
      );
    });
  });
});

describe("SPEC-042 the portal (moved from legacy/spec042portal.test.tsx)", () => {
  it("uses the client's words", async () => {
    documents("a");
    await screen.findByText("Form 1095-C From Mercer Hill Health");
    expect(screen.getAllByRole("button", { name: /^Ignore / }).length).toBeGreaterThan(0);
    const text = document.body.textContent;
    for (const word of [/Uploaded – needs review/, /Received ✓/, /\bAgent\b/, /Accrued/]) {
      expect(text).not.toMatch(word);
    }
  });

  it("says a request doesn't apply, with a reason (ac1)", async () => {
    const calls = request("b");
    const box = await screen.findByRole("dialog");
    const group = await within(box).findByRole("radiogroup", { name: "Why doesn't this apply?" });
    fireEvent.click(within(group).getByRole("radio", { name: "I don’t have this" }));
    fireEvent.click(within(box).getByRole("button", { name: "Mark not applicable" }));
    await waitFor(() => {
      const ignore = calls.find((c) => c.path.endsWith("/ignore"));
      expect((ignore?.body as { reason?: string } | undefined)?.reason).toBe("dont_have");
    });
  });

  it("shows what they said, with Undo (ac2)", async () => {
    documents("f");
    const menu = await screen.findByRole("menu", { name: "Ignore" });
    fireEvent.click(within(menu).getByRole("menuitem", { name: "Already sent another way" }));
    const form = await row("Form 1095-C From Mercer Hill Health");
    expect(await within(form).findByRole("button", { name: "Undo" })).toBeTruthy();
  });

  it("lets the admin mark the list done once everything is done (ac4)", async () => {
    const calls = documents("c2");
    const done = await screen.findByRole("button", { name: "Mark as Done" });
    expect(done.getAttribute("data-ready")).toBe("true");
    fireEvent.click(done);
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/mark-done"))).toBe(true);
    });
  });
});
