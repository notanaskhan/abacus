// P-05-T03 (TASK-6504; SPEC-650; P-05 §5.4; DEC-3104): comments v2 and to-dos in fixture mode, one
// artboard state at a time, for SHL-17 a–f and SHL-18 a, b, b2, c, d, e, f. Words and figures are
// the handoff's (SHL-17 and SHL-18 spec.md) and blueprint §9.8.3/§9.8.4; clocks are CT. Synthetic
// only: Brightwater Hale. Shapes are the generated client's (`collaboration/contract.py`).
import type {
  AnchorFactsOut,
  MentionCandidatesOut,
  PersonCandidateOut,
  PersonRefOut,
  ThreadOut,
  TodoChecklistItemOut,
  TodoOut,
  TodoPageOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

export const CLOCKS = {
  shl18a: "2026-09-14T12:35:00-05:00",
  shl18b: "2026-09-14T12:34:00-05:00",
  shl17a: "2026-09-14T12:36:00-05:00",
  shl17c: "2026-09-14T12:40:00-05:00",
  shl17d: "2026-09-21T08:30:00-05:00",
  shl17e: "2026-09-28T09:00:00-05:00",
  shl18d: "2026-10-21T14:10:00-05:00",
  shl18e: "2026-09-24T09:00:00-05:00",
  shl18f: "2026-09-23T09:00:00-05:00",
} as const;

export const PERSONAS = {
  margaret: "margaret-okonkwo",
  hannah: "hannah-leclerc",
  marcus: "marcus-delaney",
  kira: "kira-ross",
  cole: "cole-hart",
  simone: "simone-baptiste",
  omar: "omar-haddad",
} as const;

function person(slug: string, name: string, initials: string): PersonRefOut {
  return { user_id: stableId(`user:${slug}`), name, initials };
}

export const P = {
  margaret: person("margaret-okonkwo", "Margaret Okonkwo", "MO"),
  hannah: person("hannah-leclerc", "Hannah Leclerc", "HL"),
  marcus: person("marcus-delaney", "Marcus Delaney", "MD"),
  ana: person("ana-cruz", "Ana Cruz", "AC"),
  thomas: person("thomas-whitcombe", "Thomas Whitcombe", "TW"),
  kira: person("kira-ross", "Kira Ross", "KR"),
  laura: person("laura-kemp", "Laura Kemp", "LK"),
  cole: person("cole-hart", "Cole Hart", "CH"),
  simone: person("simone-baptiste", "Simone Baptiste", "SB"),
  omar: person("omar-haddad", "Omar Haddad", "OH"),
  renee: person("renee-pruett", "Renee Pruett", "RP"),
} as const;

export const IDS = {
  northwind: stableId("engagement:northwind:py2025"),
  granite: stableId("engagement:granite-peak:fy2026"),
  harlow: stableId("engagement:harlow-pike:fy2026"),
  tessellate: stableId("engagement:tessellate:soc2-type2"),
  exceptions: stableId("workpaper:northwind:internal-control-exceptions"),
  cashFlows: stableId("statement-line:granite-peak:fy2026:dividends-paid"),
  componentRoom: stableId("component-thread:harlow-pike:pruett-lang"),
  threadRow3: stableId("comment-thread:northwind:exceptions-a3"),
  commentRow3: stableId("thread-comment:northwind:exceptions-a3:mo-1235"),
  threadDividends: stableId("comment-thread:granite-peak:dividends-paid"),
  threadComponent: stableId("comment-thread:harlow-pike:pruett-lang"),
  todoRow6: stableId("todo:northwind:exceptions-row6"),
  todoE2: stableId("todo:tessellate:e2-cc81"),
  todoSurl: stableId("todo:granite-peak:surl-rerequest"),
  todoForm5500: stableId("todo:northwind:form5500-timeline"),
  todoReview7: stableId("todo:northwind:review-7-exceptions"),
  todoLoanOffsets: stableId("todo:northwind:loan-offsets"),
} as const;

const exceptionsRow = (row: number, label: string): AnchorFactsOut => ({
  anchor_kind: "workpaper",
  anchor_id: IDS.exceptions,
  locator: { sheet: "Exceptions", row },
  label,
  engagement_id: IDS.northwind,
  client_visible: false,
});

// --- SHL-18 -----------------------------------------------------------------------------------------

export type Shl18State = "a" | "b" | "b2" | "c" | "d" | "e" | "f";

/** SHL-18a: Margaret's comment on Exceptions!A3, Hannah notified. */
export function row3Thread(): ThreadOut {
  return {
    id: IDS.threadRow3,
    anchor: {
      anchor_kind: "workpaper",
      anchor_id: IDS.exceptions,
      locator: { sheet: "Exceptions", cell: "A3" },
      label: "Exceptions!A3 · Northwind PY2025",
      engagement_id: IDS.northwind,
      client_visible: false,
    },
    engagement_id: IDS.northwind,
    status: "open",
    visibility: "internal",
    opened_on_version_no: 1,
    pinned_version_no: null,
    comment_count: 1,
    last_comment_at: CLOCKS.shl18a,
    comments: [
      {
        id: IDS.commentRow3,
        author: P.margaret,
        author_side: "firm",
        body: "@Hannah Leclerc this cutoff item drives AJE-1 — show it as factual on the SUM.",
        mentioned_user_ids: [P.hannah.user_id],
        citation_ids: [],
        created_at: CLOCKS.shl18a,
      },
    ],
    events: [{ kind: "opened", actor: P.margaret, created_at: CLOCKS.shl18a }],
    allowed_actions: ["comment.create", "comment.resolve", "review_note.raise", "todo.create"],
  };
}

/** SHL-18d: the Granite Peak dividends thread, resolved by Hannah at 11:05 AM (A-10 host). */
export function dividendsThread(): ThreadOut {
  const at1040 = "2026-10-21T10:40:00-05:00";
  const at1105 = "2026-10-21T11:05:00-05:00";
  return {
    id: IDS.threadDividends,
    anchor: {
      anchor_kind: "statement_line",
      anchor_id: IDS.cashFlows,
      locator: null,
      label: "Statement of cash flows › Dividends paid",
      engagement_id: IDS.granite,
      client_visible: false,
    },
    engagement_id: IDS.granite,
    status: "resolved",
    visibility: "internal",
    opened_on_version_no: 1,
    comment_count: 2,
    last_comment_at: at1105,
    comments: [
      {
        id: stableId("thread-comment:granite-peak:dividends:mo-1040"),
        author: P.margaret,
        author_side: "firm",
        body: "@Hannah Leclerc dividends paid now shows 1,100,000 — agree it to the June 20 board minutes before the draft goes out.",
        mentioned_user_ids: [P.hannah.user_id],
        citation_ids: [],
        created_at: at1040,
      },
      {
        id: stableId("thread-comment:granite-peak:dividends:hl-1105"),
        author: P.hannah,
        author_side: "firm",
        body: "Agreed to the June 20, 2026 board minutes: dividends of 1,100,000 declared. [1]",
        mentioned_user_ids: [],
        // [1] cites "Board minutes — June 20, 2026.pdf · p. 2" (C4).
        citation_ids: [stableId("citation:granite-peak:board-minutes-june-20")],
        created_at: at1105,
      },
    ],
    events: [
      { kind: "opened", actor: P.margaret, created_at: at1040 },
      { kind: "resolved", actor: P.hannah, created_at: at1105 },
    ],
    allowed_actions: ["comment.create", "comment.resolve"],
  };
}

/** SHL-18f: the Pruett & Lang thread, shared through the component grant (A-09 host). */
export function componentThread(): ThreadOut {
  const at = "2026-09-23T09:00:00-05:00";
  return {
    id: IDS.threadComponent,
    anchor: {
      anchor_kind: "component_thread",
      anchor_id: IDS.componentRoom,
      locator: null,
      label: "Pruett & Lang LLP",
      engagement_id: IDS.harlow,
      client_visible: true,
    },
    engagement_id: IDS.harlow,
    status: "open",
    visibility: "shared",
    opened_on_version_no: null,
    comment_count: 2,
    last_comment_at: at,
    comments: [
      {
        id: stableId("thread-comment:harlow-pike:rp-question"),
        author: P.renee,
        author_side: "client",
        body: "Is component PM based on the component's own benchmark or allocated from group?",
        mentioned_user_ids: [],
        citation_ids: [],
        created_at: at,
      },
      {
        id: stableId("thread-comment:harlow-pike:oh-answer"),
        author: P.omar,
        author_side: "firm",
        body: "Allocated from group PM 180,000, weighted by component risk; see instructions §4.",
        mentioned_user_ids: [],
        citation_ids: [],
        created_at: at,
      },
    ],
    events: [{ kind: "shared", actor: P.omar, created_at: at }],
    // Shared threads never offer "Convert to review note…" (SHL-18f).
    allowed_actions: ["comment.create", "comment.resolve"],
  };
}

const candidate = (p: PersonRefOut, title: string | null, isSelf = false): PersonCandidateOut => ({
  user_id: p.user_id,
  name: p.name,
  initials: p.initials,
  title,
  is_self: isSelf,
  selectable: true,
  reason: null,
});

/** The five people on Northwind PY2025 (SHL-18b2, SHL-17b): never the agent. */
export const NORTHWIND_TEAM: PersonCandidateOut[] = [
  candidate(P.hannah, "Audit Senior Manager"),
  candidate(P.marcus, "Audit Senior"),
  candidate(P.ana, "Audit Staff"),
  candidate(P.thomas, "EQR"),
  candidate(P.margaret, null, true), // "Margaret Okonkwo (you)"
];

export function mentionCandidates(state: "b" | "b2" | "c"): MentionCandidatesOut {
  if (state === "b") {
    return { team: null, members: NORTHWIND_TEAM.filter((c) => c.name.startsWith("Ha")) };
  }
  if (state === "c") {
    return {
      team: null,
      members: [],
      // Simone is a Brightwater Hale member not on Northwind; a walled person is absent (DEC-43).
      not_on_engagement: [
        {
          ...candidate(P.simone, "Audit Senior · Denver"),
          selectable: false,
          reason: "not_on_engagement",
        },
      ],
    };
  }
  return {
    team: { label: "Northwind PY2025 team", member_count: 5 },
    members: NORTHWIND_TEAM,
  };
}

// --- SHL-17 -----------------------------------------------------------------------------------------

export type Shl17State = "a" | "b" | "c" | "d" | "e" | "f";

const item = (
  todo: string,
  position: number,
  text: string,
  done = false,
  doneBy: PersonRefOut | null = null,
  doneAt: string | null = null,
): TodoChecklistItemOut => ({
  id: stableId(`todo-checklist-item:${todo}:${String(position)}`),
  position,
  text,
  done,
  done_by: doneBy,
  done_at: doneAt,
});

/** SHL-17a/c: Margaret's to-do on Exceptions row 6 for Marcus, due Wed Sep 16. */
export function row6Todo(viewer: "margaret" | "marcus" = "margaret"): TodoOut {
  return {
    id: IDS.todoRow6,
    scope_kind: "engagement",
    engagement_id: IDS.northwind,
    title: "Request opt-out elections for the 4 auto-enrolled participants",
    status: "open",
    overdue: false,
    bucket: "this_week",
    assignee: P.marcus,
    created_by: P.margaret,
    created_at: CLOCKS.shl17a,
    due_on: "2026-09-16",
    anchor: exceptionsRow(6, "Northwind · Exceptions row 6"),
    row_text:
      "Auto-enrolled participants with no deferrals — 4 auto-enrolled employees have no deferrals and no opt-out election on file.",
    source_thread_id: null,
    unread: viewer === "marcus",
    checklist: [
      item("row6", 1, "List the 4 participants from EBP-04 Participant data F12:F15"),
      item("row6", 2, "Ask Dana Kowalski for their signed opt-out elections"),
      item("row6", 3, "Link what comes back to Exceptions row 6"),
      item("row6", 4, "If none exist, raise the missed-deferral finding in Findings"),
    ],
    comment_count: 1,
    version: 1,
    allowed_actions: [
      "todo.update",
      "todo.complete",
      "todo.assign",
      "todo.delete",
      "comment.create",
    ],
  };
}

/** SHL-17d: Kira's overdue E-2 to-do on Tessellate (X-01 host; fixture only). */
export function e2Todo(): TodoOut {
  return {
    id: IDS.todoE2,
    scope_kind: "engagement",
    engagement_id: IDS.tessellate,
    title: "Chase E-2 management response (CC8.1)",
    status: "open",
    overdue: true,
    bucket: "overdue",
    assignee: P.kira,
    created_by: P.laura,
    created_at: "2026-09-15T09:00:00-05:00",
    due_on: "2026-09-18",
    anchor: {
      anchor_kind: "attest_exception",
      anchor_id: stableId("attest-exception:tessellate:e2"),
      locator: null,
      label: "SOC 2 Type 2 › Exceptions › E-2 · CC8.1 · TES-52",
      engagement_id: IDS.tessellate,
      client_visible: false,
    },
    row_text: "1 of 25 changes: CHG-2041 deployed Mar 12, 2026, approved Mar 15, 2026",
    checklist: [
      item(
        "e2",
        1,
        "Remind Marisol Vega in the portal",
        true,
        P.kira,
        "2026-09-16T10:00:00-05:00",
      ),
      item("e2", 2, "Log her response on E-2"),
    ],
    version: 2,
    allowed_actions: ["todo.update", "todo.complete", "todo.assign", "comment.create"],
  };
}

/** SHL-17e: Cole's done SURL to-do on Granite Peak (K-03 host; fixture only). */
export function surlTodo(): TodoOut {
  return {
    id: IDS.todoSurl,
    scope_kind: "engagement",
    engagement_id: IDS.granite,
    title: "Re-request 2 SURL files",
    status: "done",
    overdue: false,
    bucket: null,
    assignee: P.cole,
    created_by: P.cole,
    created_at: "2026-09-26T09:00:00-05:00", // "Created Cole Hart · Sep 26"
    due_on: "2026-09-28",
    anchor: {
      anchor_kind: "sheet_row",
      anchor_id: stableId("request:granite-peak:bh-fs-430"),
      locator: null,
      label: "BH-FS-430 · SURL request",
      engagement_id: IDS.granite,
      client_visible: false,
    },
    row_text:
      "Evidence screening flagged a statement for payment #40188 ($23,940) and an invoice that matches payment #40171, not #40117.",
    done_by: P.cole,
    done_at: CLOCKS.shl17e,
    // "✓ Done by Cole Hart · Sep 28 · corrected files received, 40 of 40"
    checklist: [],
    version: 3,
    allowed_actions: ["todo.complete", "comment.create"],
  };
}

const myTodo = (
  id: string,
  title: string,
  from: PersonRefOut,
  label: string,
  due: string,
  bucket: "overdue" | "today" | "this_week",
  unread = false,
): TodoOut => ({
  id,
  scope_kind: "engagement",
  engagement_id: IDS.northwind,
  title,
  status: "open",
  overdue: bucket === "overdue",
  bucket,
  assignee: P.marcus,
  created_by: from,
  created_at: "2026-09-10T09:00:00-05:00",
  due_on: due,
  anchor: {
    anchor_kind: "workpaper",
    anchor_id: IDS.exceptions,
    locator: null,
    label,
    engagement_id: IDS.northwind,
    client_visible: false,
  },
  unread,
  version: 1,
  allowed_actions: ["todo.update", "todo.complete", "comment.create"],
});

/** SHL-17f: Marcus's My to-dos at 12:40 PM: 1 overdue + 1 today + 2 this week = 4 open. */
export function myTodos(): TodoPageOut {
  const items = [
    myTodo(
      IDS.todoForm5500,
      "Confirm Summit Plan Administrators' Form 5500 timeline",
      P.hannah,
      "Draft Form 5500 & Schedule H",
      "2026-09-11",
      "overdue",
    ),
    myTodo(
      IDS.todoReview7,
      "Review the 7 Internal Control exceptions before Hannah's review",
      P.marcus,
      "Internal Control › Exceptions",
      "2026-09-14",
      "today",
    ),
    { ...row6Todo("marcus"), anchor: exceptionsRow(6, "Exceptions row 6") },
    myTodo(
      IDS.todoLoanOffsets,
      "Confirm the 3 loan offsets ($14,850) are reported as distributions on Schedule H",
      P.hannah,
      "Exceptions row 7",
      "2026-09-18",
      "this_week",
    ),
  ];
  return {
    items,
    total: 4,
    counts: { open: 4, done: 0, overdue: 1, today: 1, this_week: 2, later: 0, no_date: 0 },
  };
}

export function todoFor(state: Shl17State): TodoOut | null {
  switch (state) {
    case "a":
      return row6Todo("margaret");
    case "c":
      return row6Todo("marcus");
    case "d":
      return e2Todo();
    case "e":
      return surlTodo();
    default:
      return null; // b is a new to-do; f is the list
  }
}
