// SPEC-027 (TASK-051): due dates, drafted reminders at Advise, and the firm's time zone.
import type { DraftOut, RequestItemOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import type { JSX } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { json, mockApi, renderRoutes } from "../testing/support";
import { FirmTimeZone } from "./Autonomy";
import { DueDatesBar, ItemDue, effectiveDue, isOverdue } from "./DueDates";
import { ReminderDrafts } from "./ReminderDrafts";

const E = "e1";

function item(over: Partial<RequestItemOut> = {}): RequestItemOut {
  return {
    id: "i1",
    engagement_id: E,
    description: "Bank statements",
    audit_area: "Cash",
    status: "open",
    created_at: "2026-01-02T00:00:00Z",
    ...over,
  };
}

afterEach(cleanup);

function renderOne(component: () => JSX.Element): void {
  renderRoutes([{ path: "/", component }]);
}

describe("SPEC-027 due dates (TASK-051)", () => {
  it("test_ac9_an_item_is_due_on_its_own_date_else_the_list_s", () => {
    expect(effectiveDue(item({ due_on: "2026-03-01" }), "2026-02-01")).toBe("2026-03-01");
    expect(effectiveDue(item(), "2026-02-01")).toBe("2026-02-01");
    expect(effectiveDue(item(), null)).toBeNull();
    expect(isOverdue(item(), "2026-02-01", "2026-02-02")).toBe(true);
    expect(isOverdue(item({ status: "received" }), "2026-02-01", "2026-02-02")).toBe(false);
    expect(isOverdue(item(), "2026-02-01", "2026-02-01")).toBe(false);
  });

  it("test_ac9_the_list_default_is_saved_and_overdue_items_counted", async () => {
    const api = mockApi({
      [`GET /v1/engagements/${E}/request-items/default-due-date`]: () =>
        json({ due_on: "2020-01-01" }),
      [`PUT /v1/engagements/${E}/request-items/default-due-date`]: () =>
        json({ due_on: "2030-01-01" }),
    });
    renderOne(() => <DueDatesBar engagementId={E} items={[item(), item({ id: "i2" })]} />);
    expect(await screen.findByText("2 overdue")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Due date for the request list"), {
      target: { value: "2030-01-01" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(api.calls.find((c) => c.method === "PUT")?.body).toEqual({ due_on: "2030-01-01" });
    });
  });

  it("test_ac9_an_item_s_own_date_is_set", async () => {
    const api = mockApi({
      [`PUT /v1/engagements/${E}/request-items/due-dates`]: () => json([item()]),
    });
    renderOne(() => <ItemDue item={item()} fallback="2020-01-01" />);
    expect(await screen.findByText("List default: 2020-01-01")).toBeTruthy();
    expect(screen.getByText("Overdue")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Due date for Bank statements"), {
      target: { value: "2030-06-30" },
    });
    await waitFor(() => {
      expect(api.calls.find((c) => c.method === "PUT")?.body).toEqual({
        item_ids: ["i1"],
        due_on: "2030-06-30",
      });
    });
  });
});

describe("SPEC-027 drafted reminders (TASK-051)", () => {
  const DRAFT: DraftOut = {
    id: "r1",
    recipient_user_id: "u-c",
    recipient_name: "Rachel",
    items: [{ request_item_id: "i1", description: "Bank statements" }],
    created_at: "2026-10-12T13:00:00Z",
  };

  it("test_ac4_a_person_sends_a_draft_with_a_note", async () => {
    let drafts = [DRAFT];
    const api = mockApi({
      [`GET /v1/engagements/${E}/reminders`]: () => json(drafts),
      [`POST /v1/engagements/${E}/reminders/r1/send`]: () => {
        drafts = [];
        return json({ id: "r1" });
      },
    });
    renderOne(() => <ReminderDrafts engagementId={E} />);
    expect(await screen.findByText("To Rachel")).toBeTruthy();
    expect(screen.getByText("Bank statements")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("A note for Rachel (optional)"), {
      target: { value: "Thanks!" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => {
      expect(screen.queryByText("To Rachel")).toBeNull();
    });
    expect(api.calls.find((c) => c.method === "POST")?.body).toEqual({ note: "Thanks!" });
  });

  it("test_ac4_a_draft_can_be_dismissed_and_nothing_shows_without_drafts", async () => {
    const api = mockApi({
      [`GET /v1/engagements/${E}/reminders`]: () => json([DRAFT]),
      [`POST /v1/engagements/${E}/reminders/r1/dismiss`]: () => json({ id: "r1" }),
    });
    renderOne(() => <ReminderDrafts engagementId={E} />);
    fireEvent.click(await screen.findByRole("button", { name: "Dismiss" }));
    await waitFor(() => {
      expect(api.calls.some((c) => c.path.endsWith("/dismiss"))).toBe(true);
    });
    cleanup();
    mockApi({ [`GET /v1/engagements/${E}/reminders`]: () => json([]) });
    renderOne(() => <ReminderDrafts engagementId={E} />);
    await waitFor(() => {
      expect(screen.queryByText("Reminders waiting for you")).toBeNull();
    });
  });
});

describe("SPEC-027 firm time zone (TASK-051)", () => {
  it("test_q3_the_firm_admin_sets_the_time_zone", async () => {
    const api = mockApi({
      "GET /v1/firm/time-zone": () => json({ time_zone: "America/New_York" }),
      "PUT /v1/firm/time-zone": () => json({ time_zone: "America/Chicago" }),
    });
    renderOne(() => <FirmTimeZone canSet />);
    const select = await screen.findByRole("combobox");
    fireEvent.change(select, { target: { value: "America/Chicago" } });
    await waitFor(() => {
      expect(api.calls.find((c) => c.method === "PUT")?.body).toEqual({
        time_zone: "America/Chicago",
      });
    });
  });
});
