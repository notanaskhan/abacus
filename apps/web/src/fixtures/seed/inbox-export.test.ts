// N-01-T11 (DEC-47, DF-33; DEC-836): fixture mode's inbox and Files seeds against the figures the
// Python scenario's `firm_inbox` slice exports (`inbox-e0.json`, written by `python -m
// abacus_tools.synthetic.scenarios.brightwater_hale.firm_inbox --export`; the backend's suite holds
// the file to the slice). INB-01 rows 1-17, HOME-01's "Inbox waiting" and FIL-01's Ridgeline
// figures must agree with it: 23 waiting, 4 unmatched, 21 after Feld's two are applied; Ridgeline's
// folders 12 · 3 · 4 · 5 · 0 with 6 in the Permanent file, 7 virtual children, and the mortgage
// statements footing to 512,400 on account 5500.

import { describe, expect, it } from "vitest";
import exported from "./inbox-e0.json";
import { mortgageDrawer, RIDGELINE_SOURCE_ROWS, RIDGELINE_TREE } from "./files";
import { homeView } from "./home";
import { inboxThreads, threadDetail, threadRow } from "./inbox";

type TreeNode = (typeof RIDGELINE_TREE.nodes)[number];

function walk(nodes: readonly TreeNode[]): TreeNode[] {
  return nodes.flatMap((n) => [n, ...walk(n.children)]);
}

describe("INB-01's seed against the scenario export", () => {
  const rows = inboxThreads(false).map(threadRow);

  it("has the same 17 threads, newest first, with the same senders, subjects and clients", () => {
    expect(rows).toHaveLength(17);
    expect(
      rows.map((r) => [r.subject_display, r.sender_display, r.client_name, r.message_count]),
    ).toEqual(exported.inbox.threads.map((t) => [t.subject, t.sender, t.client, t.messages]));
  });

  it("has the same attachments in the same states", () => {
    const states = { wait: "waiting", new: "new", filed: "filed", ignored: "ignored" } as const;
    const byName = (a: { name: string }, b: { name: string }) => a.name.localeCompare(b.name);
    const seeded = inboxThreads(false).map((m) =>
      threadDetail(m)
        .messages.flatMap((msg) =>
          msg.attachments.map((a) => ({ name: a.file_name, state: a.status })),
        )
        .sort(byName),
    );
    expect(seeded).toEqual(
      exported.inbox.threads.map((t) =>
        t.attachments
          .map((a) => ({ name: a.name, state: states[a.state as keyof typeof states] }))
          .sort(byName),
      ),
    );
  });

  it("foots: 23 waiting, 4 unmatched (rows 9, 13, 16, 17), 21 once Feld's two are applied", () => {
    const waiting = rows.reduce((n, r) => n + r.waiting, 0);
    expect(waiting).toBe(exported.inbox.waiting);
    expect(waiting).toBe(23);
    expect(rows.map((r) => r.waiting)).toEqual(exported.inbox.threads.map((t) => t.waiting));
    const unmatched = rows.flatMap((r, i) => (r.match_state === "unmatched" ? [i + 1] : []));
    expect(unmatched).toEqual(exported.inbox.unmatched_rows);
    const after = inboxThreads(true)
      .map(threadRow)
      .reduce((n, r) => n + r.waiting, 0);
    expect(after).toBe(exported.inbox.waiting_after_feld_applied);
  });

  it("HOME-01's Inbox waiting tile equals the inbox summary", () => {
    const view = homeView("grace-holloway");
    const tile = JSON.stringify(view).match(/"key":"inbox_waiting"[^}]*"total":(\d+)/);
    expect(tile?.[1]).toBe(String(exported.inbox.waiting));
  });
});

describe("FIL-01's seed against the scenario export", () => {
  const nodes = walk(RIDGELINE_TREE.nodes);
  const folders = exported.files.ridgeline_folders;

  it("has Ridgeline's folder counts and Permanent file", () => {
    const tax = nodes.filter((n) => n.kind === "folder");
    const byKind: Record<string, number> = Object.fromEntries(
      tax.map((n) => [n.folder_kind ?? "", n.count]),
    );
    expect(byKind.source_documents).toBe(exported.files.ridgeline_source_documents);
    expect(byKind.workpapers).toBe(folders.workpapers);
    expect(byKind.correspondence).toBe(folders.correspondence);
    expect(byKind.deliverables).toBe(folders.deliverables);
    expect(byKind.signed_authorizations).toBe(folders.signed_authorizations);
    expect(nodes.find((n) => n.kind === "permanent_file")?.count).toBe(folders.permanent_file);
  });

  it("has 12 source documents with 7 virtual children", () => {
    const documents = RIDGELINE_SOURCE_ROWS.filter((r) => r.superseded_by_name === null);
    expect(documents).toHaveLength(exported.files.ridgeline_source_documents);
    const virtual = RIDGELINE_SOURCE_ROWS.reduce((n, r) => n + r.virtual_children.length, 0);
    expect(virtual).toBe(exported.files.ridgeline_virtual);
  });

  it("foots the mortgage statements to 512,400 on account 5500", () => {
    const drawer = mortgageDrawer();
    const amounts = drawer.virtual_children.map((c) => c.amount);
    expect(amounts).toEqual(exported.files.mortgage_statements);
    expect(drawer.tie?.total).toBe(exported.files.mortgage_total);
    expect(drawer.tie?.account_number).toBe(exported.files.mortgage_account);
  });
});
