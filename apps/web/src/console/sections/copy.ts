// The console's undesigned sections (G-04-T17; G-04 §5.1; DEC-32 pattern, DEC-5701): composed from
// the kits with the words of their nearest designed screens. Status words are the blueprint's
// (01 §3.3.1); the support session words are SHL-05's and ADM-06's; nothing names a firm client.
import { amount } from "@abacus/ui";

export const SECTIONS_COPY = {
  nav: {
    sessions: "Support sessions",
    status: "Status",
    publications: "Publications",
    queue: "Support queue",
  },
  sessions: {
    title: "Support sessions",
    empty: "No support sessions yet",
    columns: ["Firm", "Scope", "Status", "Requested by", "Approver", "Started", "Minutes"],
    scope: {
      metadata: "Account metadata",
      integration_settings: "Integration settings",
      content: "Firm content",
    } as Record<string, string>,
    status: {
      requested: "Requested",
      active: "Active",
      declined: "Declined",
      revoked: "Revoked",
      ended: "Ended",
      expired: "Expired",
    } as Record<string, string>,
    tiles: { requested: "Requested", active: "Active", ended: "Ended" },
  },
  status: {
    title: "Status incidents",
    post: "Post incident…",
    empty: "No open incidents",
    severity: { degraded: "Degraded", outage: "Outage", maintenance: "Maintenance" } as Record<
      string,
      string
    >,
    resolved: "Resolved",
    open: "Open",
    sheet: {
      postTitle: "Post an incident",
      component: "Component",
      severity: "Severity",
      title: "Title",
      note: "Public note",
      post: "Post",
      updateTitle: "Update or resolve",
      update: "Post update",
      resolve: "Resolve",
      updateNote: "Note",
      cancel: "Cancel",
    },
  },
  queue: {
    title: "Support queue",
    empty: "No conversations waiting",
    unanswered: "Unanswered",
    answered: "Answered",
    reply: "Reply to the firm",
    staff: "Accrued Support",
  },
  publications: {
    title: "Publications",
    empty: "Nothing waiting to publish",
    columns: ["Kind", "Key", "Version", "Changes", "Drafted by", "Status", ""],
    kind: { help_article: "Help article", reference_set: "Reference set" } as Record<
      string,
      string
    >,
    status: { draft: "Draft", published: "Published", withdrawn: "Withdrawn" } as Record<
      string,
      string
    >,
    changes: (added: number, changed: number, removed: number): string =>
      `+${String(added)} · ~${String(changed)} · −${String(removed)}`,
    publish: "Publish",
    withdraw: "Withdraw",
    ownDraft: "You drafted this version. A second platform admin publishes it.",
  },
  planRequests: {
    tile: "Plan requests",
    card: "Plan requests",
    empty: "No plan requests",
    kind: { seats: "Seats", agent_minutes: "Agent minutes", modules: "Modules" } as Record<
      string,
      string
    >,
    change: (from: number | null, to: number | null): string =>
      `${from === null ? "—" : amount(String(from), "whole").text} → ${
        to === null ? "—" : amount(String(to), "whole").text
      }`,
    approvedBy: (name: string): string => `Approved by ${name}`,
    markApplied: "Mark applied",
    applied: "Applied",
    sent: "Sent",
  },
} as const;
