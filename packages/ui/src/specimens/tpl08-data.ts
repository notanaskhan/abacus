import type { InboxMessage, InboxState } from "../inbox/inbox-kit";
import { COPPERLEAF, FELD, NORTHWIND, RIDGELINE } from "./seed-figures";

// TPL-08's firm inbox (F-05-T58), word for word from the File Kit's `w0` and `w0-filed` datasets
// that the TPL-08 boards mount (Wave 0 Templates `#tpl08`, `kits/File Kit.dc.html` W0): Kevin
// Osei's inbox on Mon Sep 14, 2026 with the Feld thread open. 23 attachments wait (blueprint 01 §9:
// Feld 2, Shah 1, Stein 3, Collins 2, Kowal 2, Iyer 4, Copperleaf 3, Northwind 2, others 4 =
// Mendez 2, Osterberg 1, Okonjo 1) and 4 senders match no client. Where the spec's row list and the
// built boards differ (the Stein and Collins subjects, the row order), the boards win: they are the
// later decision (TPL-08 README). The clients are named as the seed names them.

export interface Tpl08Attachment {
  name: string;
  meta: string;
  state: InboxState;
  tag?: string;
  result?: { text: string; link?: string };
}

export interface Tpl08Message extends InboxMessage {
  client: string | null;
  /** Days before Sep 14, 2026, for the Received filter. */
  daysAgo: number;
  date: string;
  address: string;
  body: string;
  /** The record the thread belongs to, after the client chip. */
  context?: string;
  /** The agent's filing note above the message (it offers only Review). */
  note?: string;
  suggest: readonly string[];
  attachments: readonly Tpl08Attachment[];
  replies?: readonly Tpl08Message[];
}

const SIZES = ["212 KB PDF", "388 KB PDF", "96 KB PDF", "154 KB PDF"] as const;

/** `n` waiting attachments, the canvas's W(): sizes cycle through its four. */
const waiting = (names: readonly string[]): readonly Tpl08Attachment[] =>
  names.map((name, i) => ({ name, meta: SIZES[i % 4] ?? "", state: "wait" }));

const M = (
  id: string,
  subject: string,
  from: string,
  time: string,
  state: InboxState,
  client: string | null,
  daysAgo: number,
  rest: Partial<Tpl08Message> & Pick<Tpl08Message, "body">,
): Tpl08Message => ({
  id,
  subject,
  from,
  time,
  state,
  preview: "",
  client,
  daysAgo,
  date: `${time}, 2026`,
  address: `From ${from}`,
  suggest: [],
  attachments: [],
  ...rest,
});

const FELD_CTX = "TY2025 Form 1040 · Kevin Osei";

const FELD_NOTE =
  "Accrued Agent matched both attachments to 2025 Binder · Health & Medical (open request: Form 1095-C From Mercer Hill Health). One is a 2024 form and a duplicate of last year’s copy. Both are waiting for your decision.";

/** The inbox; `filed` is the `w0-filed` dataset, after triage (TPL-08d). */
export function tpl08Messages(filed: boolean): readonly Tpl08Message[] {
  return [
    M(
      "feld",
      "Re: 2025 tax documents",
      "claire.feld@gmail.com",
      "9:12 AM",
      filed ? "filed" : "new",
      FELD,
      0,
      {
        body: "",
        date: "September 14, 2026 9:12 AM",
        context: FELD_CTX,
        ...(filed ? {} : { note: FELD_NOTE }),
        suggest: [
          "2025 Binder › Health & Medical › Form 1095-C From Mercer Hill Health · 96%",
          "2025 Binder › Correspondence",
        ],
        replies: [
          M(
            "feld-a",
            "Re: 2025 tax documents",
            "claire.feld@gmail.com",
            "9:12 AM",
            filed ? "filed" : "wait",
            FELD,
            0,
            {
              date: "September 14, 2026 9:12 AM",
              context: FELD_CTX,
              body: "Hi Kevin, here are our health insurance forms from Mercer Hill. I wasn’t sure which year you needed, so I sent both. Thanks, Claire",
              attachments: [
                {
                  name: "Feld_1095C_2025.pdf",
                  meta: "412 KB PDF",
                  ...(filed
                    ? {
                        state: "filed" as const,
                        result: { text: "Filed to", link: "2025 Binder › Health & Medical" },
                      }
                    : { state: "wait" as const }),
                },
                {
                  name: "Feld_1095C_2024.pdf",
                  meta: "398 KB PDF",
                  ...(filed
                    ? { state: "ignored" as const, result: { text: "Ignored · wrong year" } }
                    : { state: "wait" as const, tag: "2024 ≠ 2025" }),
                },
              ],
            },
          ),
          M("feld-b", "2025 tax documents", "claire.feld@gmail.com", "Aug 3", "filed", FELD, 42, {
            date: "August 3, 2026 4:47 PM",
            context: FELD_CTX,
            body: "Hi Kevin, attached are my 2025 W-2 from Mercer Hill and our 1098 for the co-op loan. Jonah will send the Halvard 1099 separately. Thanks, Claire",
            attachments: [
              {
                name: "Claire_Feld_2025_W2_MercerHill.pdf",
                meta: "286 KB PDF",
                state: "filed",
                result: { text: "Filed to", link: "2025 Binder › Income › W-2s" },
              },
              {
                name: "Claire_Feld_2025_1098_HudsonMutual.pdf",
                meta: "174 KB PDF",
                state: "filed",
                result: { text: "Filed to", link: "2025 Binder › Home & Property" },
              },
            ],
          }),
        ],
      },
    ),
    M(
      "shah",
      "Schedule C expenses — 2025",
      "meera.shah@shahadvisory.com",
      "8:55 AM",
      "wait",
      "Meera Shah",
      0,
      {
        body: "Hi Kevin, attached is the 2025 expense summary for my advisory practice. Thanks, Meera",
        suggest: [
          "2025 Binder › Business & Self-Employment › Schedule C",
          "2025 Binder › Correspondence",
        ],
        attachments: waiting(["Shah_2025_ScheduleC_Expenses.pdf"]),
      },
    ),
    M(
      "stein",
      "Re: IRS letter — the 1099s you asked for",
      "harold.stein@outlook.com",
      "8:40 AM",
      "wait",
      "Harold Stein",
      0,
      {
        body: "Hi Kevin, here are the 1099s you asked for, and the IRS letter again in case you need it. Harold",
        note: "Two of these 3 attachments support the open IRS CP2000 for tax year 2024 (Notice N2, respond by Sep 30); the third is a copy of the notice already on file. Suggested destination: Notices › Stein CP2000 › Supporting documents.",
        suggest: ["Notices › Stein CP2000 › Supporting documents", "Notices › Stein CP2000"],
        attachments: [
          { name: "Stein_1099B_2024_Corrected.pdf", meta: "264 KB PDF", state: "wait" },
          { name: "Stein_1099DIV_2024.pdf", meta: "188 KB PDF", state: "wait" },
          {
            name: "Stein_CP2000_2024_copy.pdf",
            meta: "412 KB PDF",
            state: "wait",
            tag: "Duplicate of notice on file",
          },
        ],
      },
    ),
    M(
      "copper",
      "Receipts for August Amex charges",
      "ben.ashby@copperleafcoffee.com",
      "8:31 AM",
      "wait",
      COPPERLEAF,
      0,
      {
        body: "Receipts for the three August Amex charges you asked about.",
        suggest: ["August 2026 Close › Cards › Receipts"],
        attachments: waiting([
          "Amex_Receipt_Aug04.pdf",
          "Amex_Receipt_Aug12.pdf",
          "Amex_Receipt_Aug26.pdf",
        ]),
      },
    ),
    M(
      "north",
      "Census corrections for the 401(k) audit",
      "dana.kowalski@northwindrobotics.com",
      "8:02 AM",
      "wait",
      NORTHWIND,
      0,
      {
        body: "Corrected census files with the hire dates fixed.",
        suggest: ["Northwind 401(k) PY2025 › PBC › Census"],
        attachments: waiting(["Northwind_Census_PY2025_v2.pdf", "Northwind_Census_Changes.pdf"]),
      },
    ),
    M(
      "kowal",
      "Re: signing our 8879",
      "irene.kowal@gmail.com",
      "Yesterday",
      "wait",
      "Irene Kowal",
      1,
      {
        body: "Signed copies attached.",
        suggest: ["2025 Binder › Signatures"],
        attachments: waiting(["Kowal_8879_Signed.pdf", "Kowal_IL-8453_Signed.pdf"]),
      },
    ),
    M(
      "collins",
      "Avery’s corrected W-2",
      "wren.collins@icloud.com",
      "Yesterday",
      "wait",
      "Wren Collins",
      1,
      {
        body: "Avery’s W-2 from the summer job, front and back.",
        suggest: ["2025 Binder › Income › W-2s"],
        attachments: waiting(["Avery_W2_Front.pdf", "Avery_W2_Back.pdf"]),
      },
    ),
    M(
      "mendez",
      "Documents for 2025",
      "gloria.mendez@yahoo.com",
      "Yesterday",
      "wait",
      "Gloria Mendez",
      1,
      {
        body: "Hi Kevin, here are two more documents for our 2025 return. Gloria",
        suggest: ["2025 Binder › Income", "2025 Binder › Correspondence"],
        attachments: waiting(["Mendez_2025_1099-R.pdf", "Mendez_2025_1098-T.pdf"]),
      },
    ),
    M("sound", "Invoice SE-1187", "billing@soundelectricco.com", "Sep 12", "new", null, 2, {
      body: "Please find invoice SE-1187 attached. Thank you for your business.",
      note: "No contact uses billing@soundelectricco.com. Closest: Copperleaf Coffee Roasters, Inc. — Sound Electric is a vendor in its QuickBooks Online ledger (check #2285, $3,200.00, Aug 18).",
      suggest: ["August 2026 Close › Vendors › Invoices"],
      attachments: [{ name: "SoundElectric_INV-SE-1187.pdf", meta: "188 KB PDF", state: "new" }],
    }),
    M(
      "oster",
      "Brokerage statement",
      "ben.osterberg@gmail.com",
      "Sep 12",
      "wait",
      "Benjamin Osterberg",
      2,
      {
        body: "Attached is the year-end brokerage statement. Ben",
        suggest: ["2025 Binder › Income › 1099s"],
        attachments: waiting(["Osterberg_2025_Brokerage_Statement.pdf"]),
      },
    ),
    M(
      "okonjo",
      "Fwd: my partnership K-1",
      "juliet.okonjo@gmail.com",
      "Sep 12",
      "wait",
      "Juliet Okonjo",
      2,
      {
        body: "Forwarding the K-1 I received from the partnership. Juliet",
        suggest: ["2025 Binder › Income › K-1s"],
        attachments: waiting(["Okonjo_2025_K-1.pdf"]),
      },
    ),
    M(
      "iyer",
      "NY notice and 1099s",
      "priyanka.iyer@gmail.com",
      "Sep 11",
      "wait",
      "Priyanka Iyer",
      3,
      {
        body: "New York sent a notice, and here are the rest of my 1099s.",
        suggest: ["Notices › State notices", "2025 Binder › Income Sources"],
        attachments: waiting([
          "NY_Notice_DTF-160.pdf",
          "Iyer_2025_1099-B.pdf",
          "Iyer_2025_1099-INT.pdf",
          "Iyer_2025_1099-DIV.pdf",
        ]),
        replies: [
          M(
            "iyer-1",
            "NY notice",
            "priyanka.iyer@gmail.com",
            "Sep 9",
            "filed",
            "Priyanka Iyer",
            5,
            {
              body: "Is this notice something to worry about?",
            },
          ),
        ],
      },
    ),
    M(
      "summit",
      "Draft Form 5500 — Northwind Robotics 401(k) Plan",
      "j.ortega@summitplanadmin.com",
      "Sep 11",
      "new",
      null,
      3,
      {
        body: "Attached is the draft Form 5500 and Schedule H for your review.",
        note: "No contact uses j.ortega@summitplanadmin.com. Closest: Northwind Robotics, Inc. — Summit Plan Administrators prepares the plan’s Form 5500, and the draft is an open PBC request.",
        suggest: ["PY2025 EBP Audit › Source Documents › Form 5500 & SOC 1"],
        attachments: [
          { name: "Northwind_Draft_5500_ScheduleH.pdf", meta: "640 KB PDF", state: "new" },
        ],
      },
    ),
    M(
      "whitley",
      "Re: estimated payments",
      "dana.whitley@gmail.com",
      "Sep 11",
      "filed",
      "Marcus & Dana Whitley",
      3,
      {
        body: "Confirmations for the September estimated payments.",
        attachments: [
          {
            name: "Whitley_2026_Q3_Estimates.pdf",
            meta: "92 KB PDF",
            state: "filed",
            result: { text: "Filed to", link: "2026 Binder › Estimated payments" },
          },
        ],
      },
    ),
    M(
      "varga",
      "Donation receipt (duplicate)",
      "elena.varga@me.com",
      "Sep 10",
      "ignored",
      "Elena Varga",
      4,
      {
        body: "Sending the donation receipt again in case the first one didn’t arrive.",
        attachments: [
          {
            name: "Varga_Donation_Receipt.pdf",
            meta: "120 KB PDF",
            state: "ignored",
            result: { text: "Ignored · duplicate" },
          },
        ],
      },
    ),
    M("ferris", "Signed consent?", "kai.ferris@protonmail.com", "Sep 9", "new", null, 5, {
      body: "Is this the consent you needed me to sign?",
      note: "No contact uses kai.ferris@protonmail.com. Closest: Morgan & Kai Ferris — Kai Ferris is the second signer on their open §7216 consents.",
      suggest: ["2025 Binder › Consents"],
      attachments: [{ name: "Ferris_7216_Consent_signed.pdf", meta: "120 KB PDF", state: "new" }],
    }),
    M(
      "tallgrass",
      "Elm Street site visit photos",
      "appraisals@tallgrasscost.com",
      "Sep 9",
      "new",
      null,
      5,
      {
        body: "Photos from the Elm Street site visit are attached.",
        note: "No contact uses appraisals@tallgrasscost.com, and no open engagement mentions Elm Street. Match it to a client or ignore it.",
        attachments: [{ name: "Elm_Street_site_photos.pdf", meta: "2.4 MB PDF", state: "new" }],
      },
    ),
  ];
}

/** Every message and reply, flat. */
export const flat = (ms: readonly Tpl08Message[]): readonly Tpl08Message[] =>
  ms.flatMap((m) => [m, ...(m.replies ?? [])]);

/** Attachments waiting to be filed, by sender (the Home dashboard's 23). */
export function waitingBySender(ms: readonly Tpl08Message[]): Readonly<Record<string, number>> {
  const out: Record<string, number> = {};
  for (const m of flat(ms)) {
    const n = m.attachments.filter((a) => a.state === "wait").length;
    if (n > 0) out[m.from] = (out[m.from] ?? 0) + n;
  }
  return out;
}

/** Senders no client matches (the four the agent points somewhere or leaves to you). */
export const unmatched = (ms: readonly Tpl08Message[]): readonly string[] =>
  ms.filter((m) => m.client === null).map((m) => m.from);

/** The client chip's choices: the File Kit's list, with the seed's name for the Feld household. */
export const TPL08_CLIENTS = [
  FELD,
  "Meera Shah",
  COPPERLEAF,
  NORTHWIND,
  "Marcus & Dana Whitley",
  RIDGELINE,
] as const;

export interface Tpl08Filters {
  client: string | null;
  status: InboxState | null;
  /** Received: the boards set Past 30 Days, so the chip reads amber. */
  received: "today" | "7" | "30" | "all" | null;
  channel: "email" | "portal" | null;
  q: string;
  showIgnored: boolean;
  showFiled: boolean;
}

export const TPL08_DEFAULT: Tpl08Filters = {
  client: null,
  status: null,
  received: "30",
  channel: null,
  q: "",
  showIgnored: true,
  showFiled: true,
};

export const NO_TPL08_FILTERS: Tpl08Filters = {
  ...TPL08_DEFAULT,
  received: null,
};

/** The rail's rows under the filters (the server applies these; the fixture does here). */
export function visibleTpl08(
  ms: readonly Tpl08Message[],
  f: Tpl08Filters,
  stateOf: (m: Tpl08Message) => InboxState,
): readonly Tpl08Message[] {
  const days = { today: 0, "7": 7, "30": 30, all: Infinity, none: Infinity }[f.received ?? "none"];
  const q = f.q.trim().toLowerCase();
  return ms.filter((m) => {
    const st = stateOf(m);
    if (f.client !== null && m.client !== f.client) return false;
    if (f.status !== null && st !== f.status) return false;
    if (f.status === null && st === "ignored" && !f.showIgnored) return false;
    if (f.status === null && st === "filed" && !f.showFiled) return false;
    if (m.daysAgo > days) return false;
    if (f.channel === "portal") return false;
    if (q !== "" && !`${m.subject} ${m.from}`.toLowerCase().includes(q)) return false;
    return true;
  });
}
