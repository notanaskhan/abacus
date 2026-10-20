// TASK-102: the Home queue joins fieldwork, review and overdue counts with engagement names,
// approvals first.
import { describe, expect, it } from "vitest";
import { queueRows } from "./queue";

const NAMES = [
  { id: "e1", name: "FY26 audit", client_name: "Acme" },
  { id: "e2", name: "FY26 review", client_name: "Beta" },
];

describe("queueRows", () => {
  it("puts sample approvals first, then reviews, then overdue items", () => {
    const rows = queueRows(
      [
        {
          engagement_id: "e1",
          procedure_id: "p1",
          definition: "journal_entry_testing",
          kind: "prepare_rows",
          count: 3,
        },
        {
          engagement_id: "e2",
          procedure_id: "p2",
          definition: "unrecorded_liabilities",
          kind: "approve_sample",
          count: 14,
        },
      ],
      [{ engagement_id: "e1", count: 2 }],
      [{ engagement_id: "e2", count: 5 }],
      NAMES,
    );
    expect(rows.map((r) => r.action)).toEqual(["Approve", "Decide", "Sign off", "Follow up"]);
    expect(rows[0]?.what).toBe(
      "Approve the sample for the search for unrecorded liabilities (14 items)",
    );
    expect(rows[0]?.engagement).toBe("FY26 review");
    expect(rows[1]?.what).toBe("Decide 2 pieces of evidence");
    expect(rows[3]?.what).toBe("5 client items are past due");
  });

  it("words one of something in the singular", () => {
    const [row] = queueRows(
      [
        {
          engagement_id: "e1",
          procedure_id: "p1",
          definition: "journal_entry_testing",
          kind: "review_rows",
          count: 1,
        },
      ],
      [],
      [],
      NAMES,
    );
    expect(row?.what).toBe("Review 1 row of journal entry testing");
    expect(row?.to).toBe("fieldwork");
  });
});
