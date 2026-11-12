// T-04-T29 (TASK-6828): the review workspace's live hosts against the generated client, each
// write's body as the contract names it, and every refusal in words. Row: "Kevin approves
// documents, Samuel edits a field with a reason and signs off a section, counts update on a second
// tab within 2 s, and every 409 renders its blocker in words."
import { client } from "@abacus/api-client/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { JSX } from "react";
import { toast } from "@abacus/ui";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { type FixtureHandler, installFixtureMode, json } from "../../app-core/fixture-mode";
import { RealtimeClient, type RealtimeEvent } from "../../app-core/realtime";
import { newQueryClient } from "../../testing/support";
import { WorksheetsLive } from "../TAX-05/live";
import { IssuesLive } from "../TAX-06/live";
import { ActivityLive } from "../TAX-07/live";
import { ReviewLive } from "./live";
import { BLOCKER_COPY, blockerWords, RETURN_LIVE_KEYS } from "./live-core";

const RETURN = "11111111-1111-4111-8111-111111111111";
const ENGAGEMENT = "22222222-2222-4222-8222-222222222222";
const DOC = "33333333-3333-4333-8333-333333333333";
const SHEET = "44444444-4444-4444-8444-444444444444";
const SECTION = "55555555-5555-4555-8555-555555555555";
const ISSUE = "66666666-6666-4666-8666-666666666666";

interface Call {
  key: string;
  body: unknown;
  query: string;
}

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function serve(handlers: Record<string, FixtureHandler>, calls: Call[] = []): Call[] {
  const wrapped = Object.fromEntries(
    Object.entries<FixtureHandler>({
      "GET /v1/me/capabilities": () => json({ flags: {}, entitlements: [] }),
      ...handlers,
    }).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({ key, body: request.body, query: request.query.toString() });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ state: "live", persona: "kevin-park", handlers: wrapped });
  return calls;
}

function mount(node: JSX.Element, queryClient: QueryClient = newQueryClient()): void {
  render(<QueryClientProvider client={queryClient}>{node}</QueryClientProvider>);
}

const summary = (over: Record<string, unknown> = {}) => ({
  return_id: RETURN,
  review_count: 2,
  viewer_level: "preparer",
  issues_open: 1,
  checkpoints_proposed: 0,
  assistant: "agents_off",
  allowed_actions: ["document.approve"],
  ...over,
});

const doc = (approval: "unapproved" | "approved" | "mismatch") => ({
  evidence_version_id: DOC,
  title: "Ridgeline Partners K-1",
  category: "K-1s",
  approval,
  approvals_count: approval === "approved" ? 1 : 0,
  version: 3,
});

describe("blockerWords", () => {
  it("names each final-approval blocker in words, in the server's order", () => {
    expect(
      blockerWords({
        detail: "final_approval_blocked",
        facts: { blockers: "draft_k1,blocking_issues" },
      }),
    ).toEqual([BLOCKER_COPY.draft_k1, BLOCKER_COPY.blocking_issues]);
  });

  it("reads each refusal code as a sentence, and an unknown one as the generic sentence", () => {
    expect(blockerWords({ detail: "level_not_permitted" })).toEqual([
      BLOCKER_COPY.level_not_permitted,
    ]);
    expect(blockerWords({ detail: "version_superseded" })).toEqual([
      BLOCKER_COPY.version_superseded,
    ]);
    expect(blockerWords({ detail: "field_changed" })).toEqual([BLOCKER_COPY.field_changed]);
    expect(blockerWords({ detail: "mismatch", facts: { field_key: "div.halvard.1a" } })).toEqual([
      "Resolve 1 mismatch to approve",
    ]);
    expect(blockerWords({ detail: "no_such_code" })).toEqual([BLOCKER_COPY.generic]);
    expect(blockerWords(undefined)).toEqual([BLOCKER_COPY.generic]);
  });

  it("never shows a code", () => {
    for (const code of ["mismatch", "issue_changed", "content_changed", "undo_window_closed"]) {
      for (const words of blockerWords({ detail: code })) expect(words).not.toContain("_");
    }
  });
});

describe("TAX-04 Review (live)", () => {
  it("Kevin approves at his level with the version he saw, then may unapprove it", async () => {
    let approved = false;
    const calls = serve({
      "GET /v1/tax/returns/{return_id}/workspace": () => json(summary()),
      "GET /v1/tax/returns/{return_id}/review-tree": () =>
        json({ items: [doc(approved ? "approved" : "unapproved")], total: 1, review_count: 1 }),
      "POST /v1/tax/returns/{return_id}/document-approvals": () => {
        approved = true;
        return json(
          {
            id: "a1",
            evidence_version_id: DOC,
            level: "preparer",
            approved_by_name: "Kevin Park",
            approved_at: "2026-09-14T09:00:00Z",
          },
          201,
        );
      },
      "POST /v1/tax/document-approvals/{approval_id}/reverse": () => {
        approved = false;
        return json({
          id: "a1",
          evidence_version_id: DOC,
          level: "preparer",
          approved_by_name: "Kevin Park",
          approved_at: "2026-09-14T09:00:00Z",
          reversed: true,
        });
      },
    });
    mount(<ReviewLive returnId={RETURN} engagementId={ENGAGEMENT} />);
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    await screen.findByRole("button", { name: "Unapprove" });
    const post = calls.find((c) => c.key.endsWith("/document-approvals"));
    expect(post?.body).toEqual({ evidence_version_id: DOC, level: "preparer", seen_version: 3 });
    fireEvent.click(screen.getByRole("button", { name: "Unapprove" }));
    await screen.findByRole("button", { name: "Approve" });
    expect(calls.some((c) => c.key.endsWith("/reverse"))).toBe(true);
  });

  it("an approval's toast offers Undo for 10 s, and Undo posts the reversal (DEC-24)", async () => {
    const undoable = vi.spyOn(toast, "undoable");
    let approved = false;
    const calls = serve({
      "GET /v1/tax/returns/{return_id}/workspace": () => json(summary()),
      "GET /v1/tax/returns/{return_id}/review-tree": () =>
        json({ items: [doc(approved ? "approved" : "unapproved")], total: 1, review_count: 1 }),
      "POST /v1/tax/returns/{return_id}/document-approvals": () => {
        approved = true;
        return json(
          {
            id: "a1",
            evidence_version_id: DOC,
            level: "preparer",
            approved_by_name: "Kevin Park",
            approved_at: "2026-09-14T09:00:00Z",
          },
          201,
        );
      },
      "POST /v1/tax/document-approvals/{approval_id}/reverse": () => {
        approved = false;
        return json({
          id: "a1",
          evidence_version_id: DOC,
          level: "preparer",
          approved_by_name: "Kevin Park",
          approved_at: "2026-09-14T09:00:00Z",
          reversed: true,
        });
      },
    });
    mount(<ReviewLive returnId={RETURN} engagementId={ENGAGEMENT} />);
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    await waitFor(() => {
      expect(undoable).toHaveBeenCalledTimes(1);
    });
    const offered = undoable.mock.calls[0]?.[0];
    expect(offered?.text).toBe("Document approved");
    expect(offered?.undo).toBeTypeOf("function");
    offered?.undo?.();
    await waitFor(() => {
      expect(calls.some((c) => c.key.endsWith("/reverse"))).toBe(true);
    });
    undoable.mockRestore();
  });

  it("a 409 renders its blocker in words, and nothing moves", async () => {
    serve({
      "GET /v1/tax/returns/{return_id}/workspace": () => json(summary()),
      "GET /v1/tax/returns/{return_id}/review-tree": () =>
        json({ items: [doc("unapproved")], total: 1, review_count: 1 }),
      "POST /v1/tax/returns/{return_id}/document-approvals": () =>
        json({ detail: "version_superseded" }, 409),
    });
    mount(<ReviewLive returnId={RETURN} engagementId={ENGAGEMENT} />);
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    expect((await screen.findByRole("alert")).textContent).toBe(BLOCKER_COPY.version_superseded);
    expect(screen.queryByRole("button", { name: "Unapprove" })).toBeNull();
  });

  it("a mismatch disables Approve with the handoff's helper", async () => {
    serve({
      "GET /v1/tax/returns/{return_id}/workspace": () => json(summary()),
      "GET /v1/tax/returns/{return_id}/review-tree": () =>
        json({ items: [doc("mismatch")], total: 1, review_count: 1 }),
    });
    mount(<ReviewLive returnId={RETURN} engagementId={ENGAGEMENT} />);
    const approve = await screen.findByRole("button", { name: "Approve" });
    expect((approve as HTMLButtonElement).disabled).toBe(true);
    expect(document.querySelector("[data-mismatch-helper]")?.textContent).toBe(
      "Resolve 1 mismatch to approve",
    );
  });

  it("a viewer without document.approve sees no Approve", async () => {
    serve({
      "GET /v1/tax/returns/{return_id}/workspace": () => json(summary({ allowed_actions: [] })),
      "GET /v1/tax/returns/{return_id}/review-tree": () =>
        json({ items: [doc("unapproved")], total: 1, review_count: 1 }),
    });
    mount(<ReviewLive returnId={RETURN} engagementId={ENGAGEMENT} />);
    await screen.findByText("Ridgeline Partners K-1");
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  });

  // TASK-7322: the tree names the live approval at the viewer's level, so Unapprove reaches one
  // made in another session (or by a colleague at the same level), not only one made here.
  it("Unapprove reaches the tree's live approval, made in another session", async () => {
    let approved = true;
    const calls = serve({
      "GET /v1/tax/returns/{return_id}/workspace": () => json(summary()),
      "GET /v1/tax/returns/{return_id}/review-tree": () =>
        json({
          items: [
            { ...doc(approved ? "approved" : "unapproved"), approval_id: approved ? "a9" : null },
          ],
          total: 1,
          review_count: approved ? 0 : 1,
        }),
      "POST /v1/tax/document-approvals/{approval_id}/reverse": () => {
        approved = false;
        return json({
          id: "a9",
          evidence_version_id: DOC,
          level: "preparer",
          approved_by_name: "Kevin Park",
          approved_at: "2026-09-13T16:00:00Z",
          reversed: true,
        });
      },
    });
    mount(<ReviewLive returnId={RETURN} engagementId={ENGAGEMENT} />);
    fireEvent.click(await screen.findByRole("button", { name: "Unapprove" }));
    await screen.findByRole("button", { name: "Approve" });
    const reversed = calls.find((c) => c.key.endsWith("/reverse"));
    expect(reversed?.body).toEqual({});
    expect(calls.filter((c) => c.key.endsWith("/reverse"))).toHaveLength(1);
  });

  it("an approved document without document.approve offers no Unapprove", async () => {
    serve({
      "GET /v1/tax/returns/{return_id}/workspace": () => json(summary({ allowed_actions: [] })),
      "GET /v1/tax/returns/{return_id}/review-tree": () =>
        json({ items: [{ ...doc("approved"), approval_id: "a9" }], total: 1, review_count: 0 }),
    });
    mount(<ReviewLive returnId={RETURN} engagementId={ENGAGEMENT} />);
    await screen.findByText("Ridgeline Partners K-1");
    expect(screen.queryByRole("button", { name: "Unapprove" })).toBeNull();
  });
});

// TASK-7322 (TAX-05 e; SHL-12's level line): with nothing left to review, the request goes to
// BH-TAX-02's signer, whom the server names; the person confirms it, and a refusal is in words.
describe("TAX-04 Review (live): Request final approval", () => {
  const DANIEL = "77777777-7777-4777-8777-777777777777";
  const done = () =>
    json({ items: [{ ...doc("approved"), approval_id: "a1" }], total: 1, review_count: 0 });
  const staff = () =>
    json({
      members: [
        {
          user_id: DANIEL,
          display_name: "Daniel Reyes",
          email: "daniel@brightwaterhale.test",
          firm_role: null,
          status: "active",
        },
      ],
    });
  const asking = (over: Record<string, unknown> = {}) =>
    summary({
      review_count: 0,
      viewer_level: "manager",
      allowed_actions: ["document.approve", "tax_return.request_approval"],
      final_approver_user_id: DANIEL,
      ...over,
    });

  it("names the signer, and the person's confirm posts the request to them", async () => {
    const shown = vi.spyOn(toast, "show");
    const calls = serve({
      "GET /v1/tax/returns/{return_id}/workspace": () => json(asking()),
      "GET /v1/tax/returns/{return_id}/review-tree": done,
      "GET /v1/firm/staff": staff,
      "POST /v1/tax/returns/{return_id}/final-approval-requests": () =>
        json({ gate_id: "g1", requested_at: "2026-09-14T10:00:00Z" }, 201),
    });
    mount(<ReviewLive returnId={RETURN} engagementId={ENGAGEMENT} />);
    fireEvent.click(await screen.findByRole("button", { name: "Request final approval…" }));
    await screen.findByText("Partner · final approval (BH-TAX-02)");
    await screen.findByText("Assignee · Daniel Reyes");
    expect(calls.some((c) => c.key.endsWith("/final-approval-requests"))).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Request final approval" }));
    await waitFor(() => {
      expect(calls.find((c) => c.key.endsWith("/final-approval-requests"))?.body).toEqual({
        assignee_user_id: DANIEL,
      });
    });
    await waitFor(() => {
      expect(shown).toHaveBeenCalledWith({ text: "Final approval requested" });
    });
    shown.mockRestore();
  });

  it("is disabled while the K-1 is a draft, and says why", async () => {
    serve({
      "GET /v1/tax/returns/{return_id}/workspace": () =>
        json(asking({ k1_dependency: "draft_pre_release" })),
      "GET /v1/tax/returns/{return_id}/review-tree": done,
      "GET /v1/firm/staff": staff,
    });
    mount(<ReviewLive returnId={RETURN} engagementId={ENGAGEMENT} />);
    const button = await screen.findByRole("button", { name: "Request final approval…" });
    expect((button as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(BLOCKER_COPY.draft_k1)).toBeTruthy();
  });

  it("with no signer named in BH-TAX-02 it is disabled and says so", async () => {
    serve({
      "GET /v1/tax/returns/{return_id}/workspace": () =>
        json(asking({ final_approver_user_id: null })),
      "GET /v1/tax/returns/{return_id}/review-tree": done,
      "GET /v1/firm/staff": staff,
    });
    mount(<ReviewLive returnId={RETURN} engagementId={ENGAGEMENT} />);
    const button = await screen.findByRole("button", { name: "Request final approval…" });
    expect((button as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("No partner is named for this client in BH-TAX-02.")).toBeTruthy();
  });

  it("a refusal names its blockers in words", async () => {
    serve({
      "GET /v1/tax/returns/{return_id}/workspace": () => json(asking()),
      "GET /v1/tax/returns/{return_id}/review-tree": done,
      "GET /v1/firm/staff": staff,
      "POST /v1/tax/returns/{return_id}/final-approval-requests": () =>
        json({ detail: "final_approval_blocked", facts: { blockers: "blocking_issues" } }, 409),
    });
    mount(<ReviewLive returnId={RETURN} engagementId={ENGAGEMENT} />);
    fireEvent.click(await screen.findByRole("button", { name: "Request final approval…" }));
    fireEvent.click(await screen.findByRole("button", { name: "Request final approval" }));
    expect((await screen.findByRole("alert")).textContent).toBe(BLOCKER_COPY.blocking_issues);
  });

  it("is not offered without the request action", async () => {
    serve({
      "GET /v1/tax/returns/{return_id}/workspace": () =>
        json(asking({ allowed_actions: ["document.approve"] })),
      "GET /v1/tax/returns/{return_id}/review-tree": done,
      "GET /v1/firm/staff": staff,
    });
    mount(<ReviewLive returnId={RETURN} engagementId={ENGAGEMENT} />);
    await screen.findByText("Ridgeline Partners K-1");
    expect(screen.queryByRole("button", { name: "Request final approval…" })).toBeNull();
  });

  it("is not offered while a document still needs review", async () => {
    serve({
      "GET /v1/tax/returns/{return_id}/workspace": () => json(asking({ review_count: 1 })),
      "GET /v1/tax/returns/{return_id}/review-tree": () =>
        json({ items: [doc("unapproved")], total: 1, review_count: 1 }),
      "GET /v1/firm/staff": staff,
    });
    mount(<ReviewLive returnId={RETURN} engagementId={ENGAGEMENT} />);
    await screen.findByRole("button", { name: "Approve" });
    expect(screen.queryByRole("button", { name: "Request final approval…" })).toBeNull();
  });
});

describe("TAX-05 / TXI-01 Worksheets (live)", () => {
  const fields = (value: string) => ({
    worksheet_id: SHEET,
    sections: [
      {
        key: "income",
        title: "Income",
        section_id: SECTION,
        fields: [
          {
            field_key: "l2a",
            label: "2a Tax-exempt interest",
            value,
            state: "imported",
            seen_seq: 4,
          },
          {
            field_key: "l11",
            label: "11 Adjusted gross income",
            value: "598030.00", // the API's Decimal string (MaybeMoney)
            state: "imported",
            seen_seq: 2,
            engine_label: "CCH",
          },
        ],
      },
    ],
  });

  it("Samuel edits a field only with a reason; the edit carries the version he saw", async () => {
    let value = "0";
    const calls = serve({
      "GET /v1/tax/returns/{return_id}/worksheets": () =>
        json({ items: [{ worksheet_id: SHEET, title: "Form 1040", group: "Federal" }] }),
      "GET /v1/tax/worksheets/{worksheet_id}/fields": () => json(fields(value)),
      "PUT /v1/fields/{target_type}/{target_id}/{field_key}/value": () => {
        value = "1550.00"; // the API's Decimal string
        return json({ ok: true });
      },
    });
    mount(<WorksheetsLive returnId={RETURN} engagementId={ENGAGEMENT} />);
    const edits = await screen.findAllByRole("button", { name: "Edit" });
    expect(edits).toHaveLength(1); // the engine line is read-only
    fireEvent.click(edits[0] as HTMLElement);
    fireEvent.change(screen.getByLabelText("2a Tax-exempt interest"), {
      target: { value: "1550" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect((await screen.findByRole("alert")).textContent).toBe("A reason is required.");
    expect(calls.some((c) => c.key.startsWith("PUT"))).toBe(false);
    fireEvent.change(screen.getByLabelText("Reason for the change"), {
      target: { value: "K-1 box 18A" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText("1,550");
    const put = calls.find((c) => c.key.startsWith("PUT"));
    expect(put?.body).toEqual({
      value: { t: "decimal", v: "1550" },
      seen_seq: 4,
      citation_note: "K-1 box 18A",
    });
  });

  it("a stale edit reads in words; a section offers its sign-off", async () => {
    serve({
      "GET /v1/tax/returns/{return_id}/worksheets": () =>
        json({ items: [{ worksheet_id: SHEET, title: "Form 1040", group: "Federal" }] }),
      "GET /v1/tax/worksheets/{worksheet_id}/fields": () => json(fields("0")),
      "PUT /v1/fields/{target_type}/{target_id}/{field_key}/value": () =>
        json({ detail: "field_changed" }, 409),
    });
    mount(<WorksheetsLive returnId={RETURN} engagementId={ENGAGEMENT} />);
    expect(await screen.findByRole("button", { name: "Sign off…" })).toBeTruthy();
    // TASK-7324: the API's Decimal string reads as the form's grouped whole dollars.
    expect(screen.getByText("598,030")).toBeTruthy();
    expect(screen.queryByText("598030.00")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByLabelText("Reason for the change"), {
      target: { value: "typo" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect((await screen.findByRole("alert")).textContent).toBe(BLOCKER_COPY.field_changed);
  });
});

describe("TAX-06 Issues (live)", () => {
  const item = (status: string) => ({
    id: ISSUE,
    kind: "review_point",
    priority: "high",
    status,
    version: 2,
    allowed_actions: ["issue.update", "issue.resolve"],
    assignee_agent: false,
    assignee_name: "Samuel Ito",
    assignee_user_id: null,
    blocks: ["final_approval"],
    created_at: "2026-09-14T09:00:00Z",
    engagement_id: ENGAGEMENT,
    instructions_required: false,
    link_count: 0,
    record: { type: "tax_return", id: RETURN },
    work_item_id: RETURN,
  });
  const detail = (status: string) => ({
    issue: item(status),
    title: "18A tax-exempt interest is not on the return",
    links: [],
    events: [],
    explanations: [],
    fix_instructions: null,
    fix_run: null,
    internal_note: null,
    client_wording: null,
    client_contact: null,
    record_label: "2025 Form 1040",
    request_item_id: null,
    suggestion: null,
  });

  it("the queue reads each issue's title; resolving needs a note and the version seen", async () => {
    let status = "open";
    const calls = serve({
      "GET /v1/issues": () => json({ items: [item(status)], total: 1 }),
      "GET /v1/issues/{issue_id}": () => json(detail(status)),
      "POST /v1/issues/{issue_id}/resolve": () => {
        status = "resolved";
        return json(detail(status));
      },
    });
    mount(<IssuesLive returnId={RETURN} engagementId={ENGAGEMENT} />);
    expect(
      (await screen.findAllByText("18A tax-exempt interest is not on the return")).length,
    ).toBeGreaterThan(0);
    const list = calls.find((c) => c.key === "GET /v1/issues");
    expect(list?.query).toContain("record_type=tax_return");
    expect(list?.query).toContain(`record_id=${RETURN}`);
    const resolve = await screen.findByRole("button", { name: /Mark as Resolved/ });
    expect((resolve as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Resolution note"), {
      target: { value: "Added to 2a" },
    });
    fireEvent.click(resolve);
    await waitFor(() => {
      expect(calls.some((c) => c.key.endsWith("/resolve"))).toBe(true);
    });
    expect(calls.find((c) => c.key.endsWith("/resolve"))?.body).toEqual({
      seen_version: 2,
      note: "Added to 2a",
    });
  });

  it("an explanation is agent text: markup renders as text, never as HTML", async () => {
    serve({
      "GET /v1/issues": () => json({ items: [item("open")], total: 1 }),
      "GET /v1/issues/{issue_id}": () =>
        json({
          ...detail("open"),
          explanations: [
            {
              id: "x1",
              agent_run_id: "r1",
              citations: [],
              explained_at: "2026-09-14T09:00:00Z",
              pinned: false,
              text: '<img src="x" onerror="alert(1)"> The 18A box is not on line 2a.',
            },
          ],
        }),
    });
    mount(<IssuesLive returnId={RETURN} engagementId={ENGAGEMENT} />);
    await waitFor(() => {
      expect(document.querySelector("[data-explanation]")).not.toBeNull();
    });
    expect(document.querySelector("[data-explanation] img")).toBeNull();
  });

  it("a system-only issue's refusal reads in words", async () => {
    serve({
      "GET /v1/issues": () => json({ items: [item("open")], total: 1 }),
      "GET /v1/issues/{issue_id}": () => json(detail("open")),
      "POST /v1/issues/{issue_id}/resolve": () => json({ detail: "system_resolved_only" }, 409),
    });
    mount(<IssuesLive returnId={RETURN} engagementId={ENGAGEMENT} />);
    fireEvent.change(await screen.findByLabelText("Resolution note"), {
      target: { value: "done" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Mark as Resolved/ }));
    expect((await screen.findByRole("alert")).textContent).toBe(BLOCKER_COPY.system_resolved_only);
  });
});

describe("TAX-07 Activity (live)", () => {
  it("reads the return's activity by work item and names an agent's person via Agent", async () => {
    const calls = serve({
      "GET /v1/checkpoints": () =>
        json({
          items: [],
          total: 0,
          filter: "all",
          allowed_actions: [],
          current_checkpoint_id: null,
          target_id: RETURN,
          target_type: "tax_return",
        }),
      "POST /v1/engagements/{engagement_id}/audit-events/query": () =>
        json({
          items: [
            {
              seq: 1,
              action: "document.approved",
              category: "decision",
              mark: "ok",
              effective_at: "2026-09-14T14:00:00Z",
              actor: {
                kind: "via_agent",
                on_behalf_of: { user_id: "u1", display_name: "Samuel Ito" },
              },
              target: { type: "tax_return", id: RETURN, label: "2025 Form 1040" },
            },
          ],
          total: 1,
        }),
    });
    mount(<ActivityLive returnId={RETURN} engagementId={ENGAGEMENT} />);
    expect(await screen.findByText(/Samuel Ito via Agent/)).toBeTruthy();
    expect(screen.getByText(/Document · approved · 2025 Form 1040/)).toBeTruthy();
    const q = calls.find((c) => c.key.endsWith("/audit-events/query"));
    expect(q?.body).toEqual({ work_item_id: RETURN, limit: 100 });
  });
});

describe("counts on a second tab", () => {
  it("an engagement invalidation refetches the workspace summary and every section's reads", async () => {
    const queryClient = newQueryClient();
    const seen: unknown[] = [];
    const real = queryClient.invalidateQueries.bind(queryClient);
    queryClient.invalidateQueries = (filters?: Parameters<typeof real>[0]) => {
      seen.push(filters?.queryKey);
      return real(filters);
    };
    const opening: RealtimeEvent[] = [{ seq: 1, type: "stream" }];
    const live = new RealtimeClient(queryClient, function* () {
      yield* opening;
    } as unknown as ConstructorParameters<typeof RealtimeClient>[1]);
    await live.start([`engagement:${ENGAGEMENT}`]);
    await live.handle({
      seq: 2,
      type: "invalidate",
      topic: `engagement:${ENGAGEMENT}`,
      ref_type: "document_approval",
      ref_id: "a1",
    });
    for (const key of RETURN_LIVE_KEYS) expect(seen).toContainEqual(key);
    expect(seen).toContainEqual([{ _id: "workspace" }]);
  });
});
