import type { IconName } from "../icons";

// C-16 Request kit, portal variant (F-05-T36): the generic shapes the kit draws and its pure rules,
// ported from the C-16 handoff (`reference/request-rows-types.ts`). Data comes in through props
// and intents go out through callbacks; nothing here calls the API (L2). Keys keep the kit's short
// names so the handoff's rules read across one for one. The firm's name is always a parameter:
// the kit never names a firm, and never the product.

/** Stored request status (DEC-09 words are the server's; these are the kit's view states).
 * req requested · up uploaded by the client · acc accepted by the firm · fu needs follow-up ·
 * na not applicable (ignored with a reason) · firm the firm provides it · ret returned by the firm. */
export type RequestStatus = "req" | "up" | "acc" | "fu" | "na" | "firm" | "ret";

export type CategoryKey =
  "personal" | "income" | "home" | "health" | "edu" | "retire" | "charity" | "business" | "other";

export interface RequestCategory {
  key: CategoryKey;
  label: string;
  icon: IconName;
}

/** The nine CategoryRail rows, in order (C-16 spec 3). */
export const CATEGORIES: readonly RequestCategory[] = [
  { key: "personal", label: "Personal & Household Information", icon: "circle-user-round" },
  { key: "income", label: "Income Sources", icon: "banknote" },
  { key: "home", label: "Home & Property", icon: "house" },
  { key: "health", label: "Health & Medical", icon: "heart" },
  { key: "edu", label: "Education & Student", icon: "graduation-cap" },
  { key: "retire", label: "Retirement", icon: "piggy-bank" },
  { key: "charity", label: "Charitable & Donations", icon: "hand-heart" },
  { key: "business", label: "Business & Self-Employment", icon: "briefcase" },
  { key: "other", label: "Other Activity", icon: "ellipsis" },
];

export interface RequestSectionData {
  key: string;
  /** The rail row it rolls up to. */
  category: CategoryKey;
  /** Client language: "W-2s". The firm's internal name never reaches the client. */
  title: string;
  icon: IconName;
}

export interface RequestItem {
  id: string;
  /** `RequestSectionData.key`. */
  sec: string;
  /** Plain client language, no internal codes. */
  title: string;
  st: RequestStatus;
  /** The requested date, "Jul 14". */
  req: string;
  /** The file that satisfies it. */
  file?: string;
  /** Every file, when a second upload lands on an already-matched request. */
  files?: readonly string[];
  /** The expected file name: an upload of exactly this name routes here first. */
  fname?: string;
  /** The latest event's date: uploaded (up) or accepted (acc). */
  on?: string;
  /** The uploaded date when `on` is the acceptance date. */
  up?: string;
  /** The firm's follow-up note (fu, ret) or the firm-provided text (firm). */
  note?: string;
  /** The Ignore reason (na). */
  reason?: string;
  /** The optional note typed in the Ignore menu. */
  naNote?: string;
  /** An upload nobody asked for: hidden by the Requested filter. */
  extra?: boolean;
  /** Set when an upload was routed here: "Matched to this request". */
  matched?: boolean;
  /** A code-rule link no person has accepted yet: the line reads "Suggested — ‹firm› will
   * confirm" instead (DEC-58 a; POR-03 c). */
  suggested?: boolean;
  /** The date the client replied to a follow-up. */
  replied?: string;
  retLabel?: string;
  /** A line under a requested row while a file for it uploads: "Uploading 2 files…". */
  uploading?: string;
  /** Overrides the uploaded line: "Received by email Aug 3", "Jonah uploaded Aug 5". */
  upText?: string;
  /** An open request's due line in the audit variant's bands: "Due Sep 18". */
  due?: string;
}

/** A file in flight, `p` from 0 to 1. */
export interface UploadInFlight {
  name: string;
  /** Formatted by the caller ("1.1 MB"). */
  size: string;
  p: number;
}

export type RequestFilter = "requested" | "all" | "uploaded" | "fu";

export const FILTERS: readonly { value: RequestFilter; label: string }[] = [
  { value: "requested", label: "Requested" },
  { value: "all", label: "All" },
  { value: "uploaded", label: "Uploaded" },
  { value: "fu", label: "Needs follow-up" },
];

/** The three Ignore reasons (C-16 spec 9, TPL-07f). */
export const IGNORE_REASONS = [
  "Not applicable this year",
  "Already sent another way",
  "I don’t have this",
] as const;

/** Counts toward "everything is in": uploaded, accepted, not applicable or firm-provided. */
export function satisfied(r: RequestItem): boolean {
  return r.st === "up" || r.st === "acc" || r.st === "na" || r.st === "firm";
}

/** Filter × category. Requested keeps every requested item in any state and hides only uploads
 * nobody asked for. */
export function keep(
  r: RequestItem,
  filter: RequestFilter,
  cat: CategoryKey | null,
  sections: readonly RequestSectionData[],
): boolean {
  const byFilter =
    filter === "all"
      ? true
      : filter === "uploaded"
        ? r.st === "up" || r.st === "acc"
        : filter === "fu"
          ? r.st === "fu"
          : r.extra !== true;
  const sec = sections.find((s) => s.key === r.sec);
  return byFilter && (cat === null || sec?.category === cat);
}

export interface CategoryState {
  /** Every request in it is satisfied: the 19 olive disc. */
  done: boolean;
  /** Nothing requested in it: ink-3 label, ink-4 glyph. */
  none: boolean;
}

/** A CategoryRail row's state; `doneCats` forces the disc on (the firm's own categories). */
export function categoryState(
  key: CategoryKey,
  visible: readonly RequestItem[],
  sections: readonly RequestSectionData[],
  doneCats: readonly CategoryKey[] = [],
): CategoryState {
  const mine = visible.filter((r) => sections.find((s) => s.key === r.sec)?.category === key);
  const forced = doneCats.includes(key);
  return {
    done: (mine.length > 0 && mine.every(satisfied)) || forced,
    none: mine.length === 0 && !forced,
  };
}

export interface DoneButtonView {
  ready: boolean;
  open: number;
  ariaDisabled: boolean;
  label: string;
  tip: string;
}

/** Mark as Done: tonal until every requested item is satisfied, then olive. Never `disabled`. */
export function doneButton(visible: readonly RequestItem[], done: boolean): DoneButtonView {
  const open = visible.filter((r) => r.extra !== true && !satisfied(r)).length;
  const ready = open === 0;
  return {
    ready,
    open,
    ariaDisabled: !ready || done,
    label: done ? "Marked as Done" : "Mark as Done",
    tip: ready
      ? done
        ? "Your firm has been told"
        : "Tell your firm everything is in"
      : `${String(open)} request${open > 1 ? "s" : ""} still open`,
  };
}

/** "Marked not applicable", then the reason unless it is the default one, then the note. */
export function naText(r: RequestItem): string {
  const reason =
    r.reason !== undefined && r.reason !== "Not applicable this year" ? ` · ${r.reason}` : "";
  const note = r.naNote !== undefined && r.naNote !== "" ? ` · “${r.naNote}”` : "";
  return `Marked not applicable${reason}${note}`;
}

export interface RowView {
  titleMuted: boolean;
  docFilled: boolean;
  fileLines: readonly string[];
  uploaded: string | null;
  matched: boolean;
  /** "Suggested — ‹firm› will confirm" under a code-rule link (DEC-58 a). */
  suggested: string | null;
  accepted: string | null;
  uploadLink: boolean;
  followUp: { note: string; reply: boolean; replied: string | null } | null;
  returned: { label: string; note: string } | null;
  firmProvided: string | null;
  notApplicable: string | null;
  trash: boolean;
  ignore: boolean;
}

/** The lines a client-side row shows, by status (C-16 spec 6). */
export function rowView(r: RequestItem, firm: string): RowView {
  const st = r.st;
  const upText = r.upText ?? `You uploaded ${r.on ?? r.up ?? ""}`;
  return {
    titleMuted: st === "na",
    docFilled: !(st === "req" || st === "ret" || st === "na" || st === "firm"),
    fileLines: r.file !== undefined && st !== "na" && st !== "req" ? (r.files ?? [r.file]) : [],
    uploaded: st === "up" ? upText : null,
    matched: st === "up" && r.matched === true && r.suggested !== true,
    suggested: st === "up" && r.suggested === true ? `Suggested — ${firm} will confirm` : null,
    accepted: st === "acc" ? `Accepted by ${firm} · ${r.on ?? ""}` : null,
    uploadLink: st === "req",
    followUp:
      st === "fu"
        ? {
            note: r.note ?? "",
            reply: r.replied === undefined,
            replied: r.replied === undefined ? null : `You replied ${r.replied}`,
          }
        : null,
    returned: st === "ret" ? { label: r.retLabel ?? "Returned", note: r.note ?? "" } : null,
    firmProvided: st === "firm" ? (r.note ?? "") : null,
    notApplicable: st === "na" ? naText(r) : null,
    trash: st === "up" && (r.matched === true || upText.startsWith("You uploaded")),
    ignore: st === "req",
  };
}

/** Where a finished upload goes: an exact `fname`, then an exact `file`, among open requests; then
 * the keyword table (substring → request id). Null: the firm sorts it. */
export function route(
  name: string,
  all: readonly RequestItem[],
  keywords: readonly (readonly [string, string])[] = [],
): RequestItem | null {
  const n = name.toLowerCase();
  const open = all.filter(
    (r) =>
      r.st === "req" || r.st === "fu" || r.st === "ret" || (r.st === "up" && r.matched === true),
  );
  const exact =
    open.find((r) => r.fname?.toLowerCase() === n) ??
    open.find((r) => r.file?.toLowerCase() === n);
  if (exact !== undefined) return exact;
  for (const [k, id] of keywords) {
    if (!n.includes(k)) continue;
    const hit = all.find((x) => x.id === id && (x.st === "req" || x.st === "fu" || x.st === "up"));
    if (hit !== undefined) return hit;
  }
  return null;
}

/** A routed upload applied to its request. A second file on a matched request is added under it. */
export function applyUpload(r: RequestItem, name: string, today: string): RequestItem {
  const again = r.st === "up" && r.matched === true;
  return {
    ...withoutKeys(r, ["upText", "uploading"]),
    st: "up",
    file: again && r.file !== undefined ? r.file : name,
    files: again ? [...(r.files ?? (r.file === undefined ? [] : [r.file])), name] : [name],
    on: today,
    matched: true,
  };
}

type OptionalKey = Exclude<keyof RequestItem, "id" | "sec" | "title" | "st" | "req">;

/** The request without some of its optional fields (an undo, a removal, a finished upload). */
export function withoutKeys(r: RequestItem, keys: readonly OptionalKey[]): RequestItem {
  return Object.fromEntries(
    Object.entries(r).filter(([k]) => !(keys as readonly string[]).includes(k)),
  ) as unknown as RequestItem;
}

/** The DropZone ring's progress: the average of the files in flight, 0 with none. */
export function averageProgress(uploads: readonly UploadInFlight[]): number {
  if (uploads.length === 0) return 0;
  return uploads.reduce((sum, u) => sum + u.p, 0) / uploads.length;
}
