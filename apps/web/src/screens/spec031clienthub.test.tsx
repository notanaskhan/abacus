// SPEC-031 AC-1, AC-3 to AC-7, AC-9 (TASK-061): the client's request detail, history and your
// part; the firm's guidance editing; the send-back dialog's notice.
import type { ClientViewOut, EngagementOut, RequestItemOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { ClientEngagement } from "./ClientEngagement";
import { ClientGuidance } from "./ClientGuidance";
import { DecisionActions } from "./DecisionActions";
import { estimate, gapMessage, outcomeLabel, yourPartMessage } from "./clientHubMessages";

const E = "e1";
const ITEMS = `/v1/engagements/${E}/request-items`;
const VIEW = `${ITEMS}/i1/client-view`;
const ENGAGEMENT = {
  id: E,
  name: "FY2026 audit",
  client_name: "Northwind",
  fiscal_period_start: "2026-01-01",
  fiscal_period_end: "2026-12-31",
} as unknown as EngagementOut;

function item(over: Partial<RequestItemOut> = {}): RequestItemOut {
  return {
    id: "i1",
    engagement_id: E,
    description: "Bank statements for December",
    audit_area: "Cash",
    status: "open",
    created_at: "2026-10-01T00:00:00Z",
    ...over,
  };
}

const NO_VIEW: ClientViewOut = { provided: null, gap: null, history: [] };

function page(items: RequestItemOut[], view: ClientViewOut = NO_VIEW, extra = {}): void {
  mockApi({
    [`GET /v1/engagements/${E}`]: () => json(ENGAGEMENT),
    [`GET ${ITEMS}`]: () => json(items),
    [`GET /v1/engagements/${E}/client-contacts`]: () => json({ detail: "forbidden" }, 403),
    [`GET ${VIEW}`]: () => json(view),
    [`GET ${ITEMS}/i2/client-view`]: () => json(NO_VIEW),
    ...extra,
  });
  renderRoutes([{ path: "/", component: () => <ClientEngagement engagementId={E} /> }]);
}

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("ac1 the client's request", () => {
  it("shows why, what good looks like, still needed and the due date", async () => {
    page([
      item({
        why: "To confirm cash",
        good_looks_like: "The bank's PDF",
        still_needed: "The payroll account",
        due_on: "2027-01-15",
      }),
    ]);
    expect(await screen.findByText("To confirm cash")).toBeTruthy();
    expect(screen.getByText("What good looks like")).toBeTruthy();
    expect(screen.getByText("The payroll account")).toBeTruthy();
    expect(screen.getByText("Due January 15, 2027")).toBeTruthy();
  });

  it("shows no guidance headings when there's none", async () => {
    page([item()]);
    expect(await screen.findByText("Bank statements for December")).toBeTruthy();
    expect(screen.queryByText("Why we need it")).toBeNull();
  });

  it("lists items that block fieldwork first, marked", async () => {
    page([item({ id: "i2", description: "Second" }), item({ blocks_fieldwork: true })]);
    const rows = await screen.findAllByRole("listitem");
    await waitFor(() => {
      expect(within(rows[0] as HTMLElement).queryByText("Blocks fieldwork")).toBeTruthy();
    });
  });
});

describe("ac4 provided", () => {
  it("says where it came from and asks for no upload", async () => {
    page([item({ status: "received" })], {
      ...NO_VIEW,
      provided: { source: "export", on: "2026-10-05T12:00:00Z" },
    });
    expect(
      await screen.findByText("Provided from your export of October 5, 2026. Nothing to do here."),
    ).toBeTruthy();
    expect(screen.queryByLabelText(/Upload files for/)).toBeNull();
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

  it("shows the gap on the request", async () => {
    page([item({ document_kind: "bank_statement" })], {
      ...NO_VIEW,
      gap: { covered: ["2290"], needed: ["4471"] },
    });
    expect(
      await screen.findByText(
        "We have statements for account ending 2290; we still need account ending 4471.",
      ),
    ).toBeTruthy();
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
    page(
      [item({ status: "needs_revision" })],
      {
        provided: null,
        gap: null,
        history: [
          { ...entry, outcome: "sent_back", reason_label: "Wrong period", note: "Need December" },
          {
            evidence_version_id: "v0",
            added_by: "firm",
            added_by_name: "",
            added_at: "2026-10-01T10:00:00Z",
            outcome: "replaced",
          },
        ],
      },
      {
        [`GET ${ITEMS}/i1/uploads`]: () =>
          json([
            {
              evidence_version_id: "v1",
              file_name: "nov.pdf",
              media_type: "application/pdf",
              size_bytes: 3,
              uploaded_by: "u",
              uploaded_by_name: "Cara",
              uploaded_at: "2026-10-09T10:00:00Z",
            },
          ]),
        [`GET ${ITEMS}/i1/uploads/v1/checks`]: () => json([]),
      },
    );
    fireEvent.click(await screen.findByRole("button", { name: "Show history" }));
    const list = await screen.findByRole("list", { name: "Uploaded files" });
    expect(await within(list).findByText("Sent back: Wrong period")).toBeTruthy();
    expect(within(list).getByText("“Need December”")).toBeTruthy();
    expect(within(list).getByText("Provided from your records")).toBeTruthy();
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

describe("ac3 firm guidance", () => {
  const firmItem = item({
    why: "To confirm cash",
    guidance_source: "kind_default",
    document_kind: "bank_statement",
    effort: "small",
  });

  it("shows the source and no Edit for roles that can't edit", () => {
    mockApi({});
    renderRoutes([
      {
        path: "/",
        component: () => <ClientGuidance engagementId={E} item={firmItem} canEdit={false} />,
      },
    ]);
    return screen.findByText(/Default for bank statements/).then(() => {
      expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
    });
  });

  it("saves the edit for partner, manager and senior", async () => {
    const { calls } = mockApi({
      [`PUT ${ITEMS}/i1/guidance`]: () => json({ ...firmItem, guidance_source: "firm" }),
    });
    renderRoutes([
      { path: "/", component: () => <ClientGuidance engagementId={E} item={firmItem} canEdit /> },
    ]);
    fireEvent.click(await screen.findByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByLabelText("Still needed"), { target: { value: "Payroll" } });
    fireEvent.click(screen.getByLabelText("Blocks fieldwork"));
    fireEvent.change(screen.getByLabelText("Effort for the client"), {
      target: { value: "large" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(calls.find((c) => c.method === "PUT")?.body).toEqual({
        why: "To confirm cash",
        good_looks_like: null,
        still_needed: "Payroll",
        blocks_fieldwork: true,
        effort: "large",
      });
    });
  });

  it("shows an error when the save fails", async () => {
    mockApi({ [`PUT ${ITEMS}/i1/guidance`]: () => json({ detail: "forbidden" }, 403) });
    renderRoutes([
      { path: "/", component: () => <ClientGuidance engagementId={E} item={firmItem} canEdit /> },
    ]);
    fireEvent.click(await screen.findByRole("button", { name: "Edit" }));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Couldn't save the guidance")).toBeTruthy();
  });
});

describe("send-back notice", () => {
  it("tells the reviewer who reads the note", async () => {
    mockApi({
      [`GET /v1/engagements/${E}/review-reason-codes/send_back`]: () => json([]),
      [`GET /v1/engagements/${E}/review-reason-codes/reject`]: () => json([]),
    });
    renderRoutes([
      {
        path: "/",
        component: () => (
          <DecisionActions
            engagementId={E}
            versionId="v1"
            itemLabel="Bank"
            seenProposal={null}
            onSettled={() => undefined}
          />
        ),
      },
    ]);
    const select = await screen.findByDisplayValue("Accept");
    fireEvent.change(select, { target: { value: "send_back" } });
    expect(await screen.findByText("The client will see this note.")).toBeTruthy();
    fireEvent.change(select, { target: { value: "reject" } });
    expect(await screen.findByText("Only your team sees this note.")).toBeTruthy();
  });
});
