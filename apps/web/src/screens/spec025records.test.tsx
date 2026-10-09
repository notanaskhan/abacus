// SPEC-025 (TASK-044): acceptance, the partner's conclusion, independence, the letter, the gate.
import type { SetupOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { errorMessage } from "../api";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { EngagementRecords } from "./EngagementRecords";
import { MyConfirmations } from "./MyConfirmations";

const E = "e1";
const ME = {
  user_id: "u-p",
  display_name: "Pat Partner",
  email: "p@firm.test",
  active_tenant_id: "t1",
  memberships: [{ tenant_id: "t1", firm_name: "Firm", firm_role: null, kind: "staff" }],
};

function setup(over: Partial<SetupOut> = {}): SetupOut {
  return {
    acceptance: null,
    letter: null,
    confirmations: [
      {
        user_id: "u-p",
        display_name: "Pat Partner",
        status: "requested",
        note: null,
        before_act_1: false,
        answered_at: null,
      },
      {
        user_id: "u-s",
        display_name: "Sam Staff",
        status: "declined",
        note: "Spouse works at the client",
        before_act_1: false,
        answered_at: "2026-10-09T10:00:00Z",
      },
    ],
    letter_required: false,
    blocked: "acceptance_missing",
    steps: [],
    summary: "",
    ...over,
  };
}

const records = (role: string | null): void => {
  renderRoutes([
    { path: "/", component: () => <EngagementRecords engagementId={E} role={role} /> },
  ]);
};

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("ac4 acceptance and the independence conclusion", () => {
  it("lets the partner record a new client's acceptance with the predecessor and conclusion", async () => {
    const { calls } = mockApi({
      "GET /v1/me": () => json(ME),
      [`GET /v1/engagements/${E}/setup`]: () => json(setup()),
      [`PUT /v1/engagements/${E}/acceptance`]: () => json(setup({ blocked: null })),
    });
    records("engagement_partner");
    const panel = (await screen.findByText("Acceptance and independence conclusion")).closest(
      "section",
    ) as HTMLElement;
    fireEvent.click(within(panel).getByRole("button", { name: "Record" }));
    fireEvent.change(screen.getByLabelText("Where it's documented"), {
      target: { value: "PPC 1-200" },
    });
    fireEvent.change(screen.getByLabelText("Predecessor auditor (optional)"), {
      target: { value: "Old & Co" },
    });
    fireEvent.change(screen.getByLabelText("Date communicated (optional)"), {
      target: { value: "2026-09-01" },
    });
    fireEvent.click(screen.getByLabelText(/I have concluded on compliance/));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(calls.find((c) => c.method === "PUT")?.body).toEqual({
        decision: "accepted",
        documented_at: "PPC 1-200",
        predecessor_auditor: "Old & Co",
        predecessor_communicated_on: "2026-09-01",
        independence_concluded: true,
      });
    });
  });

  it("shows others the record without a way to change it", async () => {
    mockApi({
      "GET /v1/me": () => json(ME),
      [`GET /v1/engagements/${E}/setup`]: () => json(setup()),
    });
    records("staff");
    expect(await screen.findByText(/Not recorded yet/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Record" })).toBeNull();
  });
});

describe("ac5 independence", () => {
  it("shows each person's state with decline notes, and lets me confirm", async () => {
    const { calls } = mockApi({
      "GET /v1/me": () => json(ME),
      [`GET /v1/engagements/${E}/setup`]: () => json(setup()),
      [`POST /v1/engagements/${E}/independence`]: () => json(setup()),
    });
    records("engagement_partner");
    const list = await screen.findByRole("list", { name: "Independence confirmations" });
    expect(within(list).getByText("Declined")).toBeTruthy();
    expect(within(list).getByText(/Spouse works at the client/)).toBeTruthy();
    expect(screen.getByText("0 of 2 confirmed")).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: "Confirm my independence" }));
    await waitFor(() => {
      expect(calls.find((c) => c.method === "POST")?.body).toEqual({ confirm: true });
    });
  });

  it("asks for a reason before declining from my confirmations card", async () => {
    const { calls } = mockApi({
      "GET /v1/firm/confirmations": () =>
        json([
          {
            engagement_id: E,
            engagement_name: "FY2026 audit",
            client_name: "Halvorsen",
            status: "requested",
            statement:
              "I confirm I am independent of Halvorsen for this engagement, under the firm's independence policy.",
          },
        ]),
      [`POST /v1/engagements/${E}/independence`]: () => json(setup()),
    });
    renderRoutes([{ path: "/", component: MyConfirmations }]);
    expect(await screen.findByText(/independent of Halvorsen/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "I can't confirm" }));
    const decline = screen.getByRole("button", { name: "Decline" });
    expect((decline as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/Why you can't confirm/), {
      target: { value: "Former employer" },
    });
    fireEvent.click(decline);
    await waitFor(() => {
      expect(calls.find((c) => c.method === "POST")?.body).toEqual({
        confirm: false,
        note: "Former employer",
      });
    });
  });
});

describe("ac6 the letter", () => {
  it("records a letter not required this year with its reason", async () => {
    const { calls } = mockApi({
      "GET /v1/me": () => json(ME),
      [`GET /v1/engagements/${E}/setup`]: () => json(setup()),
      [`PUT /v1/engagements/${E}/letter`]: () => json(setup()),
    });
    records("manager");
    const panel = (await screen.findByText("Engagement letter")).closest("section") as HTMLElement;
    fireEvent.click(within(panel).getByRole("button", { name: "Record" }));
    fireEvent.change(screen.getByLabelText("Status"), {
      target: { value: "not_required_this_year" },
    });
    fireEvent.change(screen.getByLabelText("Why not this year"), {
      target: { value: "Multi-year letter signed 2025" },
    });
    fireEvent.click(within(panel).getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(calls.find((c) => c.method === "PUT")?.body).toMatchObject({
        status: "not_required_this_year",
        reason: "Multi-year letter signed 2025",
      });
    });
  });
});

describe("ac7 the gate's reasons", () => {
  it("explains every refusal in plain words", () => {
    expect(errorMessage({ detail: "acceptance_missing" })).toMatch(/records acceptance/);
    expect(errorMessage({ detail: "independence_conclusion_missing" })).toMatch(
      /independence conclusion/,
    );
    expect(errorMessage({ detail: "acceptance_declined" })).toMatch(/declined/);
    expect(errorMessage({ detail: "letter_missing" })).toMatch(/engagement letter/);
  });
});
