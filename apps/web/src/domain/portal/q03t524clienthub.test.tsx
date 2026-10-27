// ac-test-author: ayushkbhatia
// Q-03-T524: back-fill of TASK-061 (client hub web), black-box from SPEC-031 against the client
// paths that replaced the legacy page (R-01-T18: POR-03 Documents and POR-04 the request sheet),
// driven through their fixture scenarios. Retired only when R-01's own AC suite covers SPEC-031.
// Server ACs (2, 3, 8, and the counts behind 5 and 6) are Q-03-T047's
// backend/tests/integration/backfill/test_q03t047_requests_client_hub.py and
// backend/tests/unit/engagements/test_workbook_guidance.py (see TASK-1707).
import { client } from "@abacus/api-client/client";
import { cleanup, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
  never,
} from "../../app-core/fixture-mode";
import { freshScenario, type Por04State } from "../../fixtures/scenarios/POR-04";
import { sheet1095c } from "../../fixtures/seed/portal-documents";
import { PortalRequest } from "../../screens/POR-04";
import { ARTBOARD as POR04_ARTBOARD } from "../../screens/POR-04/scenarios";
import { renderRoutes } from "../../testing/support";
import { gapMessage, outcomeLabel, yourPartMessage } from "./clientHub";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

const SHEET = "GET /v1/portal/request-items/{item_id}";

function open(state: Por04State, over: Record<string, FixtureHandler> = {}): void {
  const scenario: Scenario = freshScenario(state);
  restore = installFixtureMode({ ...scenario, handlers: { ...scenario.handlers, ...over } });
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
}

describe("SPEC-031 AC-1", () => {
  it("test_ac1_the_client_sees_the_request_with_why_status_and_date", async () => {
    open("a");
    const box = await screen.findByRole("dialog");
    expect(
      await within(box).findByRole("heading", { name: "Form 1095-C From Mercer Hill Health" }),
    ).toBeTruthy();
    expect(within(box).getByText("Why we need it")).toBeTruthy();
    expect(within(box).getByText(/requested Feb 3/)).toBeTruthy();
  });

  it("test_ac1_no_text_on_the_sheet_is_attributed_to_an_agent", async () => {
    open("a");
    const box = await screen.findByRole("dialog");
    await within(box).findByText("Why we need it");
    expect(box.textContent).not.toMatch(/Agent|Accrued/);
  });
});

describe("SPEC-031 AC-2", () => {
  it("test_ac2_with_no_guidance_the_fields_are_empty_and_not_shown", async () => {
    open("a", { [SHEET]: () => json(sheet1095c({ guidance: null })) });
    const box = await screen.findByRole("dialog");
    await within(box).findByRole("heading", { name: "Form 1095-C From Mercer Hill Health" });
    expect(within(box).queryByText("Why we need it")).toBeNull();
  });
});

describe("SPEC-031 AC-4", () => {
  it("test_ac4_a_provided_item_shows_its_source_and_date_and_no_upload", async () => {
    open("c");
    const box = await screen.findByRole("dialog");
    expect(await within(box).findByText(/Received by email Sep 14/)).toBeTruthy();
    expect(within(box).queryByRole("button", { name: /Upload/ })).toBeNull();
  });
});

describe("SPEC-031 AC-5", () => {
  it("test_ac5_covered_and_needed_accounts_are_named_by_last_four", () => {
    const words = gapMessage({ covered: ["1111"], needed: ["2222"] });
    expect(words).toContain("1111");
    expect(words).toContain("2222");
  });

  it("test_ac5_with_nothing_needed_there_is_no_gap_line", () => {
    expect(gapMessage({ covered: ["1111"], needed: [] })).toBeNull();
  });
});

describe("SPEC-031 AC-6", () => {
  it("test_ac6_the_home_line_says_items_left_blockers_and_effort", () => {
    const line = yourPartMessage({ items_left: 4, blocks_fieldwork: 2, minutes: 120 });
    expect(line).toContain("4 left");
    expect(line).toContain("2 block fieldwork");
    expect(line).toContain("2 hours");
  });

  it("test_ac6_nothing_left_says_so", () => {
    expect(yourPartMessage({ items_left: 0, blocks_fieldwork: 0, minutes: 0 })).not.toMatch(/\d/);
  });
});

describe("SPEC-031 AC-7", () => {
  const base = {
    evidence_version_id: "v9",
    added_by: "client" as const,
    added_by_name: "Claire Feld",
    added_at: "2026-09-10T15:00:00Z",
  };

  it("test_ac7_a_send_back_shows_its_reason_label", () => {
    expect(outcomeLabel({ ...base, outcome: "sent_back", reason_label: "Unreadable" })).toContain(
      "Unreadable",
    );
  });

  it("test_ac7_a_rejection_shows_no_note", () => {
    expect(outcomeLabel({ ...base, outcome: "not_accepted" })).toBe("Not accepted");
  });

  it("test_ac7_the_sheet_shows_the_returned_version_with_the_reviewers_note", async () => {
    open("d");
    const box = await screen.findByRole("dialog");
    expect(await within(box).findByText(/Returned/)).toBeTruthy();
    expect(within(box).getByText("Feld_1095C_2024.pdf")).toBeTruthy();
  });
});

describe("SPEC-031 AC-9", () => {
  it("test_ac9_loading_shows_no_request_yet", async () => {
    open("a", { [SHEET]: () => never() });
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText("Why we need it")).toBeNull();
  });

  it("test_ac9_an_error_is_said_in_words", async () => {
    open("a", { [SHEET]: () => json({ message: "boom" }, 500) });
    const box = await screen.findByRole("dialog");
    expect(await within(box).findByRole("button", { name: /try again|retry/i })).toBeTruthy();
    expect(within(box).queryByText("Why we need it")).toBeNull();
  });

  it("test_ac9_not_allowed_shows_no_request", async () => {
    open("a", { [SHEET]: () => json({ detail: "not_found" }, 404) });
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText("Why we need it")).toBeNull();
  });
});
