import type { InboxMessage, InboxState } from "../inbox/inbox-kit";
import { COPPERLEAF, FELD, NORTHWIND, RIDGELINE, STAFF } from "./seed-figures";
import { FORM_PAGE_PNG, STATEMENT_PAGE_PNG } from "./viewer-pages";

// The T8 frame's inbox, word for word from the T8 handoff's boards (Wave 0 Foundations `#t8`): the
// firm inbox on Mon Sep 14, 2026. Clients are named as the seed names them, and where a board names
// a client contact the seed has differently, the seed's wins (DEC-354): Copperleaf's controller is
// Ben Ashby, Northwind's plan contact is Dana Kowalski, and Ridgeline's 704(b) correction is Pell
// Street Ventures LLC's. Senders that are not clients (Paycrest Payroll, Harborline Trust Company,
// Brightline Securities) stay as the boards draw them. TPL-08 (F-05-T58) draws the seed's own
// Feld thread and the 23 waiting.

export interface T8Attachment {
  name: string;
  meta: string;
  kind: "pdf" | "sheet";
  state?: Extract<InboxState, "wait" | "filed">;
}

export interface T8Message extends InboxMessage {
  /** The matched client, or null for an unmatched sender. */
  client: string | null;
  /** 0 is today; for the Received filter. */
  daysAgo: number;
  channel: "email" | "portal";
  /** The reading pane's date and address lines. */
  date: string;
  address: string;
  body: string;
  signature?: string;
  /** Where File… offers to put it, best first. */
  suggest: readonly string[];
  attachments: readonly T8Attachment[];
  /** The agent's filing note above the message, and whether it offers Review. */
  note?: { text: string; review: boolean };
  replies?: readonly T8Message[];
}

export const T8_CLIENTS = [FELD, COPPERLEAF, NORTHWIND, RIDGELINE] as const;

export const T8_MESSAGES: readonly T8Message[] = [
  {
    id: "pay",
    subject: "Bridge letter · Oct 1 – Dec 31, 2025",
    from: "Paycrest Payroll",
    time: "9:18 AM",
    state: "new",
    preview:
      "Our bridge letter for the SOC 1 Type 2 report, covering October through December 2025.",
    client: null,
    daysAgo: 0,
    channel: "email",
    date: "Sep 14, 2026, 9:18 AM",
    address: "From Paycrest Payroll <soc.reports@…>",
    body: "Attached is our bridge letter for the SOC 1 Type 2 report on the Paycrest payroll processing system. It covers October 1 through December 31, 2025, the part of your client’s plan year after our report period ends.",
    signature: "Paycrest Payroll · SOC Reporting",
    suggest: [
      "Northwind 401(k) PY2025 › Service organizations › Bridge letters",
      "Northwind 401(k) PY2025 › Correspondence",
    ],
    attachments: [
      {
        name: "Paycrest bridge letter Q4 2025.pdf",
        meta: "186 KB PDF",
        kind: "pdf",
        state: "wait",
      },
    ],
  },
  {
    id: "brk",
    subject: "2025 Composite 1099 — Brightline",
    from: "Claire Feld",
    time: "9:12 AM",
    state: "wait",
    preview: "Here is the corrected composite. The first one left out the foreign tax paid.",
    client: FELD,
    daysAgo: 0,
    channel: "email",
    date: "Sep 14, 2026, 9:12 AM",
    address: "From Claire Feld <claire.feld@…>",
    body: "Here is the corrected composite from Brightline. The first one left out the foreign tax paid on the international fund, so please use this one instead.",
    signature: "Claire Feld",
    suggest: [
      "2025 Binder › Income › 1099-DIV",
      "2025 Binder › Income › 1099-B",
      "2025 Binder › Correspondence",
    ],
    note: { text: "Accrued Agent filed 2 of 3 attachments to 2025 Binder · Income", review: true },
    attachments: [
      {
        name: "2025 Composite 1099 — Brokerage.pdf",
        meta: "1.2 MB PDF",
        kind: "pdf",
        state: "wait",
      },
      {
        name: "2025 Composite 1099 — Supplemental statement.pdf",
        meta: "640 KB PDF",
        kind: "pdf",
        state: "filed",
      },
      {
        name: "Brightline account summary 2025.xlsx",
        meta: "58 KB Excel",
        kind: "sheet",
        state: "filed",
      },
    ],
  },
  {
    id: "aug",
    subject: "Re: August bank statements",
    from: "Ben Ashby · Copperleaf",
    time: "8:58 AM",
    state: "new",
    preview: "Draft reconciliation for the operating account attached.",
    client: COPPERLEAF,
    daysAgo: 0,
    channel: "email",
    date: "Sep 14, 2026, 8:58 AM",
    address: "From Ben Ashby <ben.ashby@…>",
    body: "Draft reconciliation for the operating account is attached. The Amex statement for ••1009 is still coming; I will send it once it posts on Monday.",
    signature: `Ben Ashby · Controller, ${COPPERLEAF}`,
    suggest: ["August 2026 Close › Bank › Reconciliations", "August 2026 Close › Correspondence"],
    attachments: [
      { name: "Operating ••4410 reconciliation, August.xlsx", meta: "64 KB Excel", kind: "sheet" },
    ],
    replies: [
      {
        id: "aug-2",
        subject: `${STAFF.raj} · Brightwater Hale`,
        from: STAFF.raj,
        time: "Yesterday",
        state: "ignored",
        preview: "Thanks. The card statement for ••1009 is still missing.",
        client: COPPERLEAF,
        daysAgo: 1,
        channel: "email",
        date: "Sep 13, 2026, 4:20 PM",
        address: "To Ben Ashby",
        body: "Thanks, Ben. The card statement for ••1009 is still missing; could you send it with the reconciliation?",
        suggest: [],
        attachments: [],
      },
      {
        id: "aug-1",
        subject: "Ben Ashby · Copperleaf",
        from: "Ben Ashby · Copperleaf",
        time: "Yesterday",
        state: "filed",
        filedTo: "August 2026 Close › Bank › Statements",
        preview: "August statements for both Front Range accounts.",
        client: COPPERLEAF,
        daysAgo: 1,
        channel: "email",
        date: "Sep 13, 2026, 10:05 AM",
        address: "From Ben Ashby <ben.ashby@…>",
        body: "August statements for both Front Range Bank accounts are attached.",
        suggest: ["August 2026 Close › Bank › Statements"],
        attachments: [],
      },
    ],
  },
  {
    id: "tb",
    subject: "PY2025 trial balance",
    from: "Dana Kowalski · Northwind Robotics",
    time: "Yesterday",
    state: "wait",
    preview: "Final trial balance for the plan year, investments on their own tab.",
    client: NORTHWIND,
    daysAgo: 1,
    channel: "email",
    date: "Sep 13, 2026, 3:41 PM",
    address: "From Dana Kowalski <dana.kowalski@…>",
    body: "Final trial balance for the plan year. The investment detail is on its own tab, and it ties to the Harborline statement.",
    signature: `Dana Kowalski · HR Director, ${NORTHWIND}`,
    suggest: ["Northwind 401(k) PY2025 › Trial balance", "Northwind 401(k) PY2025 › Investments"],
    attachments: [
      { name: "Northwind 401(k) TB.xlsx", meta: "312 KB Excel", kind: "sheet", state: "wait" },
    ],
  },
  {
    id: "harbor",
    subject: "Net trust assets · December 31, 2025",
    from: "Harborline Trust Company",
    time: "Yesterday",
    state: "filed",
    filedTo: "Northwind 401(k) PY2025 › Investments › Trust statements",
    preview: "Net trust assets report for the Northwind Robotics 401(k) Plan.",
    client: NORTHWIND,
    daysAgo: 1,
    channel: "email",
    date: "Sep 13, 2026, 11:18 AM",
    address: "From Harborline Trust Company <client.reporting@…>",
    body: "Attached is the statement of net trust assets for the Northwind Robotics 401(k) Plan as of December 31, 2025.",
    signature: "Harborline Trust Company · Client Reporting",
    suggest: ["Northwind 401(k) PY2025 › Investments › Trust statements"],
    note: {
      text: "All 1 attachment is filed to Northwind 401(k) PY2025 · Investments",
      review: false,
    },
    attachments: [
      {
        name: "Harborline Net Trust Assets 12-31-2025.pdf",
        meta: "2.4 MB PDF",
        kind: "pdf",
        state: "filed",
      },
    ],
  },
  {
    id: "cap",
    subject: "Capital account roll-forward",
    from: RIDGELINE,
    time: "2 Days Ago",
    state: "new",
    preview: "Updated for the 704(b) adjustment we discussed.",
    client: RIDGELINE,
    daysAgo: 2,
    channel: "email",
    date: "Sep 12, 2026, 2:07 PM",
    address: `From ${RIDGELINE} <accounting@…>`,
    body: "Updated for the 704(b) adjustment we discussed on Thursday. Pell Street Ventures LLC’s ending capital now reflects the $8,500 correction.",
    signature: `${RIDGELINE} · Accounting`,
    suggest: ["2025 Form 1065 › Capital accounts", "2025 Form 1065 › Correspondence"],
    attachments: [
      { name: "Capital account roll-forward.xlsx", meta: "41 KB Excel", kind: "sheet" },
    ],
  },
  {
    id: "rcpt",
    subject: "Charitable receipts",
    from: "Jonah Feld",
    time: "Sep 11",
    state: "new",
    preview: "The three receipts are in the mail; photos to follow.",
    client: FELD,
    daysAgo: 3,
    channel: "portal",
    date: "Sep 11, 2026, 7:45 PM",
    address: "Through the client portal",
    body: "The originals for the three charitable receipts are in the mail. I will send photos tonight if that is faster for you.",
    signature: "Jonah Feld",
    suggest: ["2025 Binder › Deductions › Charitable", "2025 Binder › Correspondence"],
    attachments: [],
  },
  {
    id: "news",
    subject: "September client newsletter",
    from: "Brightline Securities",
    time: "Sep 10",
    state: "ignored",
    preview: "Market commentary and year-end planning reminders.",
    client: null,
    daysAgo: 4,
    channel: "email",
    date: "Sep 10, 2026, 6:00 AM",
    address: "From Brightline Securities <newsletter@…>",
    body: "Market commentary and year-end planning reminders for September.",
    signature: "Brightline Securities",
    suggest: [],
    attachments: [],
  },
];

/** The page render a thumbnail shows: the gallery's synthetic form or statement page. */
export const thumbSrc = (a: T8Attachment): string =>
  a.kind === "pdf" ? FORM_PAGE_PNG : STATEMENT_PAGE_PNG;

export const STATUS_OPTIONS = [
  { value: "new", label: "Not filed" },
  { value: "wait", label: "Waiting to be filed" },
  { value: "filed", label: "Filed" },
  { value: "ignored", label: "Ignored" },
] as const;

export const RECEIVED_OPTIONS = [
  { value: "today", label: "Today" },
  { value: "7", label: "Past 7 Days" },
  { value: "30", label: "Past 30 Days" },
  { value: "all", label: "All time" },
] as const;

export const CHANNEL_OPTIONS = [
  { value: "both", label: "Email · Portal" },
  { value: "email", label: "Email" },
  { value: "portal", label: "Portal" },
] as const;

export interface T8Filters {
  client: string | null;
  status: InboxState | null;
  received: "today" | "7" | "30" | "all";
  channel: "both" | "email" | "portal";
  q: string;
  showIgnored: boolean;
  showFiled: boolean;
}

export const NO_FILTERS: T8Filters = {
  client: null,
  status: null,
  received: "30",
  channel: "both",
  q: "",
  showIgnored: false,
  showFiled: true,
};

/** The rail's rows under the filters (the server applies these; the fixture does here). */
export function visibleMessages(
  messages: readonly T8Message[],
  f: T8Filters,
  stateOf: (m: T8Message) => InboxState,
): readonly T8Message[] {
  const q = f.q.trim().toLowerCase();
  return messages.filter((m) => {
    const st = stateOf(m);
    if (f.client !== null && m.client !== f.client) return false;
    if (f.status !== null) {
      if (st !== f.status) return false;
    } else {
      if (st === "ignored" && !f.showIgnored) return false;
      if (st === "filed" && !f.showFiled) return false;
    }
    if (f.received === "today" && m.daysAgo > 0) return false;
    if (f.received === "7" && m.daysAgo > 7) return false;
    if (f.channel !== "both" && m.channel !== f.channel) return false;
    if (q !== "" && !`${m.subject} ${m.from} ${m.preview}`.toLowerCase().includes(q)) return false;
    return true;
  });
}
