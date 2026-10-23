import { type JSX, useState } from "react";
import { Pill } from "../components/pill";
import type { IconName } from "../icons";
import type { PillVariant } from "../status";
import {
  ActivityRow,
  DashTile,
  DashboardLayout,
  DeadlineRow,
  QueueEmpty,
  QueueRow,
} from "../templates/dashboard-layout";
import guards from "../../scope-guards.gen.json";
import { Artboard } from "./portal";
import { FIRM, RETURNS_BY_OFFICE } from "./seed-figures";

// T11 DashboardLayout (F-05-T46): T11a to T11f (Wave 0 - Foundations `#t11`) and TPL-11a to
// TPL-11f (Wave 0 - Templates TPL-11), Home at Mon Sep 14, 2026, 9:24 AM CT. Every string and
// count is the canvas's own and the practice counts tie to blueprint §9.5 (TY2025 returns 224 =
// 98 + 64 + 62, open 79, Prepared 17 · In review 15 · Issues 11 · Ready 7; audits 27 = 7 + 9 + 6 +
// 2 + 3; closes 11 of 22; notices 9, 2 new; 3 running). The office filter hands the layout the
// view for that office, as the server would: T11 filters its queue and deadlines by each row's
// office; TPL-11 swaps in the Denver view the canvas draws (TPL-11f).

const NAV = guards.nav.map((label) => ({ label }));
const TOOLBAR = {
  nav: NAV,
  firm: FIRM,
  firmShort: "Brightwater",
  firmTitle: "Brightwater Hale LLP",
  holdLabelWidth: false,
} as const;

const DATE = "Monday, September 14";
const RUNNING = "3 running";
const OFFICES = ["Chicago", "Denver", "New York"] as const;
const ALL = "All offices";

type Office = (typeof OFFICES)[number];

const office = (value: string | null, onChange: (o: string | null) => void) => ({
  label: "Office",
  options: OFFICES,
  value,
  allLabel: ALL,
  onChange,
});

// ---- T11 ------------------------------------------------------------------------------------------

type QueueType = "q" | "sign" | "approve" | "signature" | "send";
const QUEUE_ICON: Record<QueueType, IconName> = {
  q: "circle-help",
  sign: "circle-check",
  approve: "sparkles",
  signature: "signature",
  send: "send",
};

interface T11Item {
  type: QueueType;
  title: string;
  ctx: string;
  /** Days until due: 7 or fewer reads red, 30 or fewer amber. */
  days: number;
  due: string;
  office: Office;
}

const Q = (
  type: QueueType,
  title: string,
  ctx: string,
  days: number,
  due: string,
  where: Office,
): T11Item => ({ type, title, ctx, days, due, office: where });

const dueVariant = (days: number): PillVariant =>
  days <= 7 ? "red-tint" : days <= 30 ? "amber" : "soon";

type Tile = Parameters<typeof DashTile>[0];
const S = (value: number, label: string, variant: PillVariant): Tile => ({
  kind: "single",
  value: String(value),
  label,
  variant,
});
const G = (title: string, counts: readonly (readonly [number, string])[]): Tile => ({
  kind: "group",
  title,
  counts: counts.map(([n, label]) => ({ value: String(n), label })),
});

interface T11Role {
  id: string;
  name: string;
  note: string;
  greet: string;
  tiles: readonly Tile[];
  queue: readonly T11Item[];
  quiet?: boolean;
  loading?: boolean;
}

const T11_DEADLINES: readonly (readonly [string, string, string, string, PillVariant, Office])[] =
  [
    [
      "Sep 15",
      "Ridgeline Property Partners, LP",
      "Form 1065 · extended",
      "In review · Partner",
      "amber",
      "Chicago",
    ],
    [
      "Sep 15",
      "Granite Peak Outdoor Supply",
      "Form 1120-S · extended",
      "Ready",
      "green-tint",
      "Denver",
    ],
    [
      "Sep 15",
      "Harborview Dental Properties, LP",
      "Form 1065 · extended",
      "Awaiting signature",
      "amber",
      "New York",
    ],
    [
      "Sep 15",
      "Copperleaf Coffee Roasters, Inc.",
      "Form 1120-S · extended",
      "Issues",
      "red-tint",
      "Chicago",
    ],
    ["Sep 30", "Calloway Family Trust", "Form 1041 · extended", "Prepared", "neutral", "Chicago"],
    [
      "Oct 15",
      "Jonah & Claire Feld",
      "Form 1040 · extended",
      "In review · Manager",
      "amber",
      "Chicago",
    ],
    [
      "Oct 15",
      "Northwind Robotics 401(k) Plan",
      "Form 5500 · extended",
      "Planning",
      "amber",
      "Chicago",
    ],
  ];

const T11_FEED: readonly (readonly [IconName, string, string, string])[] = [
  [
    "upload",
    "Paycrest Payroll sent the Q4 bridge letter",
    "Northwind Robotics 401(k) Plan",
    "9:18 AM",
  ],
  ["upload", "Claire Feld uploaded a corrected composite 1099", "Jonah & Claire Feld", "9:12 AM"],
  [
    "mail",
    "Lucia Ferraro sent the August reconciliation",
    "Copperleaf Coffee Roasters, Inc.",
    "8:58 AM",
  ],
  ["upload", "Dana Whitley uploaded 2 W-2s", "Marcus & Dana Whitley", "Sep 12"],
  [
    "file-text",
    "Ridgeline sent the capital account roll-forward",
    "Ridgeline Property Partners, LP",
    "Sep 12",
  ],
];

const T11_ROLES: readonly T11Role[] = [
  {
    id: "t11a",
    name: "Partner",
    note: "Margaret Okonkwo, Managing Partner and Audit EP",
    greet: "Good morning, Margaret",
    tiles: [
      G("TY2025 Returns", [
        [17, "Prepared"],
        [15, "In review"],
        [11, "Issues"],
        [7, "Ready"],
      ]),
      G("Audits", [
        [7, "Planning"],
        [9, "Fieldwork"],
        [6, "In review"],
        [2, "Ready to release"],
      ]),
      G("Closes", [
        [11, "In progress"],
        [5, "In review"],
        [3, "Not started"],
      ]),
      S(10, "Awaiting signature", "amber"),
      S(9, "Notices", "red-tint"),
    ],
    queue: [
      Q(
        "q",
        "Choose the materiality benchmark",
        "Northwind Robotics 401(k) Plan · PY2025 audit · asked by Accrued Agent",
        0,
        "Today",
        "Chicago",
      ),
      Q(
        "sign",
        "Sign off Service Organizations & SOC 1",
        "Northwind Robotics 401(k) Plan · prepared by Accrued Agent",
        4,
        "Sep 18",
        "Chicago",
      ),
      Q(
        "approve",
        "Approve 3 proposed entries for the August close",
        "Copperleaf Coffee Roasters, Inc. · proposed by Accrued Agent",
        -4,
        "4 days late",
        "Chicago",
      ),
      Q(
        "signature",
        "Sign the Lakeshore Literacy Alliance engagement letter",
        "Engagement letter · 2026 audit",
        11,
        "Sep 25",
        "Chicago",
      ),
      Q(
        "send",
        "Send the Northwind planning letter to the plan committee",
        "Northwind Robotics 401(k) Plan · governance communication",
        16,
        "Sep 30",
        "Chicago",
      ),
    ],
  },
  {
    id: "t11b",
    name: "Manager",
    note: "Samuel Ito, Tax Manager and reviewer",
    greet: "Good morning, Samuel",
    tiles: [
      S(17, "Prepared", "neutral"),
      S(15, "In review", "amber"),
      S(11, "Issues", "red-tint"),
      S(7, "Ready", "green-tint"),
      G("TY2025 Returns", [
        [224, "Total"],
        [79, "Open"],
        [145, "Filed or accepted"],
      ]),
      G("Signatures", [
        [17, "Out"],
        [10, "Returns awaiting"],
      ]),
    ],
    queue: [
      Q(
        "q",
        "Tell Accrued Agent which composite 1099 the Feld return uses",
        "Jonah & Claire Feld · a corrected 1099 arrived at 9:12 AM",
        0,
        "Today",
        "Chicago",
      ),
      Q(
        "approve",
        "Approve the Whitley document reminder",
        "Marcus & Dana Whitley · drafted by Accrued Agent",
        2,
        "Sep 16",
        "Denver",
      ),
      Q(
        "sign",
        "Review the Feld 1040",
        "Jonah & Claire Feld · 4 issues open · prepared by Kevin Osei",
        31,
        "Oct 15",
        "Chicago",
      ),
      Q(
        "sign",
        "Review the Calloway Family Trust 1041",
        "Calloway Family Trust · prepared by Olivia Brandt",
        16,
        "Sep 30",
        "Chicago",
      ),
      Q(
        "send",
        "Send the Feld transmittal letter",
        "Jonah & Claire Feld · approved Sep 12",
        31,
        "Oct 15",
        "Chicago",
      ),
    ],
  },
  {
    id: "t11c",
    name: "Staff",
    note: "Kevin Osei, Tax Preparer",
    greet: "Good morning, Kevin",
    tiles: [
      G("My Returns", [
        [1, "Gathering"],
        [1, "Preparing"],
        [1, "In review"],
        [2, "Issues"],
      ]),
      G("Feld 1040", [
        [4, "Issues"],
        [2, "Intake"],
      ]),
      G("Upcoming Deadlines", [
        [2, "Sep 15"],
        [3, "Oct 15"],
      ]),
    ],
    queue: [
      Q(
        "approve",
        "Approve the line 3b fix on the Feld 1040",
        "Accrued Agent proposes 4,812 from the 1099 in place of 4,182",
        0,
        "Today",
        "Chicago",
      ),
      Q(
        "q",
        "Choose how to treat the three lots with no basis",
        "Jonah & Claire Feld · composite 1099-B",
        4,
        "Sep 18",
        "Chicago",
      ),
      Q(
        "send",
        "Send the Whitley document reminder",
        "Marcus & Dana Whitley · 5 requests open",
        16,
        "Sep 30",
        "Denver",
      ),
    ],
  },
  {
    id: "t11d",
    name: "Admin",
    note: "Grace Holloway, Firm Admin",
    greet: "Good morning, Grace",
    tiles: [
      G("Seats", [
        [46, "Total"],
        [22, "Chicago"],
        [14, "Denver"],
        [10, "New York"],
      ]),
      G("Integrations", [
        [5, "Connected"],
        [2, "Need reauth"],
      ]),
      S(6, "Installed", "green"),
      S(23, "Inbox", "amber"),
    ],
    queue: [
      Q(
        "approve",
        "Approve SOC 1 Coverage Check for the audit team",
        "Agent install · requested by Hannah Leclerc",
        2,
        "Sep 16",
        "Chicago",
      ),
      Q(
        "approve",
        "Approve a seasonal seat for Lena Park",
        "Chicago · requested by Samuel Ito",
        1,
        "Tomorrow",
        "Chicago",
      ),
      Q(
        "q",
        "Choose who renews the Lacerte and ADP connections",
        "Integrations · both signed out on Sep 12",
        1,
        "Tomorrow",
        "Chicago",
      ),
      Q(
        "signature",
        "Sign the 2026 data processing addendum",
        "Firm agreement · Accrued",
        16,
        "Sep 30",
        "Chicago",
      ),
    ],
  },
  {
    id: "t11e",
    name: "Quiet day",
    note: "Lena Park has nothing waiting",
    greet: "Good morning, Lena",
    quiet: true,
    tiles: [
      G("My Returns", [
        [2, "Prepared"],
        [1, "In review"],
        [1, "Not started"],
      ]),
      S(0, "Issues", "red-tint"),
      S(0, "Intake", "muted"),
    ],
    queue: [],
  },
  {
    id: "t11f",
    name: "Loading",
    note: "Skeleton tiles and rows while the dashboard loads",
    greet: "Good morning, Margaret",
    loading: true,
    tiles: [],
    queue: [],
  },
];

function T11Frame({ role }: { role: T11Role }): JSX.Element {
  const [where, setWhere] = useState<string | null>(null);
  const queue = role.queue.filter((q) => where === null || q.office === where);
  const deadlines = T11_DEADLINES.filter((d) => where === null || d[5] === where);
  return (
    <Artboard id={role.id} badge={`T11${role.id.slice(-1)}`} name={role.name} note={role.note}>
      <DashboardLayout
        embedded
        height={860}
        toolbar={TOOLBAR}
        greeting={role.greet}
        date={DATE}
        office={office(where, setWhere)}
        running={RUNNING}
        loading={role.loading === true}
        tiles={role.tiles.map((t, i) => (
          <DashTile key={String(i)} {...t} />
        ))}
        queue={{
          title: "Waiting on you",
          ...(queue.length === 0 ? {} : { count: queue.length }),
          children:
            queue.length === 0 ? (
              <QueueEmpty title="Nothing waiting on you.">
                Decisions, sign-offs, approvals and things to send show up here as they come in.
              </QueueEmpty>
            ) : (
              <ul>
                {queue.map((q) => (
                  <QueueRow
                    key={q.title}
                    icon={QUEUE_ICON[q.type]}
                    title={q.title}
                    context={q.ctx}
                    due={{ label: q.due, variant: dueVariant(q.days) }}
                    href={`#${role.id}`}
                  />
                ))}
              </ul>
            ),
        }}
        side={[
          {
            title: "Deadlines",
            children:
              deadlines.length === 0 ? (
                <p className="px-[14px] py-[12px] text-body text-ink-3">
                  No deadlines for this office this month.
                </p>
              ) : (
                <ul>
                  {deadlines.map(([d, client, form, status, variant]) => (
                    <DeadlineRow
                      key={`${d}${client}`}
                      date={d}
                      client={client}
                      form={form}
                      status={{ label: status, variant }}
                    />
                  ))}
                </ul>
              ),
          },
          {
            title: "Client Activity",
            children: (
              <ul className="py-[4px]">
                {T11_FEED.map(([icon, text, ctx, when]) => (
                  <ActivityRow key={text} icon={icon} text={text} context={ctx} when={when} />
                ))}
              </ul>
            ),
          },
        ]}
      />
    </Artboard>
  );
}

/** T11a to T11f (Wave 0 - Foundations `#t11`). */
export function T11Specimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      {T11_ROLES.map((role) => (
        <T11Frame key={role.id} role={role} />
      ))}
    </div>
  );
}

// ---- TPL-11 ---------------------------------------------------------------------------------------

type Who = "MO" | "DR" | "KO" | "GH";
type RowTone = "amber" | "red" | "neutral";
const ROW_VARIANT: Record<RowTone, PillVariant> = {
  amber: "amber",
  red: "red-tint",
  neutral: "soon",
};

interface Tpl11Row {
  icon: IconName;
  t: string;
  c: string;
  due: string;
  kind: RowTone;
  go: string;
}
const R = (
  icon: IconName,
  t: string,
  c: string,
  due: string,
  kind: RowTone,
  go: string,
): Tpl11Row => ({
  icon,
  t,
  c,
  due,
  kind,
  go,
});

const ROWS: Record<Who, readonly Tpl11Row[]> = {
  MO: [
    R(
      "circle-help",
      "Planning materiality — Northwind Robotics 401(k) Plan, PY2025",
      "Proposed v1 by Accrued Agent on unadjusted net assets $16,812,400: 1.0% = $168,100 or 1.5% = $252,200 (recommended). Blocking 3 workpapers.",
      "Blocked on a partner decision",
      "amber",
      "Opens AUD-07 with the decision card (SHL-11)",
    ),
    R(
      "circle-help",
      "Planning materiality — Granite Peak Outdoor Supply, Inc., FY2026",
      "Proposed by Accrued Agent: 5% of pre-tax income $3,100,000 = $155,000 · PM $116,250 · CT $7,750",
      "Blocked on a partner decision",
      "amber",
      "Opens AUD-07 with the decision card (SHL-11)",
    ),
    R(
      "signature",
      "Countersign engagement letter — FY2026 FS audit · Granite Peak Outdoor Supply",
      "Luis Ferrante signed · your signature",
      "Sep 16 · 2 days",
      "red",
      "Opens SIG-01, then SIG-02 to sign",
    ),
    R(
      "signature",
      "Countersign engagement letter — PY2025 EBP audit · Fairhaven Foods 401(k) Plan",
      "Sent Sep 8 to the plan administrator and to you",
      "Sep 18 · 4 days",
      "red",
      "Opens SIG-01, then SIG-02 to sign",
    ),
  ],
  DR: [
    R(
      "circle-check",
      "Final approval — 2025 Form 1065 · Ridgeline Property Partners, LP (BH-TAX-02)",
      "11 open issues · the K-1s release with approval",
      "Sep 15 · 1 day",
      "red",
      "Opens HOME-02 with the approval open",
    ),
    R(
      "package",
      "Release K-1s — Ridgeline (5 recipients)",
      "All five release together after final approval",
      "After approval",
      "neutral",
      "Opens TXP-12 · K-1 package",
    ),
    R(
      "signature",
      "Countersign engagement letter — Ridgeline cost segregation & §754 analysis",
      "Owen Calder signs first",
      "Sep 24 · 10 days",
      "neutral",
      "Opens SIG-01, then SIG-02 to sign",
    ),
  ],
  KO: [
    R(
      "file-text",
      "Jonah & Claire Feld · 2025 Form 1040",
      "4 open issues · extended due date Oct 15, 2026",
      "In review · Manager",
      "amber",
      "Opens TAX-02",
    ),
    R(
      "mail",
      "Marcus & Dana Whitley · CP2000 response",
      "Response due Sep 23",
      "Analyzing",
      "amber",
      "Opens NOT-02",
    ),
    R(
      "mail",
      "Thomas & Irene Kowal · CP14 response",
      "Response due Sep 21",
      "Response drafted",
      "amber",
      "Opens NOT-02",
    ),
  ],
  GH: [
    R(
      "shield-check",
      "Approve support session — Feld 2025 Form 1040 (2 hours)",
      "Requested by Accrued Support in SHL-05 · Firm settings › Security",
      "Awaiting firm approval",
      "amber",
      "Opens ADM-06",
    ),
    R(
      "folder",
      "File inbox attachments",
      "23 attachments waiting in the firm inbox",
      "23 waiting",
      "neutral",
      "Opens INB-01",
    ),
  ],
};

const ENGAGEMENTS: Partial<Record<Who, readonly (readonly [string, string, string])[]>> = {
  MO: [
    ["Northwind Robotics 401(k) Plan", "run Processing · PBC 11 of 24", "Planning"],
    ["Granite Peak Outdoor Supply, Inc.", "", "Planning"],
    ["Fairhaven Foods 401(k) Plan", "", "Planning"],
    ["Arbor Senior Living 401(k) Plan", "", "Fieldwork"],
  ],
  DR: [
    ["Ridgeline Property Partners, LP · TY2025 Form 1065", "", "In review · Partner"],
    ["Jonah & Claire Feld · TY2025 Form 1040", "", "In review · Manager"],
    ["Ridgeline cost segregation & §754 analysis", "", "Scoping"],
  ],
};

/** Deadlines in the next 14 days: [date, client, form, status, office]; "All" is the roll-up row. */
const DEADLINES: readonly (readonly [string, string, string, string, Office | "All"])[] = [
  [
    "Sep 15",
    "Ridgeline Property Partners, LP",
    "Form 1065 (extended)",
    "In review · Partner",
    "New York",
  ],
  ["Sep 15", "7 more 1065 / 1120-S returns", "extended due date", "", "All"],
  ["Sep 16", "Granite Peak Outdoor Supply", "Engagement letter", "Partially signed", "Denver"],
  ["Sep 18", "Fairhaven Foods 401(k) Plan", "Engagement letter", "Sent", "Chicago"],
  ["Sep 21", "Thomas & Irene Kowal", "IRS CP14 response", "Response drafted", "Chicago"],
  ["Sep 23", "Marcus & Dana Whitley", "IRS CP2000 response", "Analyzing", "Denver"],
  ["Sep 23", "Morgan & Kai Ferris", "§7216 consents", "Partially signed", "Chicago"],
  [
    "Sep 24",
    "Ridgeline Property Partners, LP",
    "Engagement letter — cost segregation & §754",
    "Sent",
    "New York",
  ],
  ["Sep 28", "Rafael Quintero", "IRS CP501 response", "Response drafted", "Denver"],
];

const ACTIVITY: readonly (readonly [IconName, string, string])[] = [
  ["mail", "9:12 AM", "Claire Feld emailed 2 health insurance forms — waiting to be filed"],
  [
    "message-circle",
    "9:02 AM",
    "Ben Ashby replied to “What was the $3,200 payment to Sound Electric?” — invoice to follow this afternoon",
  ],
  [
    "upload",
    "8:47 AM",
    "Sam Ortiz (Keystone Retirement Services) uploaded the Schedule of Account Balances",
  ],
  ["signature", "Sep 12", "Luis Ferrante signed the Granite Peak engagement letter"],
  ["pen-line", "Sep 11", "Thomas Kowal signed Form 8879 (Irene Kowal pending)"],
];

/** The practice view for one office, as the server sends it (canvas `tpl11Vals`). Only the views
 * the artboards draw are fixtures: all offices (§9.5) and Denver (TPL-11f). */
export interface PracticeView {
  caption: string;
  /** Prepared, In review, Issues, Ready. */
  tax: readonly [number, number, number, number];
  /** Planning, Fieldwork, In review, Ready to release, Released. */
  audits: readonly [number, number, number, number, number];
  /** The server's total, never summed in the browser (ADR-050); the specimen test foots it. */
  auditsTotal: number;
  closes: { inProgress: number; total: number };
  notices: { open: number; isNew: number };
}

export const PRACTICE_VIEWS: Readonly<Record<"all" | "Denver", PracticeView>> = {
  all: {
    caption: "Tax returns · TY2025 · 79 open",
    tax: [17, 15, 11, 7],
    audits: [7, 9, 6, 2, 3],
    auditsTotal: 27,
    closes: { inProgress: 11, total: 22 },
    notices: { open: 9, isNew: 2 },
  },
  Denver: {
    caption: `Denver · ${String(RETURNS_BY_OFFICE.Denver)} returns`,
    tax: [5, 4, 3, 2],
    audits: [2, 3, 2, 1, 1],
    auditsTotal: 9,
    closes: { inProgress: 4, total: 8 },
    notices: { open: 3, isNew: 1 },
  },
};

const TAX_LABELS = [
  ["Prepared", "neutral"],
  ["In review", "amber"],
  ["Issues", "red-tint"],
  ["Ready", "green-tint"],
] as const;
const AUDIT_LABELS = [
  "Planning",
  "Fieldwork",
  "In review",
  "Ready to release",
  "Released",
] as const;
const ADMIN_STATS = [
  ["17", "Signatures out"],
  ["23", "Inbox waiting"],
  ["4", "Portal invites pending"],
] as const;

interface Tpl11Frame {
  id: string;
  badge: string;
  name: string;
  note: string;
  who: Who;
  greet: string;
  quiet?: boolean;
  office?: "Denver";
}

const TPL11_FRAMES: readonly Tpl11Frame[] = [
  {
    id: "tpl-11a",
    badge: "TPL-11a",
    name: "Partner default",
    note: "Margaret Okonkwo: two materiality decisions and two letters to countersign",
    who: "MO",
    greet: "Margaret",
  },
  {
    id: "tpl-11b",
    badge: "TPL-11b",
    name: "Tax partner",
    note: "Daniel Reyes: final approval, K-1 release and the §754 letter",
    who: "DR",
    greet: "Daniel",
  },
  {
    id: "tpl-11c",
    badge: "TPL-11c",
    name: "Staff",
    note: "Kevin Osei: My returns instead of decisions",
    who: "KO",
    greet: "Kevin",
  },
  {
    id: "tpl-11d",
    badge: "TPL-11d",
    name: "Admin",
    note: "Grace Holloway: signatures, inbox and portal invites",
    who: "GH",
    greet: "Grace",
  },
  {
    id: "tpl-11e",
    badge: "TPL-11e",
    name: "Quiet day",
    note: "Nothing waiting on Margaret",
    who: "MO",
    greet: "Margaret",
    quiet: true,
  },
  {
    id: "tpl-11f",
    badge: "TPL-11f",
    name: "Office · Denver",
    note: "The tiles and deadlines recompute; the chip turns amber",
    who: "MO",
    greet: "Margaret",
    office: "Denver",
  },
];

function Tpl11Tiles({ view, who }: { view: PracticeView; who: Who }): JSX.Element {
  return (
    <>
      {TAX_LABELS.map(([label, variant], i) => (
        <DashTile
          key={label}
          kind="single"
          value={String(view.tax[i])}
          label={label}
          variant={variant}
        />
      ))}
      {who === "GH" ? (
        ADMIN_STATS.map(([value, caption]) => (
          <DashTile key={caption} kind="stat" value={value} caption={caption} />
        ))
      ) : (
        <>
          <DashTile
            kind="group"
            title={`Audits & assurance · ${String(view.auditsTotal)}`}
            width={360}
            counts={AUDIT_LABELS.map((label, i) => ({ value: String(view.audits[i]), label }))}
          />
          <DashTile
            kind="meter"
            value={String(view.closes.inProgress)}
            pill={{ label: "In progress", variant: "amber" }}
            caption={`of ${String(view.closes.total)} · August 2026`}
          />
          <DashTile
            kind="meter"
            value={String(view.notices.open)}
            pill={{ label: `${String(view.notices.isNew)} New`, variant: "red-tint" }}
            caption="Notices open"
          />
        </>
      )}
    </>
  );
}

function Tpl11Board({ frame }: { frame: Tpl11Frame }): JSX.Element {
  const [where, setWhere] = useState<string | null>(frame.office ?? null);
  const denver = where === "Denver";
  const view = denver ? PRACTICE_VIEWS.Denver : PRACTICE_VIEWS.all;
  const rows = frame.quiet === true ? [] : ROWS[frame.who];
  const engagements = ENGAGEMENTS[frame.who] ?? [];
  const deadlines = DEADLINES.filter(([, , , , o]) => !denver || o === "Denver");
  return (
    <Artboard id={frame.id} badge={frame.badge} name={frame.name} note={frame.note}>
      <DashboardLayout
        embedded
        height={860}
        toolbar={TOOLBAR}
        greeting={`Good morning, ${frame.greet}`}
        date={DATE}
        caption={view.caption}
        office={{
          ...office(where, setWhere),
          // Only the views the artboards draw are fixtures (DECISIONS.md, F-05-T46).
          options: ["Denver"],
        }}
        running={RUNNING}
        tiles={<Tpl11Tiles view={view} who={frame.who} />}
        queue={{
          title: frame.who === "KO" ? "My returns" : "Waiting on you",
          count: rows.length,
          children: (
            <>
              {rows.length === 0 ? (
                <QueueEmpty title="Nothing waiting on you.">
                  Decisions, sign-offs and approvals that need you appear here.
                </QueueEmpty>
              ) : (
                <ul>
                  {rows.map((r) => (
                    <QueueRow
                      key={r.t}
                      icon={r.icon}
                      title={r.t}
                      context={r.c}
                      due={{ label: r.due, variant: ROW_VARIANT[r.kind] }}
                      href={`#${frame.id}`}
                      hint={r.go}
                    />
                  ))}
                </ul>
              )}
              {engagements.length > 0 && (
                <section aria-label="Your engagements">
                  <h3 className="flex h-[30px] items-center bg-band-hd px-[14px] text-dense font-medium hairline-b">
                    Your engagements
                  </h3>
                  <ul>
                    {engagements.map(([t, meta, state]) => (
                      <li
                        key={t}
                        className="flex h-[38px] items-center gap-[10px] px-[14px] text-body hairline-b"
                      >
                        <span className="min-w-0 flex-1 truncate">{t}</span>
                        {meta !== "" && <span className="text-meta text-ink-3">{meta}</span>}
                        <Pill variant="amber" size="state">
                          {state}
                        </Pill>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          ),
        }}
        side={[
          {
            title: "Deadlines · next 14 days",
            children: (
              <ul>
                {deadlines.map(([d, client, form, status, o]) => (
                  <DeadlineRow
                    key={`${d}${client}${form}`}
                    date={d}
                    dateTone={Number(d.split(" ")[1]) <= 21 ? "red" : "amber"}
                    client={client}
                    form={form}
                    {...(o === "All"
                      ? { link: { label: "View all →", href: `#${frame.id}` } }
                      : { status: { label: status, variant: "amber" as const } })}
                  />
                ))}
              </ul>
            ),
          },
          {
            title: "Client activity",
            children: (
              <ul className="py-[4px]">
                {ACTIVITY.map(([icon, when, text]) => (
                  <ActivityRow key={text} icon={icon} text={text} when={when} layout="lead" />
                ))}
              </ul>
            ),
          },
        ]}
      />
    </Artboard>
  );
}

/** TPL-11a to TPL-11f (Wave 0 - Templates TPL-11). */
export function Tpl11Specimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      {TPL11_FRAMES.map((frame) => (
        <Tpl11Board key={frame.id} frame={frame} />
      ))}
    </div>
  );
}
