// A-08-T32 (TASK-8545; DEC-5530): an API confirmation row becomes the log row the artboards draw,
// with the handoff's words, the API's dates and people, and the server's figures (never summed).
import type { ConfirmationRowOut } from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import { logRowOf } from "./live";

const NOW = new Date("2026-09-30T09:00:00-05:00");

const row = (over: Partial<ConfirmationRowOut>): ConfirmationRowOut => ({
  id: "00000000-0000-4000-8000-000000000c02",
  number: "C2",
  type: "accounts_receivable",
  respondent_org: "Summit Trail Outfitters",
  channel: "accrued_link",
  status: "responded",
  book_total: "412600.00",
  address_independent: true,
  authorization_on_file: false,
  sent_at: "2026-09-18T10:00:00-05:00",
  viewed_at: "2026-09-19T08:00:00-05:00",
  second_request_at: null,
  responded_at: "2026-09-25T11:00:00-05:00",
  sample_item_ref: null,
  allowed_actions: [],
  address_check: {
    method: "Customer master matched website and phone call",
    verified_by_name: "Cole Hart",
    verified_on: "2026-09-17",
  },
  confirmed_total: "412600.00",
  difference: "0.00",
  ...over,
});

describe("AUD-14 live rows", () => {
  it("draws C2 as the handoff does, figures as the server answers them", () => {
    expect(logRowOf(row({}), NOW)).toEqual({
      number: "C2",
      item: "Accounts receivable",
      respondent: "Summit Trail Outfitters",
      address: "Customer master matched website and phone call (CH, Sep 17)",
      channel: "Accrued link (POR-17)",
      sent: "Sep 18",
      response: "Sep 25",
      book: "412600.00",
      confirmed: "412600.00",
      difference: "0.00",
      status: "responded",
    });
  });

  it("an unanswered sent request reads No response with its newest follow-up", () => {
    const awaiting = row({
      number: "C4",
      status: "sent",
      responded_at: null,
      second_request_at: "2026-09-28T09:00:00-05:00",
      confirmed_total: null,
      difference: null,
    });
    const out = logRowOf(awaiting, NOW);
    expect(out.response).toBe("No response");
    expect(out.subLine).toBe("2nd request Sep 28");
    expect([out.confirmed, out.difference]).toEqual([null, null]);
    expect(logRowOf({ ...awaiting, second_request_at: null }, NOW).subLine).toBe("Viewed Sep 19");
  });

  it("a draft has no dates, no address check and the bank label", () => {
    const draft = logRowOf(
      row({
        type: "bank",
        status: "draft",
        channel: "network_recorded",
        sent_at: null,
        viewed_at: null,
        responded_at: null,
        address_check: null,
        confirmed_total: null,
        difference: null,
      }),
      NOW,
    );
    expect([draft.item, draft.channel, draft.sent, draft.response, draft.address]).toEqual([
      "Bank balances & debt",
      "Bank confirmation network",
      "",
      "",
      "",
    ]);
    expect(draft.subLine).toBeUndefined();
  });
});
